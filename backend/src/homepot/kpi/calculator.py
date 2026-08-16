"""UK demonstrator KPI calculations.

Each function computes one KPI register item (docs/kpi-evaluation-roadmap.md §5)
over a time-bounded, device-filtered population. Functions are async and take
a database session from ``homepot.database.get_database_service`` so results
are reproducible from a clean database snapshot.

Provenance scoping: tables that snapshot a ``provenance`` column are filtered
on that column directly. ``device_commands`` predates provenance snapshots, so
command KPIs scope by the device's classification derived at export time.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from homepot.app.models.AnalyticsModel import (
    ConfigurationHistory,
    DeviceMetrics,
    DeviceStateHistory,
)
from homepot.kpi.models import ExportFilters, KPIResult
from homepot.models import CommandStatus, Device, DeviceCommand, Site, derive_provenance

TERMINAL_STATUSES = {
    CommandStatus.COMPLETED,
    CommandStatus.FAILED,
    CommandStatus.EXPIRED,
}

COVERAGE_TABLES = ("device_metrics", "device_state_history", "configuration_history")

_NAIVE = ""


def _to_utc(dt: Any) -> Optional[datetime]:
    """Normalize a timestamp to an aware UTC datetime.

    Used for ``device_commands`` timestamps, which are stored as
    ``TIMESTAMP WITH TIME ZONE`` and therefore require aware comparison values.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return cast(datetime, dt.replace(tzinfo=timezone.utc))
    return cast(datetime, dt.astimezone(timezone.utc))


