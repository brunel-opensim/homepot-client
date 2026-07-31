"""Gate E: Lifecycle Integrity Verification.

Validates that the device is in an active lifecycle state, has healthy
credentials, and is in a valid health state. This gate prevents the AI from
making recommendations for devices that are suspended, retired, in error, or
have compromised credentials. Failing Gate E falls back to Mode 5 (lifecycle
halt, non-actionable) -- see ``MODE_LIFECYCLE_HALT`` below.
"""

from __future__ import annotations

from typing import Any, List

from sqlalchemy import select

from .base import (
    CheckResult,
    EvidenceRef,
    Gate,
    GateContext,
    GateResult,
    GateStatus,
    Mode,
)

# ---------------------------------------------------------------------------
# TUNABLE: the ``trust_ceiling`` for MODE_LIFECYCLE_HALT is set to 0.50
# (best-effort-analytics level), meaning the AI can still provide analytic
# summaries but cannot make actionable recommendations when the device's
# lifecycle or credentials are compromised. Adjust this once empirical
# calibration data is available -- see base.py's module-level comment.
# ---------------------------------------------------------------------------

MODE_LIFECYCLE_HALT = Mode(
    id="mode_5",
    label="Mode 5: Lifecycle Halt",
    description=(
        "Device lifecycle state, credentials, or health are invalid. "
        "The AI cannot make actionable recommendations for a device "
        "that is not in an active, healthy state."
    ),
    actionable=False,
    trust_ceiling=0.50,
)


class LifecycleIntegrityGate(Gate):
    """Gate E: validates device lifecycle, credential health, and health state."""

    def __init__(self) -> None:
        """Configure Gate E with its fixed identity and Mode 5 failure fallback."""
        super().__init__(
            gate_id="E",
            name="Lifecycle Integrity",
            failure_mode=MODE_LIFECYCLE_HALT,
        )

    async def evaluate(self, context: GateContext) -> GateResult:
        """Check lifecycle state, health state, and credential health."""
        session = context.session
        if session is None:
            return GateResult(
                gate_id=self.gate_id,
                name=self.name,
                status=GateStatus.FAIL,
                checks=[
                    CheckResult(
                        check_id="E.session",
                        name="Database session available",
                        passed=False,
                        message="No database session supplied to Gate E.",
                    )
                ],
            )

        from homepot.models import Device

        device_int_id = context.device_int_id
        device_id = context.device_id

        stmt = select(Device)
        if device_int_id is not None:
            stmt = stmt.where(Device.id == device_int_id)
        elif device_id is not None:
            stmt = stmt.where(Device.device_id == device_id)
        else:
            return GateResult(
                gate_id=self.gate_id,
                name=self.name,
                status=GateStatus.PASS,
                checks=[
                    CheckResult(
                        check_id="E.device_identity",
                        name="Device identity available",
                        passed=True,
                        message="No device specified — Gate E skipped (device-level check).",
                    )
                ],
            )

        result = await session.execute(stmt)
        device = result.scalar_one_or_none()
        if device is None:
            return GateResult(
                gate_id=self.gate_id,
                name=self.name,
                status=GateStatus.FAIL,
                checks=[
                    CheckResult(
                        check_id="E.device_found",
                        name="Device exists",
                        passed=False,
                        message=(
                            f"Device not found "
                            f"(int_id={device_int_id}, device_id={device_id})."
                        ),
                    )
                ],
            )

        checks: List[CheckResult] = [
            self._check_lifecycle_state(device),
            self._check_health_state(device),
            await self._check_credential_health(session, device),
        ]
        status = GateStatus.PASS if all(c.passed for c in checks) else GateStatus.FAIL
        return GateResult(
            gate_id=self.gate_id, name=self.name, status=status, checks=checks
        )

    def _check_lifecycle_state(self, device: Any) -> CheckResult:
        passed = device.lifecycle_state == "active"
        return CheckResult(
            check_id="E.lifecycle_state",
            name="Lifecycle state is active",
            passed=passed,
            message=(
                f"Device lifecycle state is '{device.lifecycle_state}'."
                if passed
                else (
                    f"Device lifecycle state is '{device.lifecycle_state}' "
                    f"\u2014 expected 'active'."
                )
            ),
            evidence=[
                EvidenceRef(
                    table="devices",
                    field="lifecycle_state",
                    device_id=device.device_id,
                    observed=device.lifecycle_state,
                    threshold="active",
                    query_id="E.lifecycle_state",
                )
            ],
        )

    def _check_health_state(self, device: Any) -> CheckResult:
        passed = device.health_state not in ("error",)
        return CheckResult(
            check_id="E.health_state",
            name="Health state is valid",
            passed=passed,
            message=(
                f"Device health state is '{device.health_state or 'unknown'}'."
                if passed
                else (
                    f"Device health state is '{device.health_state}'"
                    f" \u2014 must not be 'error'."
                )
            ),
            evidence=[
                EvidenceRef(
                    table="devices",
                    field="health_state",
                    device_id=device.device_id,
                    observed=device.health_state,
                    threshold="not error",
                    query_id="E.health_state",
                )
            ],
        )

    async def _check_credential_health(self, session: Any, device: Any) -> CheckResult:
        from homepot.models import DeviceCredential

        stmt = select(DeviceCredential).where(
            DeviceCredential.device_id == device.id,
            DeviceCredential.is_active.is_(True),
        )
        result = await session.execute(stmt)
        credentials = result.scalars().all()

        active = [c for c in credentials if c.revoked_at is None]
        passed = len(active) > 0
        return CheckResult(
            check_id="E.credential_health",
            name="Credential health",
            passed=passed,
            message=(
                f"Device has {len(active)} active credential(s)."
                if passed
                else "No active, non-revoked credentials found for device."
            ),
            evidence=[
                EvidenceRef(
                    table="device_credentials",
                    field="is_active",
                    device_id=device.device_id,
                    observed=len(active),
                    threshold="> 0",
                    query_id="E.credential_health",
                    extra={
                        "total_credentials": len(credentials),
                        "active_count": len(active),
                    },
                )
            ],
        )
