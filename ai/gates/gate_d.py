"""Gate D: Permission and Capability Verification.

Validates that device permissions are properly bounded by device capabilities
and that both are defined and consistent. This gate prevents the AI from
recommending actions that the device is not permitted or capable of performing.
Failing Gate D falls back to Mode 4 (permission gap, non-actionable) --
see ``MODE_PERMISSION_GAP`` below.
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
# TUNABLE: the ``trust_ceiling`` for MODE_PERMISSION_GAP is set to 0.75
# (cautionary-summaries level), same as Gate C's MODE_CAUTIONARY. Adjust
# this once empirical calibration data is available -- see base.py's
# module-level comment for the calibration methodology.
# ---------------------------------------------------------------------------

MODE_PERMISSION_GAP = Mode(
    id="mode_4",
    label="Mode 4: Permission Gap",
    description=(
        "Device permissions and capabilities are inconsistent or undefined. "
        "The AI cannot safely recommend device actions."
    ),
    actionable=False,
    trust_ceiling=0.75,
)


class PermissionCapabilityGate(Gate):
    """Gate D: validates device permissions are bounded by capabilities."""

    def __init__(self) -> None:
        """Configure Gate D with its fixed identity and Mode 4 failure fallback."""
        super().__init__(
            gate_id="D",
            name="Permission and Capability",
            failure_mode=MODE_PERMISSION_GAP,
        )

    async def evaluate(self, context: GateContext) -> GateResult:
        """Check capabilities defined, permissions defined, permissions within capabilities."""
        session = context.session
        if session is None:
            return GateResult(
                gate_id=self.gate_id,
                name=self.name,
                status=GateStatus.FAIL,
                checks=[
                    CheckResult(
                        check_id="D.session",
                        name="Database session available",
                        passed=False,
                        message="No database session supplied to Gate D.",
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
                status=GateStatus.FAIL,
                checks=[
                    CheckResult(
                        check_id="D.device_identity",
                        name="Device identity available",
                        passed=False,
                        message="Neither device_int_id nor device_id supplied to Gate D.",
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
                        check_id="D.device_found",
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
            self._check_capabilities_defined(device),
            self._check_permissions_defined(device),
            self._check_permissions_within_capabilities(device),
        ]
        status = GateStatus.PASS if all(c.passed for c in checks) else GateStatus.FAIL
        return GateResult(
            gate_id=self.gate_id, name=self.name, status=status, checks=checks
        )

    def _check_capabilities_defined(self, device: Any) -> CheckResult:
        caps = device.capabilities
        passed = caps is not None and isinstance(caps, dict) and len(caps) > 0
        return CheckResult(
            check_id="D.capabilities_defined",
            name="Capabilities defined",
            passed=passed,
            message=(
                "Device capabilities are defined."
                if passed
                else "Device capabilities are not defined or empty."
            ),
            evidence=[
                EvidenceRef(
                    table="devices",
                    field="capabilities",
                    device_id=device.device_id,
                    query_id="D.capabilities_defined",
                    extra={
                        "capabilities": caps if caps else {},
                        "is_null": caps is None,
                    },
                )
            ],
        )

    def _check_permissions_defined(self, device: Any) -> CheckResult:
        perms = device.device_permissions
        passed = perms is not None and isinstance(perms, dict) and len(perms) > 0
        return CheckResult(
            check_id="D.permissions_defined",
            name="Permissions defined",
            passed=passed,
            message=(
                "Device permissions are defined."
                if passed
                else "Device permissions are not defined or empty."
            ),
            evidence=[
                EvidenceRef(
                    table="devices",
                    field="device_permissions",
                    device_id=device.device_id,
                    query_id="D.permissions_defined",
                    extra={
                        "permissions": perms if perms else {},
                        "is_null": perms is None,
                    },
                )
            ],
        )

    def _check_permissions_within_capabilities(self, device: Any) -> CheckResult:
        caps = device.capabilities or {}
        perms = device.device_permissions or {}
        if not caps or not perms:
            return CheckResult(
                check_id="D.permissions_within_capabilities",
                name="Permissions within capabilities",
                passed=False,
                message="Cannot verify: capabilities or permissions are empty.",
                evidence=[
                    EvidenceRef(
                        table="devices",
                        field="device_permissions",
                        device_id=device.device_id,
                        query_id="D.permissions_within_capabilities",
                        extra={"capabilities": caps, "permissions": perms},
                    )
                ],
            )

        violations: List[str] = []
        for key, requested in perms.items():
            if requested and not caps.get(key, False):
                violations.append(key)

        passed = not violations
        return CheckResult(
            check_id="D.permissions_within_capabilities",
            name="Permissions within capabilities",
            passed=passed,
            message=(
                "All permissions are within device capabilities."
                if passed
                else f"Permissions exceed capabilities for: {violations}"
            ),
            evidence=[
                EvidenceRef(
                    table="devices",
                    device_id=device.device_id,
                    query_id="D.permissions_within_capabilities",
                    extra={
                        "violations": violations,
                        "capabilities": caps,
                        "permissions": perms,
                    },
                )
            ],
        )
