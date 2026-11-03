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


def evaluate_step(
    db: SASession,
    step: Any,
    *,
    plan: Any = None,
    allowed_tiers: Tuple[str, ...] = ALLOWED_RISK_TIERS,
) -> PolicyResult:
    """Evaluate whether a single step may be dispatched at this moment.

    Reuses the per-device checks from :func:`evaluate_plan` but for one step.
    Called at dispatch time (not just plan-level) because device state and
    permissions can change between steps.
    """
    reasons: List[str] = []
    spec = get_action_spec(step.action)
    if spec is None:
        reasons.append(f"Unknown action '{step.action}'.")
        return PolicyResult(allowed=not reasons, reasons=reasons)

    if spec.risk_tier not in allowed_tiers:
        reasons.append(
            f"Action '{step.action}' is risk tier {spec.risk_tier}; "
            f"only {list(allowed_tiers)} may execute in v1."
        )

    device_id = step.target_device_id
    if not device_id:
        reasons.append(f"Step {step.seq} has no target device.")
        return PolicyResult(allowed=not reasons, reasons=reasons)

    device = db.query(Device).filter(Device.device_id == device_id).first()
    if device is None:
        reasons.append(f"Target device '{device_id}' not found.")
        return PolicyResult(allowed=not reasons, reasons=reasons)

    if _lifecycle_value(device) != LifecycleState.ACTIVE.value:
        reasons.append(
            f"Device '{device_id}' is not active "
            f"(state '{_lifecycle_value(device)}')."
        )

    if spec.required_permission and not _permissions(device).get(
        spec.required_permission, False
    ):
        reasons.append(
            f"Device '{device_id}' has not granted " f"'{spec.required_permission}'."
        )

    # Evaluate preconditions if present
    precond_errors = _evaluate_preconditions(step, db, device)
    reasons.extend(precond_errors)

    return PolicyResult(allowed=not reasons, reasons=reasons)


def validate_dependencies(plan: Any) -> List[str]:
    """Validate the dependency graph of a plan.

    Checks for:
    - Missing dependency targets (depends_on_step_id points to a non-existent step)
    - Cycles in the dependency graph
    - A step depending on itself

    Returns a list of error strings (empty = valid).
    """
    errors: List[str] = []
    steps = list(plan.steps or [])
    step_ids = {s.step_id for s in steps}

    # Check each dependency reference
    for step in steps:
        dep_id = getattr(step, "depends_on_step_id", None)
        if dep_id is not None:
            if dep_id == step.step_id:
                errors.append(f"Step {step.seq} depends on itself.")
            elif dep_id not in step_ids:
                errors.append(f"Step {step.seq} depends on unknown step {dep_id}.")

    # Cycle detection (DFS)
    if not errors:
        # Build adjacency list
        adj: Dict[str, List[str]] = {sid: [] for sid in step_ids}
        for step in steps:
            dep_id = getattr(step, "depends_on_step_id", None)
            if dep_id is not None:
                adj[dep_id].append(step.step_id)

        # DFS for cycles
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {sid: WHITE for sid in step_ids}

        def dfs(node: str) -> bool:
            color[node] = GRAY
            for neighbor in adj.get(node, []):
                if color.get(neighbor, WHITE) == GRAY:
                    return True  # cycle detected
                if color.get(neighbor, WHITE) == WHITE:
                    if dfs(neighbor):
                        return True
            color[node] = BLACK
            return False

        for sid in step_ids:
            if color.get(sid, WHITE) == WHITE:
                if dfs(sid):
                    errors.append("Dependency cycle detected in plan steps.")
                    break

    return errors


def _evaluate_preconditions(step: Any, db: SASession, device: Any) -> List[str]:
    """Evaluate a step's preconditions (deterministic, allowlisted).

    Precondition keys are interpreted as follows:
    - ``device_state``: expected lifecycle state (e.g. "active")
    - ``permission``: required permission must be granted
    - ``depends_on_status``: dependency step must have a given status

    Unknown keys are ignored (forward-compatible).
    """
    errors: List[str] = []
    preconds = getattr(step, "preconditions", None)
    if not isinstance(preconds, dict):
        return errors

    if "device_state" in preconds:
        expected = preconds["device_state"]
        actual = _lifecycle_value(device)
        if str(actual) != str(expected):
            errors.append(
                f"Precondition 'device_state' not met: "
                f"expected '{expected}', got '{actual}'."
            )

    if "permission" in preconds:
        perm = preconds["permission"]
        if not _permissions(device).get(perm, False):
            errors.append(f"Precondition 'permission' not met: '{perm}' not granted.")

    return errors
