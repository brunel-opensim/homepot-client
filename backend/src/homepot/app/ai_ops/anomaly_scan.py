"""Scheduled anomaly scan for multi-level detection.

The on-demand ``GET /api/v1/ai/anomalies`` scan was single-tier and ephemeral:
it recomputed a score on every poll and never remembered anything, so it could
not tell a transient CPU spike from a persistent problem. This module owns the
scheduled scan that:

* appends one :class:`~homepot.app.models.AnalyticsModel.AnomalyScan` row per
  device per pass,
* classifies each device into a 0-3 level using recent breach history (the
  "multi-level" core), and
* syncs online/offline status as a side effect (as the old endpoint did).

The endpoint now reads the persisted scans instead of recomputing on every poll.
Promotion/de-escalation of the ``is_monitored`` flag is a follow-up; the level
is computed and stored here so it is ready for that step.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from homepot.app.models.AnalyticsModel import AnomalyScan, DeviceMetrics
from homepot.models import (
    ConnectivityState,
    Device,
    DeviceStatus,
    HealthCheck,
    compute_connectivity,
)

logger = logging.getLogger(__name__)

#: Default background scan cadence (seconds).
ANOMALY_SCAN_INTERVAL_SECONDS = 5 * 60

#: Config fallbacks (see ``anomaly_detection`` in ``ai/config.yaml``).
DEFAULT_PERSISTENCE_WINDOW_MINUTES = 60
DEFAULT_PERSISTENT_BREACH_COUNT = 3
DEFAULT_FLAPPING_WINDOW_CHECKS = 50

#: A single health-check failure at/above this count promotes to Level 2
#: regardless of score (matches the detector's "System Failure" signal).
_STATUS_SYNC_FAILURE_THRESHOLD = 3


def classify_anomaly_level(
    score: float,
    *,
    consecutive_failures: float = 0.0,
    flapping_count: float = 0.0,
    consecutive_failure_threshold: float = 3.0,
    flapping_threshold: float = 5.0,
    breach_count: int = 0,
    persistent_breach_count: int = DEFAULT_PERSISTENT_BREACH_COUNT,
) -> int:
    """Map a scan score plus persistence signals onto a 0-3 anomaly level.

    * 0 — normal (no breach).
    * 1 — transient (a single low-impact breach).
    * 2 — persistent (repeated breaches, consecutive failures, or flapping).
    * 3 — critical (score >= 0.8).
    """
    if score <= 0:
        return 0
    if score >= 0.8:
        return 3
    if consecutive_failures >= consecutive_failure_threshold:
        return 2
    if flapping_count > flapping_threshold:
        return 2
    if breach_count >= persistent_breach_count:
        return 2
    return 1


def _severity_for(level: int) -> str:
    if level >= 3:
        return "critical"
    if level == 2:
        return "warning"
    return "normal"


def _count_flapping(checks: List[Any]) -> int:
    """Count healthy<->unhealthy transitions over the provided checks."""
    ordered = sorted(checks, key=lambda c: c.timestamp)
    return sum(
        1
        for i in range(1, len(ordered))
        if ordered[i].is_healthy != ordered[i - 1].is_healthy
    )


def _count_consecutive_failures(checks: List[Any]) -> int:
    """Count leading unhealthy checks starting from the newest."""
    ordered = sorted(checks, key=lambda c: c.timestamp, reverse=True)
    count = 0
    for check in ordered:
        if not check.is_healthy:
            count += 1
        else:
            break
    return count


def _summary(
    device: Any, score: float, reasons: List[str], level: int, metrics: Dict[str, Any]
) -> Dict[str, Any]:
    """Build an anomaly dict matching the shape the endpoint used to return."""
    return {
        "device_id": device.device_id,
        "device_name": device.name,
        "score": round(score, 2),
        "level": level,
        "reasons": reasons,
        "severity": _severity_for(level),
        "metrics": metrics,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def _gather_metrics(
    session: Any, device: Any, flapping_window: int
) -> Dict[str, Any]:
    """Compute the metric dict for one device from its latest row + checks."""
    metrics: Dict[str, Any] = {}

    latest = (
        (
            await session.execute(
                select(DeviceMetrics)
                .where(DeviceMetrics.device_id == device.id)
                .order_by(DeviceMetrics.timestamp.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if latest is not None:
        metrics.update(
            {
                "cpu_percent": latest.cpu_percent,
                "memory_percent": latest.memory_percent,
                "disk_percent": latest.disk_percent,
                "network_latency_ms": latest.network_latency_ms,
                "error_rate": latest.error_rate,
            }
        )
        ts = latest.timestamp
        if ts is not None:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            metrics["stale_telemetry"] = (
                datetime.now(timezone.utc) - ts
            ).total_seconds() > 600
        else:
            metrics["stale_telemetry"] = True
        metrics["no_telemetry"] = False
    else:
        metrics["no_telemetry"] = True
        metrics["stale_telemetry"] = False

    # Connectivity: separate a deliberate "goodbye" (graceful shutdown) from an
    # unexpected outage. A graceful shutdown sends a final offline heartbeat that
    # sets ``status=offline`` and clears the heartbeat; a crash/power loss leaves
    # ``status=online`` with a stale heartbeat. Only the latter is monitor-worthy.
    is_offline = compute_connectivity(device) == ConnectivityState.OFFLINE.value
    graceful_offline = device.status == DeviceStatus.OFFLINE.value
    metrics["graceful_offline"] = graceful_offline
    metrics["connectivity_offline"] = is_offline and not graceful_offline

    # Flapping over a real window (previously only the last 5 checks, which
    # could never exceed a threshold of 5 state changes).
    checks = (
        (
            await session.execute(
                select(HealthCheck)
                .where(HealthCheck.device_id == device.id)
                .order_by(HealthCheck.timestamp.desc())
                .limit(flapping_window)
            )
        )
        .scalars()
        .all()
    )
    metrics["flapping_count"] = float(_count_flapping(checks))
    metrics["consecutive_failures"] = float(_count_consecutive_failures(checks))
    return metrics


async def _count_prior_breaches(
    session: Any, device_id: str, window_start: datetime
) -> int:
    count = (
        await session.execute(
            select(func.count())
            .select_from(AnomalyScan)
            .where(
                AnomalyScan.device_id == device_id,
                AnomalyScan.timestamp >= window_start,
                AnomalyScan.score > 0,
            )
        )
    ).scalar() or 0
    return int(count)


def _sync_status(device: Any, metrics: Dict[str, Any]) -> None:
    """Sync online/offline status from consecutive health-check failures."""
    consecutive = metrics.get("consecutive_failures", 0.0)
    if consecutive >= _STATUS_SYNC_FAILURE_THRESHOLD:
        if device.status != "offline":
            device.status = "offline"  # type: ignore[assignment]
    elif consecutive == 0 and device.status == "offline":
        device.status = "online"  # type: ignore[assignment]


async def scan_and_persist(db: Any) -> List[Dict[str, Any]]:
    """Scan every active device, persist its result, return level >= 1 summaries.

    ``db`` is a :class:`~homepot.database.DatabaseService`. Each pass appends an
    ``AnomalyScan`` row (including clean Level 0 rows, so de-escalation can be
    computed later) and syncs device online/offline status.
    """
    from ai.anomaly_detection import AnomalyDetector
    from ai.config import load_ai_config

    detector = AnomalyDetector()
    section = load_ai_config().get("anomaly_detection", {}) or {}
    persistence_minutes = int(
        section.get("persistence_window_minutes", DEFAULT_PERSISTENCE_WINDOW_MINUTES)
    )
    persistent_breach_count = int(
        section.get("persistent_breach_count", DEFAULT_PERSISTENT_BREACH_COUNT)
    )
    flapping_window = int(section.get("window_size", DEFAULT_FLAPPING_WINDOW_CHECKS))
    ignore_graceful_offline = bool(section.get("ignore_graceful_offline", True))

    summaries: List[Dict[str, Any]] = []
    async with db.get_session() as session:
        devices = (
            (await session.execute(select(Device).where(Device.is_active.is_(True))))
            .scalars()
            .all()
        )
        window_start = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            minutes=persistence_minutes
        )

        for device in devices:
            try:
                metrics = await _gather_metrics(session, device, flapping_window)
                score: float
                reasons: List[str]
                if metrics.get("graceful_offline") and ignore_graceful_offline:
                    # Deliberately off (graceful goodbye): not an anomaly, and
                    # leave the offline status exactly as the agent set it (the
                    # status-sync would otherwise flip it back to "online").
                    score, reasons = 0.0, []
                else:
                    score, reasons = detector.check_anomaly(metrics)
                    _sync_status(device, metrics)
                prior = await _count_prior_breaches(
                    session, device.device_id, window_start
                )
                breach_count = prior + (1 if score > 0 else 0)
                level = classify_anomaly_level(
                    score,
                    consecutive_failures=float(
                        metrics.get("consecutive_failures", 0.0)
                    ),
                    flapping_count=float(metrics.get("flapping_count", 0.0)),
                    consecutive_failure_threshold=float(
                        detector.thresholds["consecutive_failures"]
                    ),
                    flapping_threshold=float(detector.thresholds["flapping_count"]),
                    breach_count=breach_count,
                    persistent_breach_count=persistent_breach_count,
                )
                session.add(
                    AnomalyScan(
                        device_id=device.device_id,
                        score=round(score, 4),
                        level=level,
                        severity=_severity_for(level),
                        reasons=reasons,
                    )
                )
                if level >= 1:
                    summaries.append(_summary(device, score, reasons, level, metrics))
            except Exception:
                logger.warning(
                    "Anomaly scan failed for %s", device.device_id, exc_info=True
                )

        await session.commit()
    return summaries


async def latest_anomaly_summaries(db: Any, min_level: int = 2) -> List[Dict[str, Any]]:
    """Return the latest stored scan per device, filtered to ``min_level``.

    Reads the persisted scan history (not a live recompute) so the Dashboard
    poll is cheap and stable between background passes.
    """
    summaries: List[Dict[str, Any]] = []
    async with db.get_session() as session:
        subq = select(
            AnomalyScan,
            func.row_number()
            .over(
                partition_by=AnomalyScan.device_id,
                order_by=AnomalyScan.timestamp.desc(),
            )
            .label("rn"),
        ).subquery()
        scan_alias = aliased(AnomalyScan, subq)
        rows = (
            (await session.execute(select(scan_alias).where(subq.c.rn == 1)))
            .scalars()
            .all()
        )

        names: Dict[str, str] = {}
        device_ids = {row.device_id for row in rows}
        if device_ids:
            devices = (
                (
                    await session.execute(
                        select(Device).where(Device.device_id.in_(device_ids))
                    )
                )
                .scalars()
                .all()
            )
            names = {d.device_id: d.name for d in devices}

        for row in rows:
            if row.level < min_level:
                continue
            summaries.append(
                {
                    "device_id": row.device_id,
                    "device_name": names.get(row.device_id, "Unknown Device"),
                    "score": round(row.score or 0.0, 2),
                    "level": row.level,
                    "reasons": row.reasons or [],
                    "severity": _severity_for(row.level),
                    "metrics": {"source": "anomaly_scan"},
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                }
            )

    summaries.sort(key=lambda x: float(str(x["score"])), reverse=True)
    return summaries


async def run_anomaly_scan_loop() -> None:
    """Run the scheduled anomaly scan forever.

    Started by ``homepot.app.main``; callers own the task lifecycle and should
    cancel it on shutdown. The first pass runs immediately so the endpoint has
    stored results as soon as the service boots.
    """
    from homepot.database import get_database_service

    while True:
        try:
            db = await get_database_service()
            await scan_and_persist(db)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Anomaly scan loop failed", exc_info=True)
        await asyncio.sleep(ANOMALY_SCAN_INTERVAL_SECONDS)
