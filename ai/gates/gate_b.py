"""Gate B: Data Integrity Assurance (paper Sec. 4.2, Table 1).

Evaluates whether accumulated telemetry is complete, fresh, continuous, and
plausible enough to support dependable reasoning. Failing Gate B means the
data's *shape* is fine (Gate A passed) but its *substance* cannot yet be
trusted, so the envelope falls back to Mode 2 (best-effort analytics, limited
trust) -- see ``base.MODE_BEST_EFFORT``.

Thresholds default to the values reported in the paper's Table 1 / Sec. 6.3
(freshness ~5 min baseline heartbeat, continuity gaps <=60s, sustained
discontinuity >60 min) but are configurable per deployment.

TUNABLE: the three DEFAULT_* constants below are the single source of truth
for these thresholds. Adjust them here for a global default, or override
per-call via ``DataIntegrityGate(freshness_max_age_seconds=..., ...)`` /
``build_default_envelope(freshness_max_age_seconds=..., ...)`` -- see
envelope.py's ``build_default_envelope``. None of these are yet validated
against real deployment data.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, List, Optional

from sqlalchemy import or_, select
from sqlalchemy.sql import func

from .base import (
    MODE_BEST_EFFORT,
    CheckResult,
    EvidenceRef,
    Gate,
    GateContext,
    GateResult,
    GateStatus,
)

DEFAULT_FRESHNESS_MAX_AGE_SECONDS = 300  # 5-minute heartbeat baseline (paper Sec. 3.3)
DEFAULT_CONTINUITY_GAP_SECONDS = 60  # paper Table 1
DEFAULT_SUSTAINED_GAP_SECONDS = 3600  # paper Sec. 6.3 ("gaps > 60 min")


class DataIntegrityGate(Gate):
    """Gate B: completeness, freshness, continuity, gap checks, validity (Fig. 2)."""

    def __init__(
        self,
        freshness_max_age_seconds: int = DEFAULT_FRESHNESS_MAX_AGE_SECONDS,
        continuity_gap_seconds: int = DEFAULT_CONTINUITY_GAP_SECONDS,
        sustained_gap_seconds: int = DEFAULT_SUSTAINED_GAP_SECONDS,
    ) -> None:
        """Configure Gate B's tunable thresholds and Mode 2 failure fallback."""
        super().__init__(
            gate_id="B", name="Data Integrity", failure_mode=MODE_BEST_EFFORT
        )
        self.freshness_max_age_seconds = freshness_max_age_seconds
        self.continuity_gap_seconds = continuity_gap_seconds
        self.sustained_gap_seconds = sustained_gap_seconds

    async def evaluate(self, context: GateContext) -> GateResult:
        """Check completeness, freshness, continuity, gaps, and value validity."""
        session = context.session
        if session is None:
            return GateResult(
                gate_id=self.gate_id,
                name=self.name,
                status=GateStatus.FAIL,
                checks=[
                    CheckResult(
                        check_id="B.session",
                        name="Database session available",
                        passed=False,
                        message="No database session supplied to Gate B.",
                    )
                ],
            )

        from homepot.app.models.AnalyticsModel import DeviceMetrics
        from homepot.models import HealthCheck

        window_start = datetime.utcnow() - timedelta(seconds=context.window_seconds)
        device_int_id = context.device_int_id

        checks: List[CheckResult] = [
            await self._check_completeness(
                session, DeviceMetrics, window_start, device_int_id
            ),
            await self._check_freshness(session, DeviceMetrics, device_int_id),
        ]
        checks.extend(
            await self._check_continuity_and_gaps(
                session, HealthCheck, window_start, device_int_id
            )
        )
        checks.append(
            await self._check_validity(
                session, DeviceMetrics, window_start, device_int_id
            )
        )

        status = GateStatus.PASS if all(c.passed for c in checks) else GateStatus.FAIL
        return GateResult(
            gate_id=self.gate_id, name=self.name, status=status, checks=checks
        )

    async def _check_completeness(
        self,
        session: Any,
        DeviceMetrics: Any,
        window_start: datetime,
        device_int_id: Optional[int],
    ) -> CheckResult:
        stmt = select(
            func.count(),
            func.count(DeviceMetrics.cpu_percent),
            func.count(DeviceMetrics.memory_percent),
            func.count(DeviceMetrics.disk_percent),
            func.count(DeviceMetrics.network_latency_ms),
        ).where(DeviceMetrics.timestamp >= window_start)
        if device_int_id:
            stmt = stmt.where(DeviceMetrics.device_id == device_int_id)

        total, cpu_n, mem_n, disk_n, lat_n = (await session.execute(stmt)).one()

        if not total:
            return CheckResult(
                check_id="B.completeness",
                name="Completeness",
                passed=False,
                message="No device_metrics rows in the evaluation window; completeness cannot be confirmed.",
                evidence=[
                    EvidenceRef(
                        table="device_metrics",
                        query_id="B.completeness",
                        extra={"window_start": window_start.isoformat()},
                    )
                ],
            )

        null_counts = {
            "cpu_percent": total - cpu_n,
            "memory_percent": total - mem_n,
            "disk_percent": total - disk_n,
            "network_latency_ms": total - lat_n,
        }
        completeness_ratio = 1 - (sum(null_counts.values()) / (total * 4))
        passed = all(n == 0 for n in null_counts.values())

        return CheckResult(
            check_id="B.completeness",
            name="Completeness",
            passed=passed,
            message=f"Non-null completeness {completeness_ratio:.1%} over {total} rows.",
            evidence=[
                EvidenceRef(
                    table="device_metrics",
                    query_id="B.completeness",
                    observed=null_counts,
                    threshold=0,
                )
            ],
        )

    async def _check_freshness(
        self, session: Any, DeviceMetrics: Any, device_int_id: Optional[int]
    ) -> CheckResult:
        stmt = select(func.max(DeviceMetrics.timestamp))
        if device_int_id:
            stmt = stmt.where(DeviceMetrics.device_id == device_int_id)
        last_ts = (await session.execute(stmt)).scalar()

        if last_ts is None:
            return CheckResult(
                check_id="B.freshness",
                name="Freshness",
                passed=False,
                message="No device_metrics rows found; freshness cannot be confirmed.",
            )

        age_seconds = (datetime.utcnow() - last_ts).total_seconds()
        passed = age_seconds <= self.freshness_max_age_seconds
        return CheckResult(
            check_id="B.freshness",
            name="Freshness",
            passed=passed,
            message=(
                f"Last telemetry {age_seconds:.0f}s old "
                f"(threshold {self.freshness_max_age_seconds}s)."
            ),
            evidence=[
                EvidenceRef(
                    table="device_metrics",
                    field="timestamp",
                    observed=last_ts.isoformat(),
                    threshold=self.freshness_max_age_seconds,
                    query_id="B.freshness",
                )
            ],
        )

    async def _check_continuity_and_gaps(
        self,
        session: Any,
        HealthCheck: Any,
        window_start: datetime,
        device_int_id: Optional[int],
    ) -> List[CheckResult]:
        stmt = (
            select(HealthCheck.timestamp)
            .where(HealthCheck.timestamp >= window_start)
            .order_by(HealthCheck.timestamp.asc())
        )
        if device_int_id:
            stmt = stmt.where(HealthCheck.device_id == device_int_id)

        rows = (await session.execute(stmt)).all()

        if len(rows) < 2:
            msg = "Insufficient health_check samples in window to assess continuity."
            return [
                CheckResult(
                    check_id="B.continuity",
                    name="Continuity",
                    passed=False,
                    message=msg,
                ),
                CheckResult(
                    check_id="B.gap_checks",
                    name="Gap checks",
                    passed=False,
                    message=msg,
                ),
            ]

        max_gap = 0.0
        worst_ts = None
        sustained_gaps = 0
        prev_ts = rows[0][0]
        for (ts,) in rows[1:]:
            gap = (ts - prev_ts).total_seconds()
            if gap > max_gap:
                max_gap = gap
                worst_ts = ts
            if gap > self.sustained_gap_seconds:
                sustained_gaps += 1
            prev_ts = ts

        continuity_passed = max_gap <= self.continuity_gap_seconds
        continuity = CheckResult(
            check_id="B.continuity",
            name="Continuity",
            passed=continuity_passed,
            message=f"Max inter-arrival gap {max_gap:.1f}s (threshold {self.continuity_gap_seconds}s).",
            evidence=[
                EvidenceRef(
                    table="health_checks",
                    field="timestamp",
                    observed=round(max_gap, 1),
                    threshold=self.continuity_gap_seconds,
                    extra={"worst_gap_at": worst_ts.isoformat() if worst_ts else None},
                    query_id="B.continuity",
                )
            ],
        )

        gaps_passed = sustained_gaps == 0
        gap_checks = CheckResult(
            check_id="B.gap_checks",
            name="Gap checks",
            passed=gaps_passed,
            message=f"{sustained_gaps} sustained discontinuities > {self.sustained_gap_seconds}s.",
            evidence=[
                EvidenceRef(
                    table="health_checks",
                    observed=sustained_gaps,
                    threshold=0,
                    query_id="B.gap_checks",
                )
            ],
        )
        return [continuity, gap_checks]

    async def _check_validity(
        self,
        session: Any,
        DeviceMetrics: Any,
        window_start: datetime,
        device_int_id: Optional[int],
    ) -> CheckResult:
        stmt = (
            select(func.count())
            .select_from(DeviceMetrics)
            .where(DeviceMetrics.timestamp >= window_start)
            .where(
                or_(
                    DeviceMetrics.cpu_percent > 100,
                    DeviceMetrics.cpu_percent < 0,
                    DeviceMetrics.memory_percent > 100,
                    DeviceMetrics.memory_percent < 0,
                    DeviceMetrics.disk_percent > 100,
                    DeviceMetrics.disk_percent < 0,
                )
            )
        )
        if device_int_id:
            stmt = stmt.where(DeviceMetrics.device_id == device_int_id)

        violation_count = (await session.execute(stmt)).scalar() or 0
        passed = violation_count == 0
        return CheckResult(
            check_id="B.validity",
            name="Validity",
            passed=passed,
            message=f"{violation_count} range violations (CPU/Memory/Disk outside [0, 100]).",
            evidence=[
                EvidenceRef(
                    table="device_metrics",
                    observed=violation_count,
                    threshold=0,
                    query_id="B.validity",
                )
            ],
        )