def _to_naive_utc(dt: Any) -> Optional[datetime]:
    """Normalize a timestamp to a NAIVE UTC datetime.

    The analytics tables (``device_metrics``, ``device_state_history``,
    ``configuration_history``) store naive UTC timestamps
    (``TIMESTAMP WITHOUT TIME ZONE``). asyncpg rejects aware datetime
    parameters against such columns ("can't subtract offset-naive and
    offset-aware datetimes"), so window comparisons against those tables must
    use naive UTC values. SQLite tolerates either, which is why the tests did
    not catch this on the PostgreSQL path.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return cast(datetime, dt)
    return cast(datetime, dt.astimezone(timezone.utc).replace(tzinfo=None))


def percentile(values: List[float], q: float) -> Optional[float]:
    """Return the nearest-rank percentile ``q`` (0..1) of ``values``.

    Returns ``None`` for an empty list. Uses linear interpolation between the
    two nearest ranks so p50/p95 are well defined for small samples.
    """
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * q
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _health_status(perf: Optional[Dict[str, Any]]) -> Optional[str]:
    """Extract a normalized health status from a performance dict."""
    if isinstance(perf, dict) and isinstance(perf.get("status"), str):
        return cast(str, perf["status"]).lower()
    return None


def _is_improved(
    before: Optional[Dict[str, Any]], after: Optional[Dict[str, Any]]
) -> bool:
    """Whether ``after`` meets the documented post-change health target.

    A change is improved when the after-state reports a healthy status, or,
    when no status is present, when response time did not regress.
    """
    if not isinstance(after, dict):
        return False
    status = _health_status(after)
    if status is not None:
        return status in {"healthy", "ok", "online"}
    before_ms = before.get("response_time_ms") if isinstance(before, dict) else None
    after_ms = after.get("response_time_ms")
    if isinstance(before_ms, (int, float)) and isinstance(after_ms, (int, float)):
        return after_ms <= before_ms
    return False


async def _resolve_devices(
    session: AsyncSession, filters: ExportFilters
) -> tuple[List[int], List[str]]:
    """Resolve site/device/type filters into device PKs and device_id strings."""
    stmt = select(Device)
    if filters.site_id is not None:
        stmt = stmt.join(Site, Device.site_id == Site.id).where(
            Site.site_id == filters.site_id
        )
    if filters.device_id is not None:
        stmt = stmt.where(Device.device_id == filters.device_id)
    if filters.device_type is not None:
        stmt = stmt.where(Device.device_type == filters.device_type)
    devices = (await session.execute(stmt)).scalars().all()
    device_pks = [cast(int, d.id) for d in devices]
    device_id_strings = [cast(str, d.device_id) for d in devices]
    return device_pks, device_id_strings


async def _provenance_device_pks(session: AsyncSession) -> Dict[str, set]:
    """Map each provenance class to the device PKs carrying it today.

    Used to scope command KPIs, which lack a snapshotted provenance column.
    """
    devices = (await session.execute(select(Device))).scalars().all()
    grouped: Dict[str, set] = {"real": set(), "controlled": set(), "simulated": set()}
    for device in devices:
        provenance = derive_provenance(device)
        if provenance is not None:
            grouped[provenance.value].add(device.id)
    return grouped


def _command_scope(
    stmt: Select[tuple[DeviceCommand]],
    filters: ExportFilters,
    pk_ids: List[int],
    provenance_pks: Dict[str, set],
) -> Select[tuple[DeviceCommand]]:
    """Apply window/device/provenance filters to a DeviceCommand query."""
    start = _to_utc(filters.start)
    end = _to_utc(filters.end)
    stmt = stmt.where(
        DeviceCommand.created_at >= start, DeviceCommand.created_at <= end
    )
    if filters.provenance is not None:
        scope_pks = provenance_pks.get(filters.provenance, set())
        if pk_ids:
            scope_pks = scope_pks & set(pk_ids)
        stmt = stmt.where(DeviceCommand.device_id.in_(scope_pks))
    elif pk_ids:
        stmt = stmt.where(DeviceCommand.device_id.in_(pk_ids))
    return stmt


def _config_scope(
    stmt: Select[tuple[ConfigurationHistory]],
    filters: ExportFilters,
    device_id_strings: List[str],
) -> Select[tuple[ConfigurationHistory]]:
    """Apply window/device/provenance filters to a ConfigurationHistory query."""
    start = _to_naive_utc(filters.start)
    end = _to_naive_utc(filters.end)
    stmt = stmt.where(
        ConfigurationHistory.timestamp >= start,
        ConfigurationHistory.timestamp <= end,
        ConfigurationHistory.entity_type == "device",
    )
    if filters.provenance is not None:
        stmt = stmt.where(ConfigurationHistory.provenance == filters.provenance)
    elif device_id_strings:
        stmt = stmt.where(ConfigurationHistory.entity_id.in_(device_id_strings))
    return stmt


async def compute_command_completion_rate(
    session: AsyncSession,
    filters: ExportFilters,
    pk_ids: List[int],
    provenance_pks: Dict[str, set],
) -> KPIResult:
    """MW-01 command completion rate = completed / terminal × 100."""
    stmt = select(DeviceCommand)
    stmt = _command_scope(stmt, filters, pk_ids, provenance_pks)
    commands = (await session.execute(stmt)).scalars().all()

    terminal = [c for c in commands if c.status in TERMINAL_STATUSES]
    completed = [c for c in terminal if c.status == CommandStatus.COMPLETED]
    exclusions = len(commands) - len(terminal)

    value = (len(completed) / len(terminal) * 100) if terminal else None
    return KPIResult(
        kpi_id="MW-01",
        name="Command completion rate",
        formula="completed commands / terminal commands × 100",
        unit="%",
        value=round(value, 2) if value is not None else None,
        numerator=len(completed),
        denominator=len(terminal),
        exclusions=exclusions,
        sample_count=len(terminal),
        provenance=filters.provenance or "all",
    )


async def compute_command_roundtrip(
    session: AsyncSession,
    filters: ExportFilters,
    pk_ids: List[int],
    provenance_pks: Dict[str, set],
) -> List[KPIResult]:
    """MW-02 command round-trip time = executed_at − created_at, by command type."""
    stmt = select(DeviceCommand)
    stmt = _command_scope(stmt, filters, pk_ids, provenance_pks)
    commands = (await session.execute(stmt)).scalars().all()

    latencies: Dict[str, List[float]] = {}
    for cmd in commands:
        if cmd.status not in TERMINAL_STATUSES:
            continue
        created = _to_utc(cmd.created_at)
        executed = _to_utc(cmd.executed_at)
        if created is None or executed is None:
            continue
        latencies.setdefault(cast(str, cmd.command_type) or "unknown", []).append(
            (executed - created).total_seconds()
        )

    results: List[KPIResult] = []
    for command_type, values in sorted(latencies.items()):
        for stat, q in (("p50", 0.5), ("p95", 0.95), ("max", 1.0)):
            val = percentile(values, q)
            results.append(
                KPIResult(
                    kpi_id="MW-02",
                    name="Command round-trip time",
                    formula="terminal status time − queue time, by command type",
                    unit="seconds",
                    value=round(val, 3) if val is not None else None,
                    numerator=len(values),
                    denominator=len(values),
                    exclusions=0,
                    sample_count=len(values),
                    provenance=filters.provenance or "all",
                    group={"command_type": command_type, "statistic": stat},
                )
            )
    return results


async def compute_config_success_rate(
    session: AsyncSession, filters: ExportFilters, device_id_strings: List[str]
) -> KPIResult:
    """MW-03 configuration-change success = successful / attempted × 100."""
    stmt = select(ConfigurationHistory)
    stmt = _config_scope(stmt, filters, device_id_strings)
    rows = (await session.execute(stmt)).scalars().all()

    with_outcome = [r for r in rows if r.was_successful is not None]
    successful = [r for r in with_outcome if r.was_successful is True]

    value = (len(successful) / len(with_outcome) * 100) if with_outcome else None
    return KPIResult(
        kpi_id="MW-03",
        name="Configuration-change success",
        formula="successful changes / attempted changes × 100",
        unit="%",
        value=round(value, 2) if value is not None else None,
        numerator=len(successful),
        denominator=len(with_outcome),
        exclusions=len(rows) - len(with_outcome),
        sample_count=len(with_outcome),
        provenance=filters.provenance or "all",
    )


async def compute_verified_improvement_rate(
    session: AsyncSession, filters: ExportFilters, device_id_strings: List[str]
) -> KPIResult:
    """MW-04 verified improvement rate = improved / verified successful × 100."""
    stmt = select(ConfigurationHistory)
    stmt = _config_scope(stmt, filters, device_id_strings)
    rows = (await session.execute(stmt)).scalars().all()

    successful = [r for r in rows if r.was_successful is True]
    verified = [
        r
        for r in successful
        if r.performance_before is not None and r.performance_after is not None
    ]
    improved = [
        r
        for r in verified
        if _is_improved(
            cast(Optional[Dict[str, Any]], r.performance_before),
            cast(Optional[Dict[str, Any]], r.performance_after),
        )
    ]

    value = (len(improved) / len(verified) * 100) if verified else None
    return KPIResult(
        kpi_id="MW-04",
        name="Verified improvement rate",
        formula=(
            "successful changes meeting the post-change health target / "
            "successful changes with valid before/after windows × 100"
        ),
        unit="%",
        value=round(value, 2) if value is not None else None,
        numerator=len(improved),
        denominator=len(verified),
        exclusions=len(successful) - len(verified),
        sample_count=len(verified),
        provenance=filters.provenance or "all",
    )


async def compute_rollback_effectiveness(
    session: AsyncSession, filters: ExportFilters, device_id_strings: List[str]
) -> KPIResult:
    """MW-05 rollback effectiveness = restoring rollbacks / attempted rollbacks × 100."""
    stmt = select(ConfigurationHistory)
    stmt = _config_scope(stmt, filters, device_id_strings)
    rows = (await session.execute(stmt)).scalars().all()

    attempted = [r for r in rows if r.was_rolled_back is True]
    restored: List[ConfigurationHistory] = []
    for r in attempted:
        if r.rollback_success is True:
            restored.append(r)
        elif r.rollback_success is None and _is_improved(
            cast(Optional[Dict[str, Any]], r.performance_before),
            cast(Optional[Dict[str, Any]], r.rollback_performance),
        ):
            restored.append(r)

    value = (len(restored) / len(attempted) * 100) if attempted else None
    return KPIResult(
        kpi_id="MW-05",
        name="Rollback effectiveness",
        formula=(
            "rollbacks restoring the baseline health target / attempted "
            "rollbacks × 100"
        ),
        unit="%",
        value=round(value, 2) if value is not None else None,
        numerator=len(restored),
        denominator=len(attempted),
        exclusions=0,
        sample_count=len(attempted),
        provenance=filters.provenance or "all",
    )


async def compute_provenance_coverage(
    session: AsyncSession,
    filters: ExportFilters,
    pk_ids: List[int],
    device_id_strings: List[str],
) -> List[KPIResult]:
    """EQ-01 provenance coverage = rows with valid provenance / eligible rows × 100."""
    start = _to_naive_utc(filters.start)
    end = _to_naive_utc(filters.end)
    results: List[KPIResult] = []

    definitions = [
        (
            "device_metrics",
            DeviceMetrics,
            DeviceMetrics.timestamp,
            DeviceMetrics.provenance,
            DeviceMetrics.device_id,
            pk_ids,
        ),
        (
            "device_state_history",
            DeviceStateHistory,
            DeviceStateHistory.timestamp,
            DeviceStateHistory.provenance,
            DeviceStateHistory.device_id,
            pk_ids,
        ),
    ]
    for name, model, window_col, provenance_col, device_col, ids in definitions:
        base = select(func.count()).select_from(model)
        base = base.where(window_col >= start, window_col <= end)
        if ids:
            base = base.where(device_col.in_(ids))
        eligible = (await session.execute(base)).scalar_one()
        valid = (
            await session.execute(base.where(provenance_col.isnot(None)))
        ).scalar_one()
        value = (valid / eligible * 100) if eligible else None
        results.append(
            KPIResult(
                kpi_id="EQ-01",
                name="Provenance coverage",
                formula="rows with valid provenance / eligible rows × 100",
                unit="%",
                value=round(value, 2) if value is not None else None,
                numerator=valid,
                denominator=eligible,
                exclusions=0,
                sample_count=eligible,
                provenance="all",
                group={"table": name},
            )
        )

    config_base = select(func.count()).select_from(ConfigurationHistory)
    config_base = config_base.where(
        ConfigurationHistory.timestamp >= start,
        ConfigurationHistory.timestamp <= end,
        ConfigurationHistory.entity_type == "device",
    )
    if filters.provenance is not None:
        config_base = config_base.where(
            ConfigurationHistory.provenance == filters.provenance
        )
    elif device_id_strings:
        config_base = config_base.where(
            ConfigurationHistory.entity_id.in_(device_id_strings)
        )
    config_eligible = (await session.execute(config_base)).scalar_one()
    config_valid = (
        await session.execute(
            config_base.where(ConfigurationHistory.provenance.isnot(None))
        )
    ).scalar_one()
    value = (config_valid / config_eligible * 100) if config_eligible else None
    results.append(
        KPIResult(
            kpi_id="EQ-01",
            name="Provenance coverage",
            formula="rows with valid provenance / eligible rows × 100",
            unit="%",
            value=round(value, 2) if value is not None else None,
            numerator=config_valid,
            denominator=config_eligible,
            exclusions=0,
            sample_count=config_eligible,
            provenance="all",
            group={"table": "configuration_history"},
        )
    )
    return results


async def compute_metric_network_latency(
    session: AsyncSession, filters: ExportFilters, pk_ids: List[int]
) -> List[KPIResult]:
    """PF-LAT device-reported network latency p50/p95/max from device_metrics."""
    start = _to_naive_utc(filters.start)
    end = _to_naive_utc(filters.end)
    stmt = select(DeviceMetrics).where(
        DeviceMetrics.timestamp >= start,
        DeviceMetrics.timestamp <= end,
        DeviceMetrics.network_latency_ms.isnot(None),
    )
    if filters.provenance is not None:
        stmt = stmt.where(DeviceMetrics.provenance == filters.provenance)
    elif pk_ids:
        stmt = stmt.where(DeviceMetrics.device_id.in_(pk_ids))
    rows = (await session.execute(stmt)).scalars().all()
    values = [cast(float, r.network_latency_ms) for r in rows]

    results: List[KPIResult] = []
    for stat, q in (("p50", 0.5), ("p95", 0.95), ("max", 1.0)):
        val = percentile(values, q)
        results.append(
            KPIResult(
                kpi_id="PF-LAT",
                name="Device-reported network latency",
                formula="network_latency_ms percentiles from device_metrics",
                unit="ms",
                value=round(val, 2) if val is not None else None,
                numerator=len(values),
                denominator=len(values),
                exclusions=0,
                sample_count=len(values),
                provenance=filters.provenance or "all",
                group={"statistic": stat},
            )
        )
    return results
