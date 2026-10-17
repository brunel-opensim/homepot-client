"""Pre-execution policy checks for AI action plans (Phase 3).

This is the enforcer between an *approved* plan and the executor. It is
deliberately independent of the LLM: it re-checks, from the database, every
condition the proposal asserted, so an approval cannot smuggle in an
unauthorised or unsafe action.

v1 checks (docs/ai-delegation-plan.md sections 7, 9, 10):

* every step's action is declared in the registry;
* the risk tier is within the allowed set (T1/T2 only in v1);
* every target device exists and is ``active``;
* the device has granted the action's required permission;
* blast radius: a single plan targets at most ``MAX_DEVICES_PER_PLAN`` devices.

A blocked plan is recorded as such (``status='blocked'``) and never executed.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session as SASession

from homepot.app.ai_ops.registry import get_action_spec
from homepot.models import Device, LifecycleState

MAX_DEVICES_PER_PLAN = 5
ALLOWED_RISK_TIERS: Tuple[str, ...] = ("T1", "T2")

# Sentinel so a missing device (``None``) is cached and not re-queried.
_MISSING: Any = object()


@dataclass
class PolicyResult:
    """Outcome of a pre-execution policy evaluation."""

    allowed: bool
    reasons: List[str] = field(default_factory=list)


def _lifecycle_value(device: Device) -> Any:
    """Return the device lifecycle state as a plain value (enum or string)."""
    state = device.lifecycle_state
    return getattr(state, "value", state)


def _permissions(device: Device) -> Dict[str, bool]:
    perms = device.device_permissions
    return perms if isinstance(perms, dict) else {}


def evaluate_plan(
    db: SASession,
    plan: Any,
    *,
    allowed_tiers: Tuple[str, ...] = ALLOWED_RISK_TIERS,
    max_devices: int = MAX_DEVICES_PER_PLAN,
) -> PolicyResult:
    """Evaluate whether ``plan`` may be executed against the live system."""
    reasons: List[str] = []
    steps = list(plan.steps or [])
    if not steps:
        reasons.append("Plan has no steps.")

    devices: Dict[str, Optional[Device]] = {}
    for step in steps:
        spec = get_action_spec(step.action)
        if spec is None:
            reasons.append(f"Unknown action '{step.action}'.")
            continue

        if spec.risk_tier not in allowed_tiers:
            reasons.append(
                f"Action '{step.action}' is risk tier {spec.risk_tier}; "
                f"only {list(allowed_tiers)} may execute in v1."
            )

        device_id = step.target_device_id
        if not device_id:
            reasons.append(f"Step {step.seq} has no target device.")
            continue

        device = devices.get(device_id, _MISSING)
        if device is _MISSING:
            device = db.query(Device).filter(Device.device_id == device_id).first()
            devices[device_id] = device

        if device is None:
            reasons.append(f"Target device '{device_id}' not found.")
            continue

        if _lifecycle_value(device) != LifecycleState.ACTIVE.value:
            reasons.append(
                f"Device '{device_id}' is not active "
                f"(state '{_lifecycle_value(device)}')."
            )

        if spec.required_permission and not _permissions(device).get(
            spec.required_permission, False
        ):
            reasons.append(
                f"Device '{device_id}' has not granted "
                f"'{spec.required_permission}'."
            )

    distinct_devices = {d for d in devices.values() if d is not None}
    if len(distinct_devices) > max_devices:
        reasons.append(
            f"Plan targets {len(distinct_devices)} devices; the v1 blast-radius "
            f"limit is {max_devices}."
        )

    return PolicyResult(allowed=not reasons, reasons=reasons)
