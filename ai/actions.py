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
        description=("List running processes on a device. Read-only; no state change."),
        required_params=(),
    ),
    "list_drives": ActionSpec(
        name="list_drives",
        command_type="list_drives",
        risk_tier="T1",
        reversible=True,
        required_permission="command_execution",
        description=(
            "List mounted drives/volumes and free space on a device. "
            "Read-only; no state change."
        ),
        required_params=(),
    ),
    "tail_system_log": ActionSpec(
        name="tail_system_log",
        command_type="tail_system_log",
        risk_tier="T1",
        reversible=True,
        required_permission="command_execution",
        description=(
            "Read the most recent OS error/warning events (Windows Event Log, "
            "journalctl, or macOS unified log). Read-only; no state change."
        ),
        required_params=(),
    ),
    "scan_filesystem": ActionSpec(
        name="scan_filesystem",
        command_type="scan_filesystem",
        risk_tier="T1",
        reversible=True,
        required_permission="root_access",
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
        description=(
            "Change device settings: volume, brightness, log_level, or hostname. "
            "The 'config' param is a dict of settings to apply; reversible via "
            "snapshot; requires the owner's root_access grant."
        ),
        required_params=("config",),
    ),
    "restart": ActionSpec(
        name="restart",
        command_type="restart",
        risk_tier="T2",
        reversible=True,
        required_permission="root_access",
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
        description=(
            "Update the HOMEPOT User App on a device to the latest published "
            "release. The app checks the server-hosted feed, downloads, and "
            "restarts to install in one action. Briefly interrupts telemetry "
            "during the restart. Requires root_access."
        ),
        required_params=(),
    ),
    "rollback_app": ActionSpec(
        name="rollback_app",
        command_type="rollback_app",
        risk_tier="T3",
        reversible=False,
        required_permission="root_access",
        description=(
            "Roll the HOMEPOT User App on a device back to the previously "
            "served release. The app checks the server-hosted 'previous' "
            "channel, downloads, and restarts to install the older version in "
            "one action. Use only when a newly installed release is broken. "
            "Briefly interrupts telemetry during the restart. Requires "
            "root_access."
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
        description="Shut down the device host. Disruptive and not reversible.",
        required_params=(),
    ),
    "start_program": ActionSpec(
        name="start_program",
        command_type="start_program",
        risk_tier="T2",
        reversible=True,
        required_permission="root_access",
        description="Start a program. Use 'path' (executable path or name on PATH) and optional 'args'.",
        required_params=("path",),
    ),
    "stop_program": ActionSpec(
        name="stop_program",
        command_type="stop_program",
        risk_tier="T2",
        reversible=True,
        required_permission="root_access",
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
        description="Uninstall a program via winget. Use 'package' (winget package ID).",
        required_params=("package",),
    ),
    "update_program": ActionSpec(
        name="update_program",
        command_type="update_program",
        risk_tier="T2",
        reversible=True,
        required_permission="root_access",
        description="Update a single installed program. Use 'package' (winget package ID).",
        required_params=("package",),
    ),
    "upgrade_all_programs": ActionSpec(
        name="upgrade_all_programs",
        command_type="upgrade_all_programs",
        risk_tier="T3",
        reversible=False,
        required_permission="root_access",
        description="Upgrade all installed programs. Disruptive; affects the whole device.",
        required_params=(),
    ),
    "run_command": ActionSpec(
        name="run_command",
        command_type="run_command",
        risk_tier="T3",
        reversible=False,
        required_permission="root_access",
        description="Run an elevated (root) command on the device. Disruptive; not reversible.",
        required_params=("command",),
    ),
    "run_command_unprivileged": ActionSpec(
        name="run_command_unprivileged",
        command_type="run_command_unprivileged",
        risk_tier="T2",
        reversible=True,
        required_permission="command_execution",
        description="Run a command as the unprivileged user on the device.",
        required_params=("command",),
    ),
    "run_script": ActionSpec(
        name="run_script",
        command_type="run_script",
        risk_tier="T3",
        reversible=False,
        required_permission="root_access",
        description="Run an elevated script on the device. Disruptive; not reversible.",
        required_params=("script",),
    ),
    "list_installed_programs": ActionSpec(
        name="list_installed_programs",
        command_type="list_installed_programs",
        risk_tier="T1",
        reversible=True,
        required_permission="command_execution",
        description="List installed programs on the device. Read-only.",
        required_params=(),
    ),
    "list_connections": ActionSpec(
        name="list_connections",
        command_type="list_connections",
        risk_tier="T1",
        reversible=True,
        required_permission="network_monitoring",
        description="List active network connections on the device. Read-only.",
        required_params=(),
    ),
    "network_test": ActionSpec(
        name="network_test",
        command_type="network_test",
        risk_tier="T1",
        reversible=True,
        required_permission="network_monitoring",
        description=(
            "Probe a host by DNS/ping; pass bare hostname in 'host', TCP port "
            "separately in 'port'. Never put a port in 'host' (for example "
            "host='homepot.cabera.com', port=443). Read-only; no state change."
        ),
        required_params=("host",),
    ),
    "list_sessions": ActionSpec(
        name="list_sessions",
        command_type="list_sessions",
        risk_tier="T1",
        reversible=True,
        required_permission="command_execution",
        description="List users currently logged into the device. Read-only.",
        required_params=(),
    ),
    "get_system_info": ActionSpec(
        name="get_system_info",
        command_type="get_system_info",
        risk_tier="T1",
        reversible=True,
        required_permission="command_execution",
        description=(
            "Return a hardware/OS inventory snapshot (CPU, RAM, OS build, and "
            "on Windows serial/model/GPU). Read-only; no state change."
        ),
        required_params=(),
    ),
    "get_battery_status": ActionSpec(
        name="get_battery_status",
        command_type="get_battery_status",
        risk_tier="T1",
        reversible=True,
        required_permission="command_execution",
        description=(
            "Return battery charge percentage, charging state, and estimated "
            "time remaining. Read-only; useful for battery-powered POS devices."
        ),
        required_params=(),
    ),
    "set_app_policy": ActionSpec(
        name="set_app_policy",
        command_type="set_app_policy",
        risk_tier="T2",
        reversible=True,
        required_permission="root_access",
        description=(
            "Configure application allow/block policy on the device. Supports "
            "blocklist (block specific apps) and allowlist (only allow specific "
            "apps) modes. Kills running instances of blocked apps and persists "
            "the policy. Read-only diagnostic; requires root_access."
        ),
        required_params=("mode", "apps"),
    ),
    "set_wifi_policy": ActionSpec(
        name="set_wifi_policy",
        command_type="set_wifi_policy",
        risk_tier="T2",
        reversible=True,
        required_permission="root_access",
        description=(
            "Configure Wi-Fi allow/block policy. Allowlist mode permits only "
            "approved SSIDs; blocklist mode blocks specific SSIDs. Disconnects "
            "from unauthorized networks and persists policy. Requires root_access."
        ),
        required_params=("mode", "networks"),
    ),
    "collect_support_bundle": ActionSpec(
        name="collect_support_bundle",
        command_type="collect_support_bundle",
        risk_tier="T1",
        reversible=True,
        required_permission="command_execution",
        description=(
            "Bundle hardware/OS, disk, process, and metrics snapshots into a "
            "single zip support artifact. Read-only; no state change."
        ),
        required_params=(),
    ),
    "notify_user": ActionSpec(
        name="notify_user",
        command_type="notify_user",
        risk_tier="T2",
        reversible=True,
        required_permission="command_execution",
        description=(
            "Show a message to the person at the device. Transient; no "
            "persistent state change."
        ),
        required_params=("message",),
    ),
    "disk_cleanup": ActionSpec(
        name="disk_cleanup",
        command_type="disk_cleanup",
        risk_tier="T2",
        reversible=True,
        required_permission="command_execution",
        description=(
            "Clear old temp files and caches to reclaim disk space. Removes "
            "files older than a configurable age from the system temp "
            "directory. Reversible in that cleared temp/cache files are "
            "regenerated on demand."
        ),
        required_params=(),
    ),
    "set_service_state": ActionSpec(
        name="set_service_state",
        command_type="set_service_state",
        risk_tier="T2",
        reversible=True,
        required_permission="root_access",
        description=(
            "Enable, disable, start, or stop a named OS service. Use "
            "'service_name' and 'action' (start, stop, enable, or disable). "
            "Reversible via the inverse action."
        ),
        required_params=("service_name", "action"),
    ),
    "lock_screen": ActionSpec(
        name="lock_screen",
        command_type="lock_screen",
        risk_tier="T2",
        reversible=True,
        required_permission="command_execution",
        description=(
            "Lock the terminal's screen (session lock). The person at the "
            "device unlocks it with their credentials. Reversible; no "
            "persistent state change."
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


# Map each risk tier to a short label for tool docstrings / diagnostics.
_RISK_LABELS = {
    "T1": "read-only",
    "T2": "reversible",
    "T3": "disruptive",
    "T4": "destructive",
}


# Longest description fragment rendered into the tool docstring, in characters.
# Names alone are not enough: without a hint of what each action does the model
# cannot tell ``run_command`` from ``run_command_unprivileged`` or discover that
# ``update_config`` is how volume and brightness are changed.
_DESCRIPTION_BUDGET = 96


def _brief(spec: "ActionSpec") -> str:
    """Return the leading clause of an action's description, within budget."""
    text = " ".join(spec.description.split())
    for separator in (". ", ";"):
        cut = text.find(separator)
        if 0 < cut <= _DESCRIPTION_BUDGET:
            return text[: cut + 1]
    if len(text) <= _DESCRIPTION_BUDGET:
        return text
    trimmed = text[:_DESCRIPTION_BUDGET].rsplit(" ", 1)[0]
    return f"{trimmed}..."


def allowed_actions_summary() -> str:
    """Render the registered actions grouped by risk tier.

    This is the single source of truth for the human-readable action list used
    by the proposal tool's docstring, so it can never drift from
    :data:`ACTION_REGISTRY`. Each entry carries a short description and its
    required parameters so the model can map an intent onto the right action
    instead of guessing from the name. Each line is indented to fit inside the
    tool's ``Args`` block.
    """
    grouped: Dict[str, List[str]] = {}
    for name, spec in sorted(ACTION_REGISTRY.items()):
        grouped.setdefault(spec.risk_tier, []).append(name)

    lines: List[str] = []
    for tier in ("T1", "T2", "T3", "T4"):
        names = grouped.get(tier)
        if not names:
            continue
        lines.append(f"{tier} ({_RISK_LABELS[tier]}):")
        for name in names:
            spec = ACTION_REGISTRY[name]
            entry = f"    '{name}' - {_brief(spec)}"
            if spec.required_params:
                entry += f" [params: {', '.join(spec.required_params)}]"
            lines.append(entry)
    return "\n        ".join(lines)
