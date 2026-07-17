"""Gate A: Infrastructure and Contract Verification (paper Sec. 4.1).

Validates that the data-producing interfaces are stable and schema-conformant:
the ORM/Pydantic-mapped columns for core telemetry tables actually exist and
are queryable against the live database, and that those tables are queryable
at all (DB readiness). Failing Gate A means we cannot even trust the shape of
incoming data, so the envelope falls back to Mode 1 (status-only, no AI
actions) -- see ``base.MODE_STATUS_ONLY``.
"""

from __future__ import annotations

from typing import Any, List

from sqlalchemy import func, select

from .base import (
    MODE_STATUS_ONLY,
    CheckResult,
    EvidenceRef,
    Gate,
    GateContext,
    GateResult,
    GateStatus,
)


class ContractInfrastructureGate(Gate):
    """Gate A: API + schema conformance and DB readiness (Fig. 2)."""

    def __init__(self) -> None:
        """Configure Gate A with its fixed identity and Mode 1 failure fallback."""
        super().__init__(
            gate_id="A",
            name="Contract and Infrastructure",
            failure_mode=MODE_STATUS_ONLY,
        )

    async def evaluate(self, context: GateContext) -> GateResult:
        """Verify schema conformance and DB readiness for core telemetry tables."""
        session = context.session
        if session is None:
            return GateResult(
                gate_id=self.gate_id,
                name=self.name,
                status=GateStatus.FAIL,
                checks=[
                    CheckResult(
                        check_id="A.session",
                        name="Database session available",
                        passed=False,
                        message="No database session supplied to Gate A.",
                    )
                ],
            )

        checks = [
            await self._check_schema_conformance(session),
            await self._check_db_readiness(session),
        ]
        status = GateStatus.PASS if all(c.passed for c in checks) else GateStatus.FAIL
        return GateResult(
            gate_id=self.gate_id, name=self.name, status=status, checks=checks
        )

    async def _check_schema_conformance(self, session: Any) -> CheckResult:
        """Confirm the ORM-mapped columns our contracts rely on exist in the live DB.

        Uses a real SELECT of each mapped column (rather than dialect-specific
        information_schema introspection) so this works identically against
        SQLite (tests) and PostgreSQL/TimescaleDB (production).
        """
        from homepot.app.models.AnalyticsModel import DeviceMetrics
        from homepot.models import HealthCheck

        probes = {
            "device_metrics": select(
                DeviceMetrics.id,
                DeviceMetrics.timestamp,
                DeviceMetrics.device_id,
                DeviceMetrics.cpu_percent,
                DeviceMetrics.memory_percent,
                DeviceMetrics.disk_percent,
                DeviceMetrics.network_latency_ms,
            ).limit(1),
            "health_checks": select(
                HealthCheck.id,
                HealthCheck.timestamp,
                HealthCheck.device_id,
                HealthCheck.is_healthy,
            ).limit(1),
        }

        failures: List[str] = []
        for table, stmt in probes.items():
            try:
                await session.execute(stmt)
            except Exception as exc:
                failures.append(f"{table}: {exc}")

        if failures:
            return CheckResult(
                check_id="A.api_schema_conformance",
                name="API + Schema Conformance",
                passed=False,
                message=f"Schema mismatch detected: {'; '.join(failures)}",
                evidence=[
                    EvidenceRef(
                        table=failure.split(":", 1)[0],
                        query_id="A.api_schema_conformance",
                        extra={"error": failure},
                    )
                    for failure in failures
                ],
            )

        return CheckResult(
            check_id="A.api_schema_conformance",
            name="API + Schema Conformance",
            passed=True,
            message="device_metrics and health_checks columns match the ORM/Pydantic contract.",
        )

    async def _check_db_readiness(self, session: Any) -> CheckResult:
        """Confirm core tables are queryable and note TimescaleDB hypertable status."""
        from homepot.app.models.AnalyticsModel import DeviceMetrics
        from homepot.models import HealthCheck

        try:
            dm_count = (
                await session.execute(select(func.count()).select_from(DeviceMetrics))
            ).scalar()
            hc_count = (
                await session.execute(select(func.count()).select_from(HealthCheck))
            ).scalar()
        except Exception as exc:
            return CheckResult(
                check_id="A.db_readiness",
                name="DB Readiness (tables + timestamps)",
                passed=False,
                message=f"Core tables not queryable: {exc}",
            )

        evidence = [
            EvidenceRef(
                table="device_metrics",
                extra={"row_count": dm_count},
                query_id="A.db_readiness",
            ),
            EvidenceRef(
                table="health_checks",
                extra={"row_count": hc_count},
                query_id="A.db_readiness",
            ),
        ]

        # TimescaleDB hypertable status is informational only -- HOMEPOT is
        # designed to fall back gracefully to standard PostgreSQL/SQLite.
        try:
            from homepot.timescale import TimescaleDBManager

            ts_manager = TimescaleDBManager(session)
            ts_available = await ts_manager.is_timescaledb_available()
            evidence.append(
                EvidenceRef(
                    table="health_checks",
                    extra={"timescaledb_available": ts_available},
                    query_id="A.db_readiness",
                )
            )
        except Exception:
            pass

        return CheckResult(
            check_id="A.db_readiness",
            name="DB Readiness (tables + timestamps)",
            passed=True,
            message=(
                f"device_metrics ({dm_count} rows) and health_checks "
                f"({hc_count} rows) are queryable."
            ),
            evidence=evidence,
        )
