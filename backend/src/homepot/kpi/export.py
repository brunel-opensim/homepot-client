"""Assemble and render versioned KPI export bundles."""

import csv
from datetime import datetime, timezone
import io
import json
from typing import Any, Dict, List, Optional, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from homepot.app.models.AnalyticsModel import (
    ConfigurationHistory,
    DeviceMetrics,
    DeviceStateHistory,
)
from homepot.kpi.calculator import (
    _provenance_device_pks,
    _resolve_devices,
    compute_command_completion_rate,
    compute_command_roundtrip,
    compute_config_success_rate,
    compute_metric_network_latency,
    compute_provenance_coverage,
    compute_rollback_effectiveness,
    compute_verified_improvement_rate,
)
from homepot.kpi.manifest import build_manifest
from homepot.kpi.models import ExportFilters, KPIExportBundle, KPIResult, RawTable
from homepot.models import CommandStatus, DeviceCommand

TERMINAL_STATUSES = {
    CommandStatus.COMPLETED,
    CommandStatus.FAILED,
    CommandStatus.EXPIRED,
}


def _iso(dt: Any) -> Optional[str]:
    return cast(str, dt.isoformat()) if dt is not None else None


def _to_utc(dt: Any) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return cast(datetime, dt.replace(tzinfo=timezone.utc))
    return cast(datetime, dt.astimezone(timezone.utc))


