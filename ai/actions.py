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
    # --- T1: Read-only (no state mutation) ---
    "health_check": ActionSpec(
        name="health_check",
        command_type="health_check",
        risk_tier="T1",
        reversible=True,
        required_permission="command_execution",
        min_role="viewer",
        description=(
            "Run a health check on a device (CPU, memory, disk, network). "
            "Read-only; no state change. Can be used as a verification step."
        ),
        required_params=(),
    ),
    "list_processes": ActionSpec(
        name="list_processes",
        command_type="list_processes",
        risk_tier="T1",
        reversible=True,
        required_permission="process_monitoring",
        min_role="viewer",
        description=("List running processes on a device. Read-only; no state change."),
        required_params=(),
    ),
    "scan_filesystem": ActionSpec(
        name="scan_filesystem",
        command_type="scan_filesystem",
        risk_tier="T1",
        reversible=True,
        required_permission="root_access",
        min_role="operator",
        description=("Scan the filesystem of a device. Read-only; no state change."),
        required_params=(),
    ),
    # --- T2: Reversible ---
    "update_config": ActionSpec(
        name="update_config",
        command_type="update_config",
        risk_tier="T2",
        reversible=True,
        required_permission="root_access",
        min_role="operator",
        description=(
            "Apply a configuration change to a device. The 'config' param is a "
            "dict of settings to apply, e.g. config with keys brightness, "
            "volume, log_level, hostname. Common keys: volume, brightness, "
            "log_level, hostname. Reversible via snapshot; requires the "
            "owner's root_access grant."
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
    "rollback_config": ActionSpec(
        name="rollback_config",
        command_type="update_config",
        risk_tier="T2",
        reversible=True,
        required_permission="root_access",
        min_role="operator",
        description=(
            "Roll back a previous configuration change using the snapshotted "
            "previous values. Reversible; requires root_access."
        ),
        required_params=("config",),
    ),
    # --- T3: Disruptive ---
    "restart_agent": ActionSpec(
        name="restart_agent",
        command_type="restart_agent",
        risk_tier="T3",
        reversible=False,
        required_permission="root_access",
        min_role="operator",
        description=(
            "Restart the on-device agent process. The agent exits and its "
            "supervisor respawns it, briefly interrupting heartbeat/telemetry. "
            "Useful for recovering an online-but-misbehaving agent. Requires "
            "root_access."
        ),
        required_params=(),
    ),
    "restart_service": ActionSpec(
        name="restart_service",
        command_type="restart_service",
        risk_tier="T3",
        reversible=False,
        required_permission="root_access",
        min_role="operator",
        description=(
            "Restart a named OS service on a device (Windows service or "
            "systemd unit). Disruptive; may cause brief service interruption. "
            "Requires root_access."
        ),
        required_params=("service_name",),
    ),
    "update_app": ActionSpec(
        name="update_app",
        command_type="update_app",
        risk_tier="T3",
        reversible=False,
        required_permission="root_access",
        min_role="operator",
        description=(
            "Update the HOMEPOT User App on a device to the latest published "
            "release. The app checks the server-hosted feed, downloads, and "
            "restarts to install in one action. Briefly interrupts telemetry "
            "during the restart. Requires root_access."
        ),
        required_params=(),
    ),
    # --- Additional management commands (compose command templates) ---
    "shutdown": ActionSpec(
        name="shutdown",
        command_type="shutdown",
        risk_tier="T3",
        reversible=False,
        required_permission="root_access",
        min_role="operator",
        description="Shut down the device host. Disruptive and not reversible.",
        required_params=(),
    ),
    "start_program": ActionSpec(
        name="start_program",
        command_type="start_program",
        risk_tier="T2",
        reversible=True,
        required_permission="root_access",
        min_role="operator",
        description="Start a program. Use 'path' (executable path or name on PATH) and optional 'args'.",
        required_params=("path",),
    ),
    "stop_program": ActionSpec(
        name="stop_program",
        command_type="stop_program",
        risk_tier="T2",
        reversible=True,
        required_permission="root_access",
        min_role="operator",
        description=(
            "Stop a running process. Use 'name' (process name) or 'pid'. "
            "Set 'force' to terminate immediately."
        ),
        required_params=("name",),
    ),
    "install_program": ActionSpec(
        name="install_program",
        command_type="install_program",
        risk_tier="T2",
        reversible=True,
        required_permission="root_access",
        min_role="operator",
        description=(
            "Install a program via winget. Use 'package' (winget package ID). "
            "Reversible via uninstall."
        ),
        required_params=("package",),
    ),
    "uninstall_program": ActionSpec(
        name="uninstall_program",
        command_type="uninstall_program",
        risk_tier="T2",
        reversible=True,
        required_permission="root_access",
        min_role="operator",
        description="Uninstall a program via winget. Use 'package' (winget package ID).",
        required_params=("package",),
    ),
    "update_program": ActionSpec(
        name="update_program",
        command_type="update_program",
        risk_tier="T2",
        reversible=True,
        required_permission="root_access",
        min_role="operator",
        description="Update a single installed program. Use 'package' (winget package ID).",
        required_params=("package",),
    ),
    "upgrade_all_programs": ActionSpec(
        name="upgrade_all_programs",
        command_type="upgrade_all_programs",
        risk_tier="T3",
        reversible=False,
        required_permission="root_access",
        min_role="operator",
        description="Upgrade all installed programs. Disruptive; affects the whole device.",
        required_params=(),
    ),
    "run_command": ActionSpec(
        name="run_command",
        command_type="run_command",
        risk_tier="T3",
        reversible=False,
        required_permission="root_access",
        min_role="operator",
        description="Run an elevated (root) command on the device. Disruptive; not reversible.",
        required_params=("command",),
    ),
    "run_command_unprivileged": ActionSpec(
        name="run_command_unprivileged",
        command_type="run_command_unprivileged",
        risk_tier="T2",
        reversible=True,
        required_permission="command_execution",
        min_role="operator",
        description="Run a command as the unprivileged user on the device.",
        required_params=("command",),
    ),
    "run_script": ActionSpec(
        name="run_script",
        command_type="run_script",
        risk_tier="T3",
        reversible=False,
        required_permission="root_access",
        min_role="operator",
        description="Run an elevated script on the device. Disruptive; not reversible.",
        required_params=("command",),
    ),
    "list_installed_programs": ActionSpec(
        name="list_installed_programs",
        command_type="list_installed_programs",
        risk_tier="T1",
        reversible=True,
        required_permission="root_access",
        min_role="viewer",
        description="List installed programs on the device. Read-only.",
        required_params=(),
    ),
    "list_connections": ActionSpec(
        name="list_connections",
        command_type="list_connections",
        risk_tier="T1",
        reversible=True,
        required_permission="command_execution",
        min_role="viewer",
        description="List active network connections on the device. Read-only.",
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


# Map each risk tier to a short label for tool docstrings / diagnostics.
_RISK_LABELS = {
    "T1": "read-only",
    "T2": "reversible",
    "T3": "disruptive",
    "T4": "destructive",
}


def allowed_actions_summary() -> str:
    """Render the registered actions grouped by risk tier.

    This is the single source of truth for the human-readable action list used
    by the proposal tool's docstring, so it can never drift from
    :data:`ACTION_REGISTRY`. Each line is indented to fit inside the tool's
    ``Args`` block.
    """
    grouped: Dict[str, List[str]] = {}
    for name, spec in sorted(ACTION_REGISTRY.items()):
        grouped.setdefault(spec.risk_tier, []).append(name)

    lines: List[str] = []
    for tier in ("T1", "T2", "T3", "T4"):
        names = grouped.get(tier)
        if not names:
            continue
        rendered = ", ".join(f"'{name}'" for name in names)
        lines.append(f"{rendered} ({tier} {_RISK_LABELS[tier]})")
    return "\n            ".join(lines)
