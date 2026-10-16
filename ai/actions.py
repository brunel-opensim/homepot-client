"""Action registry for AI-proposed device operations (Phase 1).

This module is the single place that declares which device-management
capabilities the AI is allowed to *propose*, and how risky each one is. It is
deliberately inert: **nothing here executes anything**. Phase 1 is
proposal-only — the agent records a structured proposal, the API persists it,
and a technician decides in a later phase.

The registry is the enforcer's allowlist: an action the model invents that is
not declared here is rejected before it can be surfaced, so a non-deterministic
plan cannot smuggle in an unknown capability (see docs/ai-delegation-plan.md,
"Risks" and §9).

Design notes
------------
* ``command_type`` mirrors the value that must exist in
  ``homepot.agent.utils.command_poller.COMMAND_TYPES``; the executor (Phase 3)
  will reuse that exact path rather than inventing a new one.
* ``required_permission`` mirrors ``REQUIRED_PERMISSION`` for the command type.
* Risk tiers: T1 read-only, T2 reversible, T3 disruptive, T4 destructive.
  v1 deliberately declares only **T2** actions.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ActionSpec:
    """Declared capability the AI is allowed to *propose* (never execute)."""

    name: str
    command_type: str
    risk_tier: str
    reversible: bool
    required_permission: Optional[str]
    min_role: str
    description: str
    required_params: Tuple[str, ...] = ()


# The single source of truth for what the AI may propose. Keep this small and
# explicit; every entry is a promise about risk, reversibility and permission.
ACTION_REGISTRY: Dict[str, ActionSpec] = {
    "update_config": ActionSpec(
        name="update_config",
        command_type="update_config",
        risk_tier="T2",
        reversible=True,
        required_permission="root_access",
        min_role="operator",
        description=(
            "Apply a configuration change to a device. Reversible via snapshot; "
            "requires the owner's root_access grant."
        ),
        required_params=("config",),
    ),
    "restart": ActionSpec(
        name="restart",
        command_type="restart",
        risk_tier="T2",
        reversible=True,
        required_permission="root_access",
        min_role="operator",
        description=(
            "Restart the device or host. Recovers to the prior running state; "
            "requires the owner's root_access grant."
        ),
        required_params=(),
    ),
}


def get_action_spec(action: str) -> Optional[ActionSpec]:
    """Return the declared spec for ``action``, or ``None`` if it is not allowed."""
    return ACTION_REGISTRY.get(action)


def validate_proposal(
    action: str,
    target_device_id: Optional[str],
    params: Optional[Dict[str, Any]],
) -> Tuple[Optional[ActionSpec], Optional[str]]:
    """Validate a model-produced proposal against the registry.

    Returns ``(spec, None)`` when the proposal is well-formed, or
    ``(None, reason)`` explaining why it was rejected. This is the deterministic
    gate that stops the model inventing capabilities or omitting required data.
    """
    spec = ACTION_REGISTRY.get(action)
    if spec is None:
        allowed = ", ".join(sorted(ACTION_REGISTRY))
        return None, f"Unknown action '{action}'. Allowed actions: {allowed}."

    if not target_device_id or not str(target_device_id).strip():
        return None, f"Action '{action}' requires a target_device_id."

    provided = params or {}
    missing = [key for key in spec.required_params if key not in provided]
    if missing:
        return None, (
            f"Action '{action}' is missing required parameter(s): "
            f"{', '.join(missing)}."
        )

    return spec, None


@dataclass
class ActionProposal:
    """A single validated, not-yet-executed action proposed by the AI.

    This is an in-memory value object: the agent loop collects these for one
    run and the API persists them as an :class:`AIActionPlan` + steps.
    """

    action: str
    target_device_id: Optional[str]
    params: Dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    risk_tier: str = "T2"
    reversible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for the API response / persisted evidence."""
        return {
            "action": self.action,
            "target_device_id": self.target_device_id,
            "params": self.params,
            "rationale": self.rationale,
            "risk_tier": self.risk_tier,
            "reversible": self.reversible,
        }


_RISK_ORDER = {"T1": 1, "T2": 2, "T3": 3, "T4": 4}


def max_risk_tier(proposals: List[ActionProposal]) -> Optional[str]:
    """Return the highest risk tier across proposals (the plan's effective tier)."""
    tiers = [p.risk_tier for p in proposals if p.risk_tier in _RISK_ORDER]
    if not tiers:
        return None
    return max(tiers, key=lambda tier: _RISK_ORDER[tier])


def all_reversible(proposals: List[ActionProposal]) -> bool:
    """Whether every proposed step can be rolled back (empty plan => False)."""
    return bool(proposals) and all(bool(p.reversible) for p in proposals)