def _to_naive_utc(dt: Any) -> Optional[datetime]:
    """Normalize a timestamp to a NAIVE UTC datetime for analytics tables.

    See ``homepot.kpi.calculator._to_naive_utc``: the analytics tables store
    naive ``TIMESTAMP WITHOUT TIME ZONE`` values, so asyncpg requires naive
    comparison parameters.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return cast(datetime, dt)
    return cast(datetime, dt.astimezone(timezone.utc).replace(tzinfo=None))


async def _extract_raw(
    session: AsyncSession,
    filters: ExportFilters,
    pk_ids: List[int],
    device_id_strings: List[str],
    provenance_pks: Dict[str, set],
) -> List[RawTable]:
    """Extract in-window raw evidence rows for the export bundle."""
    start = _to_naive_utc(filters.start)
    end = _to_naive_utc(filters.end)
    command_start = _to_utc(filters.start)
    command_end = _to_utc(filters.end)
    raw: List[RawTable] = []

    metrics_stmt = select(DeviceMetrics).where(
        DeviceMetrics.timestamp >= start, DeviceMetrics.timestamp <= end
    )
    if filters.provenance is not None:
        metrics_stmt = metrics_stmt.where(
            DeviceMetrics.provenance == filters.provenance
        )
    elif pk_ids:
        metrics_stmt = metrics_stmt.where(DeviceMetrics.device_id.in_(pk_ids))
    metric_rows = (await session.execute(metrics_stmt)).scalars().all()
    raw.append(
        RawTable(
            table="device_metrics",
            columns=[
                "timestamp",
                "device_id",
                "cpu_percent",
                "memory_percent",
                "network_latency_ms",
                "provenance",
            ],
            rows=[
                [
                    _iso(r.timestamp),
                    r.device_id,
                    r.cpu_percent,
                    r.memory_percent,
                    r.network_latency_ms,
                    r.provenance,
                ]
                for r in metric_rows
            ],
        )
    )

    state_stmt = select(DeviceStateHistory).where(
        DeviceStateHistory.timestamp >= start, DeviceStateHistory.timestamp <= end
    )
    if filters.provenance is not None:
        state_stmt = state_stmt.where(
            DeviceStateHistory.provenance == filters.provenance
        )
    elif pk_ids:
        state_stmt = state_stmt.where(DeviceStateHistory.device_id.in_(pk_ids))
    state_rows = (await session.execute(state_stmt)).scalars().all()
    raw.append(
        RawTable(
            table="device_state_history",
            columns=[
                "timestamp",
                "device_id",
                "previous_state",
                "new_state",
                "provenance",
            ],
            rows=[
                [
                    _iso(r.timestamp),
                    r.device_id,
                    r.previous_state,
                    r.new_state,
                    r.provenance,
                ]
                for r in state_rows
            ],
        )
    )

    config_stmt = select(ConfigurationHistory).where(
        ConfigurationHistory.timestamp >= start,
        ConfigurationHistory.timestamp <= end,
        ConfigurationHistory.entity_type == "device",
    )
    if filters.provenance is not None:
        config_stmt = config_stmt.where(
            ConfigurationHistory.provenance == filters.provenance
        )
    elif device_id_strings:
        config_stmt = config_stmt.where(
            ConfigurationHistory.entity_id.in_(device_id_strings)
        )
    config_rows = (await session.execute(config_stmt)).scalars().all()
    raw.append(
        RawTable(
            table="configuration_history",
            columns=[
                "timestamp",
                "entity_id",
                "parameter_name",
                "new_value",
                "was_successful",
                "was_rolled_back",
                "rollback_success",
                "provenance",
            ],
            rows=[
                [
                    _iso(r.timestamp),
                    r.entity_id,
                    r.parameter_name,
                    r.new_value,
                    r.was_successful,
                    r.was_rolled_back,
                    r.rollback_success,
                    r.provenance,
                ]
                for r in config_rows
            ],
        )
    )

    pk_to_provenance: Dict[int, Optional[str]] = {
        device_id: provenance
        for provenance, pks in provenance_pks.items()
        for device_id in pks
    }
    command_stmt = select(DeviceCommand).where(
        DeviceCommand.created_at >= command_start,
        DeviceCommand.created_at <= command_end,
    )
    if filters.provenance is not None:
        scope_pks = provenance_pks.get(filters.provenance, set())
        if pk_ids:
            scope_pks = scope_pks & set(pk_ids)
        command_stmt = command_stmt.where(DeviceCommand.device_id.in_(scope_pks))
    elif pk_ids:
        command_stmt = command_stmt.where(DeviceCommand.device_id.in_(pk_ids))
    command_rows = (await session.execute(command_stmt)).scalars().all()
    raw.append(
        RawTable(
            table="device_commands",
            columns=[
                "command_id",
                "device_id",
                "command_type",
                "status",
                "created_at",
                "sent_at",
                "executed_at",
                "provenance",
            ],
            rows=[
                [
                    r.command_id,
                    r.device_id,
                    r.command_type,
                    r.status,
                    _iso(r.created_at),
                    _iso(r.sent_at),
                    _iso(r.executed_at),
                    pk_to_provenance.get(cast(int, r.device_id)),
                ]
                for r in command_rows
            ],
        )
    )
    return raw


async def compute_kpi_bundle(
    session: AsyncSession, filters: ExportFilters
) -> KPIExportBundle:
    """Compute every in-scope KPI and assemble a versioned export bundle."""
    pk_ids, device_id_strings = await _resolve_devices(session, filters)
    provenance_pks = await _provenance_device_pks(session)

    scopes = (
        [filters.provenance]
        if filters.provenance is not None
        else ["all", "real", "controlled", "simulated"]
    )
    kpis: List[KPIResult] = []
    for scope in scopes:
        scope_filters = filters.model_copy(
            update={"provenance": None if scope == "all" else scope}
        )
        kpis.append(
            await compute_command_completion_rate(
                session, scope_filters, pk_ids, provenance_pks
            )
        )
        kpis.extend(
            await compute_command_roundtrip(
                session, scope_filters, pk_ids, provenance_pks
            )
        )
        kpis.append(
            await compute_config_success_rate(session, scope_filters, device_id_strings)
        )
        kpis.append(
            await compute_verified_improvement_rate(
                session, scope_filters, device_id_strings
            )
        )
        kpis.append(
            await compute_rollback_effectiveness(
                session, scope_filters, device_id_strings
            )
        )
        kpis.extend(
            await compute_metric_network_latency(session, scope_filters, pk_ids)
        )
    kpis.extend(
        await compute_provenance_coverage(session, filters, pk_ids, device_id_strings)
    )

    raw = await _extract_raw(
        session, filters, pk_ids, device_id_strings, provenance_pks
    )
    manifest = build_manifest(filters, scopes)
    return KPIExportBundle(manifest=manifest, kpis=kpis, raw=raw)


def render_csv_summary(bundle: KPIExportBundle) -> str:
    """Render the machine-readable KPI summary as CSV.

    The manifest is emitted as ``#`` comment rows so the file is
    self-describing for a reviewer.
    """
    buffer = io.StringIO()
    buffer.write(f"# manifest: {json.dumps(bundle.manifest)}\n\n")
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "kpi_id",
            "name",
            "formula",
            "unit",
            "value",
            "numerator",
            "denominator",
            "exclusions",
            "sample_count",
            "provenance",
            "group",
        ]
    )
    for kpi in bundle.kpis:
        writer.writerow(
            [
                kpi.kpi_id,
                kpi.name,
                kpi.formula,
                kpi.unit,
                kpi.value if kpi.value is not None else "",
                kpi.numerator,
                kpi.denominator,
                kpi.exclusions,
                kpi.sample_count,
                kpi.provenance,
                json.dumps(kpi.group) if kpi.group else "",
            ]
        )
    return buffer.getvalue()


def bundle_to_dict(bundle: KPIExportBundle) -> Dict[str, Any]:
    """Return a JSON-serializable representation of the bundle."""
    return bundle.model_dump(mode="json")
