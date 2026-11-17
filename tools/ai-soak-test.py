#!/usr/bin/env python3
r"""AI-delegation soak test for a single device.

This is the AI counterpart of ``tools/compose-soak-test.py``. Where that script
composes each command directly against the command API, this one drives the AI
delegation loop an operator otherwise runs by hand:

1. ask the AI in natural language to do something on the device,
2. confirm the AI proposed the *expected* action (via the ``propose_device_action``
   tool and the ``ACTION_REGISTRY`` allowlist),
3. approve the plan,
4. release any per-step approval gates (T3 actions),
5. execute the plan and wait for a terminal outcome,
6. confirm the underlying device command landed in Push History and the audit log.

Every one of those steps becomes an assertion, so a run produces evidence
instead of a status line to eyeball:

==============  ==============================================================
proposed        ``POST /ai/query`` returned a proposal (not a direct answer)
action_match    the proposal's action set contains the expected action
persisted       a ``plan_id`` was returned, so the plan was recorded
approved        the plan reached ``approved`` (or was auto-approved)
executed        the plan reached a terminal status within the per-command budget
verified        terminal status is ``succeeded`` and ``outcome.verified`` is set
history         Push History lists the command the plan dispatched
audit           ``command_queued`` -> ``command_sent`` -> ``command_completed``
                appears in the device audit log for that command
==============  ==============================================================

Each row shows the action's risk tier (T1 read-only, T2 reversible, T3
disruptive), read from ``ACTION_REGISTRY`` so the report cannot drift from the
AI's allowlist.

The command set mirrors ``compose-soak-test.py`` exactly (the same 24 safe
actions, in the same order) so the two runs are directly comparable: same
coverage, one through the command API and one through the AI.

Failure policy
--------------
A single failing command never stops the run: all 24 are exercised, then the
report ends with an explicit "failures to investigate" section. The only early
exit is when the device stops polling after ``restart_agent`` — the remaining
commands are then marked ``SKIPPED`` and the run still ends with the same report.

Prompts reference the device by ``device_id`` (not its display name) so the AI
does not have to resolve a name through ``find_device`` first. Name resolution
is a separate capability and is deliberately out of scope for this run.

Known side effects on the operator's own machine match the compose soak:
``update_config`` leaves the volume at 50 and the brightness at 75,
``notify_user`` pops a toast on screen, and ``start_program``/``stop_program``
spawn and stop a ``ping.exe``. The disruptive commands ``restart``, ``shutdown``,
``lock_screen``, ``update_app``, ``rollback_app``, ``upgrade_all_programs`` and
``disk_cleanup`` are excluded so the device stays logged in and the operator's
files are left alone.

Usage:
    HOMEPOT_PASSWORD='...' python tools/ai-soak-test.py \\
        --base-url https://homepot.cabera.com/api/v1 \\
        --email maziar.ghorbani@brunel.ac.uk \\
        --device-id DEVICE-HSZK-T24Y-TSCX \\
        --provider anthropic

    # Preview only (prints the delegated command list, sends nothing):
    python tools/ai-soak-test.py --list

``--provider`` pins the run to one LLM provider (``ollama``/``openai``/
``anthropic``); the server is switched via ``PUT /ai/provider`` first, and the
provider + model are recorded in the evidence bundle. Omit it to record
whatever provider is already active.
"""

import argparse
from datetime import datetime, timedelta, timezone
import getpass
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

# The risk tier shown for each command comes from the action registry, so the
# soak report cannot drift from what the AI is actually allowed to propose.
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)
from ai.actions import ACTION_REGISTRY  # noqa: E402

# Terminal plan statuses: polling stops at any of these.
TERMINAL_PLAN_STATUSES = {
    "succeeded",
    "failed",
    "rolled_back",
    "blocked",
    "rejected",
    "cancelled",
}

# A successful delegation: the plan succeeded and the verifier confirmed the
# device result. "succeeded" is only recorded with ``verified=True`` by the
# verifier, but both are checked so a plan that reaches "succeeded" without an
# outcome is not silently scored as a pass.
SUCCESS_STATUS = "succeeded"

# Command and audit timestamps are written by the server, while window edges are
# taken on this machine. A little clock skew between the two must not make a
# correctly recorded command look missing.
CLOCK_SKEW_TOLERANCE_S = 300

# The device log stream mixes real errors with bookkeeping rows that are not
# errors (see compose-soak-test.py for the full rationale).
LOG_NOISE_CATEGORIES = {"status", "command"}
ERROR_SEVERITIES = {"warning", "error", "critical", "fatal"}

# An agent that has just started reports a few seconds of uptime. A soak device
# has been up for hours, so this separates "restarted" from "still the old
# process" without needing the restart counter.
FRESH_UPTIME_S = 60

# Outcomes reported for one command.
OUTCOME_PASS = "PASS"  # nosec B105 - a status label, not a credential
OUTCOME_NOTE = "PASS_NOTE"
OUTCOME_FAIL = "FAIL"
OUTCOME_BLOCKED = "BLOCKED"
OUTCOME_TIMEOUT = "TIMEOUT"
OUTCOME_SKIPPED = "SKIPPED"

# Device grant each command type is gated on. Mirrors REQUIRED_PERMISSION in
# backend/src/homepot/agent/utils/command_poller.py; the executor re-checks the
# same grant before dispatching, so a missing grant blocks the plan.
REQUIRED_PERMISSIONS: Dict[str, str] = {
    "health_check": "command_execution",
    "restart_agent": "root_access",
    "restart_service": "root_access",
    "set_service_state": "root_access",
    "run_command": "root_access",
    "run_script": "root_access",
    "update_config": "root_access",
    "list_processes": "process_monitoring",
    "list_connections": "network_monitoring",
    "list_drives": "command_execution",
    "tail_system_log": "command_execution",
    "network_test": "network_monitoring",
    "list_sessions": "command_execution",
    "get_system_info": "command_execution",
    "notify_user": "command_execution",
    "collect_support_bundle": "command_execution",
    "scan_filesystem": "root_access",
    "run_command_unprivileged": "command_execution",
    "install_program": "root_access",
    "uninstall_program": "root_access",
    "list_installed_programs": "command_execution",
    "update_program": "root_access",
    "start_program": "root_access",
    "stop_program": "root_access",
}

# (action, label, prompt, timeout_seconds, settle_seconds)
# timeouts are generous on purpose (the winget commands are slow); settle is an
# extra pause after the command before the next one (longer for restart_agent).
# The "{device}" placeholder is replaced with the device_id at run time.
SOAK_COMMANDS: List[Dict[str, Any]] = [
    # --- T1 read-only diagnostics ---
    {
        "action": "health_check",
        "label": "Health Check",
        "prompt": "Run a health check on the device {device}.",
        "timeout": 300,
    },
    {
        "action": "list_processes",
        "label": "List Processes",
        "prompt": "List the running processes on the device {device}.",
        "timeout": 300,
    },
    {
        "action": "list_connections",
        "label": "List Connections",
        "prompt": "List the active network connections on the device {device}.",
        "timeout": 300,
    },
    {
        "action": "list_drives",
        "label": "List Drives",
        "prompt": "List the drives on the device {device}.",
        "timeout": 300,
    },
    {
        "action": "tail_system_log",
        "label": "Tail System Log",
        "prompt": "Read the most recent system log events on the device {device}.",
        "timeout": 300,
    },
    {
        "action": "network_test",
        "label": "Network Test",
        "prompt": "Test network connectivity from the device {device} to "
        "homepot.cabera.com on port 443.",
        "timeout": 300,
    },
    {
        "action": "list_sessions",
        "label": "List Sessions",
        "prompt": "List the users currently logged in on the device {device}.",
        "timeout": 300,
    },
    {
        "action": "get_system_info",
        "label": "Get System Info",
        "prompt": "Get the system information for the device {device}.",
        "timeout": 300,
    },
    {
        "action": "collect_support_bundle",
        "label": "Collect Support Bundle",
        "prompt": "Collect a support bundle on the device {device}.",
        "timeout": 300,
    },
    {
        "action": "list_installed_programs",
        "label": "List Installed Programs",
        "prompt": "List the programs installed on the device {device}.",
        "timeout": 300,
    },
    {
        "action": "scan_filesystem",
        "label": "Scan Filesystem",
        "prompt": "Scan the filesystem of the device {device}.",
        "timeout": 300,
    },
    # --- T2 reversible control ---
    {
        "action": "notify_user",
        "label": "Notify User",
        "prompt": "Show a message to the person at the device {device} saying "
        "'HOMEPOT soak test'.",
        "timeout": 300,
    },
    {
        "action": "update_config",
        "label": "Update Config",
        "prompt": "Set the volume to 50 and the brightness to 75 on the device "
        "{device}.",
        "timeout": 300,
    },
    {
        "action": "run_command_unprivileged",
        "label": "Run Command (Unprivileged)",
        "prompt": "Run the command 'ipconfig' as the unprivileged user on the "
        "device {device}.",
        "timeout": 300,
    },
    {
        "action": "start_program",
        "label": "Start Program (ping)",
        "prompt": "Start the program 'ping.exe' on the device {device}.",
        "timeout": 300,
    },
    {
        "action": "stop_program",
        "label": "Stop Program (ping)",
        "prompt": "Stop the 'ping.exe' process on the device {device}.",
        "timeout": 300,
    },
    {
        "action": "set_service_state",
        "label": "Set Service State (start Spooler)",
        "prompt": "Start the 'Spooler' service on the device {device}.",
        "timeout": 300,
    },
    # --- Service / agent restart (no PIN, recover quickly) ---
    {
        "action": "restart_service",
        "label": "Restart Service (Spooler)",
        "prompt": "Restart the 'Spooler' service on the device {device}.",
        "timeout": 300,
    },
    {
        "action": "restart_agent",
        "label": "Restart Agent",
        "prompt": "Restart the agent on the device {device}.",
        "timeout": 300,
        "settle": 5,
        "verify_agent": True,
    },
    # --- Elevated commands with safe payloads ---
    {
        "action": "run_command",
        "label": "Run Command (systeminfo)",
        "prompt": "Run the command 'systeminfo' with elevated privileges on the "
        "device {device}.",
        "timeout": 300,
    },
    {
        "action": "run_script",
        "label": "Run Script (hostname)",
        "prompt": "Run a short script that prints the hostname, with elevated "
        "privileges, on the device {device}.",
        "timeout": 300,
    },
    # --- Winget (slow, network) — last ---
    {
        "action": "install_program",
        "label": "Install Program (Notepad++)",
        "prompt": "Install Notepad++ on the device {device}.",
        "timeout": 900,
    },
    {
        "action": "update_program",
        "label": "Update Program (Notepad++)",
        "prompt": "Update Notepad++ on the device {device}.",
        "timeout": 900,
    },
    {
        "action": "uninstall_program",
        "label": "Uninstall Program (Notepad++)",
        "prompt": "Uninstall Notepad++ from the device {device}.",
        "timeout": 900,
    },
]


# --- HTTP helpers -----------------------------------------------------------


def login(client: httpx.Client, base_url: str, email: str, password: str) -> None:
    """Authenticate so the session cookie is set on the client."""
    r = client.post(
        f"{base_url}/auth/login", json={"email": email, "password": password}
    )
    r.raise_for_status()


def get_device(client: httpx.Client, base_url: str, device_id: str) -> Dict[str, Any]:
    """Fetch the device record used for readiness checks and recovery probes."""
    r = client.get(f"{base_url}/devices/device/{device_id}")
    r.raise_for_status()
    payload = r.json()
    return payload if isinstance(payload, dict) else {}


def query_ai(
    client: httpx.Client,
    base_url: str,
    device_id: str,
    prompt: str,
    timeout: int,
) -> Dict[str, Any]:
    """Ask the AI to act on the device and return the full query response.

    ``agentic=True`` enables the tool-calling loop; ``mode="diagnostic"`` pins
    the operational path (gates run, so proposals are only surfaced when the
    answer is actionable). ``device_id`` both scopes the run and guarantees the
    router does not misclassify the query as a documentation question.
    """
    r = client.post(
        f"{base_url}/ai/query",
        json={
            "query": prompt,
            "device_id": device_id,
            "agentic": True,
            "mode": "diagnostic",
        },
        timeout=timeout,
    )
    r.raise_for_status()
    payload = r.json()
    return payload if isinstance(payload, dict) else {}


def get_plan(client: httpx.Client, base_url: str, plan_id: str) -> Dict[str, Any]:
    """Fetch one action plan with its serialized steps and outcome."""
    r = client.get(f"{base_url}/ai/action-plans/{plan_id}")
    r.raise_for_status()
    payload = r.json()
    return payload if isinstance(payload, dict) else {}


def approve_plan(client: httpx.Client, base_url: str, plan_id: str) -> Dict[str, Any]:
    """Approve a pending plan (does not execute)."""
    r = client.post(
        f"{base_url}/ai/action-plans/{plan_id}/approve", json={"reason": "soak test"}
    )
    r.raise_for_status()
    payload = r.json()
    return payload if isinstance(payload, dict) else {}


def approve_step(
    client: httpx.Client, base_url: str, plan_id: str, step_id: str
) -> Dict[str, Any]:
    """Release one per-step approval gate on a plan."""
    r = client.post(
        f"{base_url}/ai/action-plans/{plan_id}/steps/{step_id}/approve",
        json={"reason": "soak test"},
    )
    r.raise_for_status()
    payload = r.json()
    return payload if isinstance(payload, dict) else {}


def execute_plan(client: httpx.Client, base_url: str, plan_id: str) -> Dict[str, Any]:
    """Execute an approved plan; completion is asynchronous (reconcile loop)."""
    r = client.post(f"{base_url}/ai/action-plans/{plan_id}/execute")
    r.raise_for_status()
    payload = r.json()
    return payload if isinstance(payload, dict) else {}


def get_provider_info(client: httpx.Client, base_url: str) -> Dict[str, Any]:
    """Return the server's current LLM provider, model and key status."""
    r = client.get(f"{base_url}/ai/provider")
    r.raise_for_status()
    payload = r.json()
    data = payload.get("data") if isinstance(payload, dict) else {}
    return data if isinstance(data, dict) else {}


def switch_provider(
    client: httpx.Client, base_url: str, provider: str
) -> Dict[str, Any]:
    """Switch the server's active LLM provider (admin only)."""
    r = client.put(f"{base_url}/ai/provider", params={"provider": provider})
    r.raise_for_status()
    payload = r.json()
    data = payload.get("data") if isinstance(payload, dict) else {}
    return data if isinstance(data, dict) else {}


def resolve_provider(
    client: httpx.Client, base_url: str, requested: Optional[str]
) -> Tuple[str, str]:
    """Return (provider, model), switching the server when ``requested`` differs.

    The server's provider is a global setting; ``--provider`` pins it for the
    run. Switching is admin-only, so a 403 leaves the current provider in place
    and the run records what actually happened rather than guessing.
    """
    info = get_provider_info(client, base_url)
    current = str(info.get("current") or "unknown")
    model = str(info.get("model") or "unknown")
    if requested and requested != current:
        try:
            info = switch_provider(client, base_url, requested)
            current = str(info.get("current") or current)
            model = str(info.get("model") or model)
            print(f"Switched provider to {current} (model: {model})")
        except httpx.HTTPStatusError as exc:
            print(
                f"Could not switch provider to '{requested}' "
                f"({exc.response.status_code}); using {current}"
            )
    return current, model


def get_history(
    client: httpx.Client, base_url: str, device_id: str, limit: int = 10
) -> List[Dict[str, Any]]:
    """Fetch the Push History listing (newest first)."""
    r = client.get(
        f"{base_url}/devices/device/{device_id}/commands", params={"limit": limit}
    )
    r.raise_for_status()
    rows = r.json()
    return (
        [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    )


def get_audit_events(
    client: httpx.Client, base_url: str, device_id: str, limit: int = 200
) -> List[Dict[str, Any]]:
    """Fetch device audit events (command lifecycle transitions live here)."""
    r = client.get(
        f"{base_url}/devices/device/{device_id}/audit-logs", params={"limit": limit}
    )
    r.raise_for_status()
    rows = r.json()
    return (
        [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    )


def error_fingerprints(
    client: httpx.Client, base_url: str, device_id: str, limit: int = 100
) -> List[str]:
    """Return recent *device errors* as stable fingerprint strings.

    Despite its name, ``/error-logs`` returns the whole device log stream: the
    periodic ``Status report: ONLINE ...`` heartbeat and every command's own
    ``Command completed: ...`` line are stored there with ``severity="info"``.
    Bookkeeping rows are dropped (see compose-soak-test.py for the rationale).
    """
    try:
        r = client.get(
            f"{base_url}/devices/device/{device_id}/error-logs",
            params={"limit": limit},
        )
        r.raise_for_status()
        rows = r.json()
    except Exception:  # noqa: BLE001 - log comparison is best effort
        return []
    if not isinstance(rows, list):
        return []

    fingerprints: List[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("category") or "").lower() in LOG_NOISE_CATEGORIES:
            continue
        severity = str(row.get("severity") or "").lower()
        if severity:
            if severity not in ERROR_SEVERITIES:
                continue
        elif not row.get("error_code"):
            continue
        fingerprints.append(
            "{0}|{1}|{2}".format(
                row.get("timestamp"),
                row.get("error_code"),
                str(row.get("error_message") or "")[:120],
            )
        )
    return fingerprints


# --- Verification helpers ---------------------------------------------------


def parse_timestamp(value: Any) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp from the API into an aware datetime."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def elapsed_seconds(start: Any, end: Any) -> Optional[float]:
    """Return whole seconds between two API timestamps, or None."""
    first = parse_timestamp(start)
    second = parse_timestamp(end)
    if first is None or second is None:
        return None
    return round((second - first).total_seconds(), 2)


def clamped_seconds(start: Any, end: Any) -> Optional[float]:
    """Like ``elapsed_seconds`` but never negative."""
    raw = elapsed_seconds(start, end)
    if raw is None:
        return None
    return max(0.0, raw)


def verify_history(
    history: List[Dict[str, Any]], command_id: Optional[str], status: Optional[str]
) -> Dict[str, Any]:
    """Check that Push History lists this command with the polled status."""
    if not command_id:
        return {
            "listed": False,
            "status": None,
            "status_matches": False,
            "result_present": False,
            "ok": False,
        }
    listed = next(
        (row for row in history if row.get("command_id") == command_id),
        None,
    )
    found = listed or {}
    return {
        "listed": listed is not None,
        "status": found.get("status"),
        "status_matches": listed is not None and found.get("status") == status,
        "result_present": listed is not None and bool(found.get("result")),
        "ok": listed is not None
        and found.get("status") == status
        and bool(found.get("result")),
    }


def verify_audit(
    events: List[Dict[str, Any]],
    command_id: str,
    command_type: str,
    queued_at: Optional[datetime],
    finished_at: Optional[datetime],
    expect_sent: bool,
    expect_terminal: bool,
) -> Dict[str, Any]:
    """Check the audit trail for this command's lifecycle.

    All paths now write ``command_queued`` when the command row is created, so
    ``ok`` requires queued, sent and terminal events. The queued event is
    correlated by command id (AI path) or command type (operator path) because
    the operator event does not carry the id in its description.
    """
    cid = str(command_id)

    def with_id(event_type: str) -> bool:
        return any(
            event.get("event_type") == event_type
            and cid in str(event.get("description") or "")
            for event in events
        )

    def queued_within_window() -> bool:
        for event in events:
            if event.get("event_type") != "command_queued":
                continue
            description = str(event.get("description") or "")
            if cid not in description and command_type not in description:
                continue
            created = parse_timestamp(event.get("created_at"))
            if created is None:
                return True
            if queued_at is None:
                return True
            lower = queued_at - timedelta(seconds=CLOCK_SKEW_TOLERANCE_S)
            upper = (
                finished_at + timedelta(seconds=CLOCK_SKEW_TOLERANCE_S)
                if finished_at is not None
                else None
            )
            if created >= lower and (upper is None or created <= upper):
                return True
        return False

    sent = with_id("command_sent")
    terminal = with_id("command_completed") or with_id("command_failed")
    queued = queued_within_window()
    ok = queued and (sent or not expect_sent) and (terminal or not expect_terminal)
    return {
        "queued": queued,
        "sent": sent,
        "terminal": terminal,
        "ok": ok,
    }


def snapshot_agent_state(
    client: httpx.Client, base_url: str, device_id: str
) -> Dict[str, Any]:
    """Read the server-side agent liveness fields used to prove a restart."""
    try:
        device = get_device(client, base_url, device_id)
    except Exception:  # noqa: BLE001 - the probe reports "unknown" and moves on
        return {}
    return {
        "last_seen": device.get("last_seen"),
        "agent_restart_count": device.get("agent_restart_count"),
        "agent_uptime_seconds": device.get("agent_uptime_seconds"),
    }


def wait_for_agent_recovery(
    client: httpx.Client,
    base_url: str,
    device_id: str,
    baseline: Dict[str, Any],
    timeout: int,
) -> Dict[str, Any]:
    """Wait until the agent proves it actually restarted (see compose soak)."""
    started = time.monotonic()
    base_count = baseline.get("agent_restart_count")
    base_uptime = baseline.get("agent_uptime_seconds")
    verifiable = isinstance(base_count, int) or isinstance(base_uptime, (int, float))
    best: Dict[str, Any] = {}

    while time.monotonic() - started < timeout:
        try:
            device = get_device(client, base_url, device_id)
        except Exception:  # noqa: BLE001 - transient errors while it restarts
            time.sleep(5)
            continue

        count = device.get("agent_restart_count")
        uptime = device.get("agent_uptime_seconds")
        best = {
            "last_seen": device.get("last_seen"),
            "agent_restart_count": count,
            "agent_uptime_seconds": uptime,
        }

        counted = (
            isinstance(count, int)
            and isinstance(base_count, int)
            and count > base_count
        )
        fresh = isinstance(uptime, (int, float)) and uptime < FRESH_UPTIME_S
        reset = (
            isinstance(uptime, (int, float))
            and isinstance(base_uptime, (int, float))
            and uptime < base_uptime - FRESH_UPTIME_S
        )
        if counted or fresh or reset:
            proof = "restart_count" if counted else "uptime_reset" if reset else "fresh"
            return {
                "recovered": True,
                "verified": True,
                "proof": proof,
                "waited_s": round(time.monotonic() - started, 1),
                **best,
            }
        time.sleep(5)

    return {
        "recovered": False,
        "verified": verifiable,
        "proof": None,
        "waited_s": round(time.monotonic() - started, 1),
        **best,
    }


def verify_restart(
    client: httpx.Client,
    base_url: str,
    device_id: str,
    record: Dict[str, Any],
    restart_wait: int,
) -> Optional[str]:
    """Prove the agent restarted; return an abort reason when it did not."""
    baseline = snapshot_agent_state(client, base_url, device_id)
    probe = wait_for_agent_recovery(client, base_url, device_id, baseline, restart_wait)
    record["agent_recovery"] = probe

    if probe["recovered"]:
        print(
            f"  agent back after {probe['waited_s']}s "
            f"(proof: {probe['proof']}, uptime={probe.get('agent_uptime_seconds')}s)"
        )
        return None

    if not probe["verified"]:
        print("  restart could not be verified; continuing")
        record["notes"].append(
            "agent restart could not be verified (no restart counter or uptime "
            "reported)"
        )
        return None

    reason = (
        f"agent did not restart within {restart_wait}s "
        "(restart counter unchanged and uptime not reset)"
    )
    record["outcome"] = OUTCOME_FAIL
    record["notes"].append(reason)
    print(f"  {reason}; remaining commands marked SKIPPED")
    return reason


# --- Readiness --------------------------------------------------------------


def evaluate_readiness(
    device: Dict[str, Any], commands: List[Dict[str, Any]]
) -> Tuple[bool, List[str], List[str]]:
    """Return (ready, blocking problems, warnings) for the planned run."""
    problems: List[str] = []
    warnings: List[str] = []

    lifecycle = str(device.get("lifecycle_state") or "unknown")
    if lifecycle != "active":
        problems.append(
            f"lifecycle_state is '{lifecycle}'; commands are only accepted for "
            "'active' devices"
        )

    connectivity = str(device.get("connectivity_state") or "").strip().lower()
    if connectivity and connectivity != "online":
        problems.append(
            f"connectivity_state is '{connectivity}'; proposals are refused for "
            "devices that are not online, so a run would measure nothing"
        )

    permissions = device.get("device_permissions")
    granted = permissions if isinstance(permissions, dict) else {}
    blocked: Dict[str, List[str]] = {}
    for spec in commands:
        needed = REQUIRED_PERMISSIONS.get(str(spec["action"]))
        if needed and not granted.get(needed, False):
            blocked.setdefault(needed, []).append(str(spec["action"]))
    for grant, actions in sorted(blocked.items()):
        problems.append(
            f"missing grant '{grant}' blocks {len(actions)} command(s): "
            + ", ".join(sorted(set(actions)))
        )

    last_seen = parse_timestamp(device.get("last_seen"))
    if last_seen is None:
        warnings.append("device has no last_seen value; it may never have polled")
    else:
        age = (datetime.now(timezone.utc) - last_seen).total_seconds()
        if age > 300:
            warnings.append(
                f"device last polled {int(age)}s ago; commands will wait for the "
                "next poll"
            )

    return not problems, problems, warnings


# --- One command ------------------------------------------------------------


def action_tier(action: str) -> str:
    """Return the registry risk tier for an action, or ``?`` if unregistered."""
    spec = ACTION_REGISTRY.get(action)
    return spec.risk_tier if spec is not None else "?"


def new_record(index: int, action: str, label: str, prompt: str) -> Dict[str, Any]:
    """Build the empty evidence record shared by run and skipped commands."""
    return {
        "index": index,
        "action": action,
        "tier": action_tier(action),
        "label": label,
        "prompt": prompt,
        "plan_id": None,
        "plan_status": None,
        "outcome": OUTCOME_FAIL,
        "checks": {
            "proposed": False,
            "action_match": False,
            "persisted": False,
            "approved": False,
            "executed": False,
            "verified": False,
            "history": False,
            "audit": False,
        },
        "proposed_actions": [],
        "trust": {},
        "gate_failure": None,
        "provider": None,
        "response": None,
        "tools_called": [],
        "step_approvals": [],
        "steps": [],
        "outcome_detail": None,
        "command_id": None,
        "timings": {},
        "new_errors": [],
        "notes": [],
        "window": {},
    }


def proposal_from_response(resp: Dict[str, Any]) -> Dict[str, Any]:
    """Return the proposal object from an AI query response, or ``{}``."""
    proposal = resp.get("proposal")
    if not isinstance(proposal, dict):
        return {}
    return proposal


def proposed_actions(proposal: Dict[str, Any]) -> List[str]:
    """Return the distinct action names in a proposal's steps."""
    steps = proposal.get("steps")
    if not isinstance(steps, list):
        return []
    actions: List[str] = []
    for step in steps:
        if isinstance(step, dict) and step.get("action"):
            actions.append(str(step["action"]))
    return actions


def query_proposal(
    client: httpx.Client,
    base_url: str,
    device_id: str,
    prompt: str,
    record: Dict[str, Any],
    query_timeout: int,
    started: float,
) -> Dict[str, Any]:
    """Run the AI query and fill ``record`` with what the AI proposed.

    Returns the proposal dict (possibly empty). A gate failure or a run that
    produced no proposal is recorded here so the caller can classify it.
    """
    try:
        resp = query_ai(client, base_url, device_id, prompt, query_timeout)
    except httpx.HTTPStatusError as exc:
        record["outcome"] = OUTCOME_FAIL
        record["notes"].append(f"query failed ({exc.response.status_code})")
        record["timings"] = {"query_s": round(time.monotonic() - started, 1)}
        return {}
    except Exception as exc:  # noqa: BLE001 - recorded, never raised
        record["outcome"] = OUTCOME_FAIL
        record["notes"].append(f"query error: {exc}")
        record["timings"] = {"query_s": round(time.monotonic() - started, 1)}
        return {}

    record["timings"]["query_s"] = round(time.monotonic() - started, 1)

    record["provider"] = resp.get("provider")
    response_text = resp.get("response")
    if isinstance(response_text, str) and response_text:
        record["response"] = response_text[:500]
    agentic = resp.get("agentic")
    if isinstance(agentic, dict):
        record["tools_called"] = agentic.get("tools_called") or []

    trust: Dict[str, Any] = {}
    if isinstance(resp.get("trust"), dict):
        trust = resp["trust"]
    record["trust"] = trust
    if not trust.get("actionable"):
        record["gate_failure"] = trust.get("failed_gate") or "unknown"
        record["outcome"] = OUTCOME_BLOCKED
        record["notes"].append(
            f"validation not actionable (gate {record['gate_failure']})"
        )
        return {}

    proposal = proposal_from_response(resp)
    actions = proposed_actions(proposal)
    record["proposed_actions"] = actions
    if not actions:
        record["outcome"] = OUTCOME_FAIL
        record["notes"].append("AI produced no proposal for an actionable query")
        return {}
    record["checks"]["proposed"] = True
    return proposal


def _approve_plan(
    client: httpx.Client,
    base_url: str,
    plan_id: str,
    status: str,
    record: Dict[str, Any],
) -> bool:
    """Approve a plan unless it is already approved; return success."""
    if status == "approved":
        # Autonomy level 3 can auto-approve the plan during proposal.
        return True
    try:
        approve_plan(client, base_url, plan_id)
        return True
    except httpx.HTTPStatusError as exc:
        record["notes"].append(f"approve failed ({exc.response.status_code})")
    except Exception as exc:  # noqa: BLE001 - recorded, never raised
        record["notes"].append(f"approve error: {exc}")
    return False


def _approve_gated_step(
    client: httpx.Client, base_url: str, plan_id: str, step: Dict[str, Any]
) -> Dict[str, Any]:
    """Approve one gated step; return a result describing the outcome."""
    step_id = str(step.get("step_id") or "")
    if not step_id:
        return {"ok": False, "error": "missing step_id"}
    try:
        approve_step(client, base_url, plan_id, step_id)
        return {"step_id": step_id, "ok": True}
    except httpx.HTTPStatusError as exc:
        return {"step_id": step_id, "ok": False, "status": exc.response.status_code}
    except Exception as exc:  # noqa: BLE001 - recorded, never raised
        return {"step_id": step_id, "ok": False, "error": str(exc)}


def approve_plan_and_steps(
    client: httpx.Client,
    base_url: str,
    record: Dict[str, Any],
    plan: Dict[str, Any],
) -> None:
    """Approve the plan, then release every per-step approval gate.

    ``plan`` is the serialized plan; ``record`` is mutated with the approval
    outcome. Steps are approved *before* execution so the execute call can
    dispatch every step in one pass (the per-step gate pauses at
    ``awaiting_approval`` otherwise).
    """
    plan_id = str(record["plan_id"])
    if not _approve_plan(
        client, base_url, plan_id, str(plan.get("status") or ""), record
    ):
        return
    record["checks"]["approved"] = True

    steps = plan.get("steps")
    if not isinstance(steps, list):
        return
    for step in steps:
        if isinstance(step, dict) and step.get("approval_required"):
            record["step_approvals"].append(
                _approve_gated_step(client, base_url, plan_id, step)
            )


def poll_until_terminal(
    client: httpx.Client,
    base_url: str,
    plan_id: str,
    timeout: int,
    poll_interval: int,
) -> Tuple[Dict[str, Any], List[str]]:
    """Poll a plan until a terminal status or the per-command timeout."""
    deadline = time.monotonic() + timeout
    plan: Dict[str, Any] = {}
    notes: List[str] = []
    failures = 0

    while time.monotonic() < deadline:
        try:
            plan = get_plan(client, base_url, plan_id)
        except Exception as exc:  # noqa: BLE001 - retry until the deadline
            failures += 1
            if failures <= 3:
                notes.append(f"poll error: {exc}")
            time.sleep(poll_interval)
            continue
        if plan.get("status") in TERMINAL_PLAN_STATUSES:
            break
        time.sleep(poll_interval)

    return plan, notes


def command_id_from_plan(plan: Dict[str, Any]) -> Optional[str]:
    """Return the first dispatched command id in a serialized plan, or None."""
    steps = plan.get("steps")
    if not isinstance(steps, list):
        return None
    for step in steps:
        if isinstance(step, dict) and step.get("command_id"):
            return str(step["command_id"])
    return None


def outcome_verified(plan: Dict[str, Any]) -> bool:
    """Return True when a terminal plan succeeded with a verified outcome."""
    if plan.get("status") != SUCCESS_STATUS:
        return False
    outcome = plan.get("outcome")
    return isinstance(outcome, dict) and bool(outcome.get("verified"))


def verify_recorded(
    client: httpx.Client,
    base_url: str,
    device_id: str,
    record: Dict[str, Any],
    queued_at: datetime,
    finished_at: datetime,
    errors_before: List[str],
) -> None:
    """Fill the Push History, audit-trail and device-log checks in ``record``."""
    command_id = record.get("command_id")
    status = record.get("command_status")

    try:
        history = get_history(client, base_url, device_id)
    except Exception as exc:  # noqa: BLE001 - report, do not lose the run
        history = []
        record["notes"].append(f"history fetch failed: {exc}")
    record["history"] = verify_history(history, command_id, status)
    record["checks"]["history"] = bool(record["history"]["ok"])

    if command_id:
        try:
            events = get_audit_events(client, base_url, device_id)
        except Exception as exc:  # noqa: BLE001 - report, do not lose the run
            events = []
            record["notes"].append(f"audit fetch failed: {exc}")
        record["audit"] = verify_audit(
            events,
            command_id,
            str(record["action"]),
            queued_at,
            finished_at,
            expect_sent=True,
            expect_terminal=record["checks"]["verified"],
        )
        record["checks"]["audit"] = bool(record["audit"]["ok"])

    errors_after = error_fingerprints(client, base_url, device_id)
    if errors_before and errors_after:
        seen = set(errors_before)
        record["new_errors"] = [row for row in errors_after if row not in seen]


def classify_outcome(record: Dict[str, Any], timed_out: bool) -> str:
    """Map a command's evidence onto one of the reported outcomes."""
    checks = record["checks"]
    if timed_out:
        return OUTCOME_TIMEOUT
    if not checks["proposed"] or not checks["action_match"] or not checks["persisted"]:
        return OUTCOME_FAIL
    if not checks["approved"] or not checks["executed"] or not checks["verified"]:
        if record["plan_status"] in ("blocked", "rejected", "cancelled"):
            return OUTCOME_BLOCKED
        return OUTCOME_FAIL
    if record["new_errors"]:
        return OUTCOME_NOTE
    return OUTCOME_PASS


def run_one(
    client: httpx.Client,
    base_url: str,
    device_id: str,
    index: int,
    spec: Dict[str, Any],
    args: argparse.Namespace,
) -> Dict[str, Any]:
    """Delegate a single command to the AI end to end and return its evidence."""
    action = str(spec["action"])
    prompt = str(spec["prompt"]).format(device=device_id)
    record = new_record(index, action, str(spec["label"]), prompt)

    errors_before = error_fingerprints(client, base_url, device_id)
    started = time.monotonic()

    proposal = query_proposal(
        client, base_url, device_id, prompt, record, int(args.query_timeout), started
    )
    if not proposal:
        return record

    record["checks"]["action_match"] = action in record["proposed_actions"]
    if not record["checks"]["action_match"]:
        record["outcome"] = OUTCOME_FAIL
        record["notes"].append(
            f"AI proposed {record['proposed_actions']} but not the expected "
            f"'{action}'"
        )
        return record

    plan_id = str(proposal.get("plan_id") or "")
    record["plan_id"] = plan_id
    record["checks"]["persisted"] = bool(plan_id)
    if not plan_id:
        record["outcome"] = OUTCOME_FAIL
        record["notes"].append("proposal had no plan_id")
        return record

    try:
        plan = get_plan(client, base_url, plan_id)
    except Exception as exc:  # noqa: BLE001 - recorded, never raised
        record["outcome"] = OUTCOME_FAIL
        record["notes"].append(f"could not read plan {plan_id}: {exc}")
        return record
    record["plan_status"] = plan.get("status")

    queued_at = datetime.now(timezone.utc)
    approve_plan_and_steps(client, base_url, record, plan)
    if not record["checks"]["approved"]:
        record["outcome"] = OUTCOME_FAIL
        return record

    try:
        execute_plan(client, base_url, plan_id)
    except httpx.HTTPStatusError as exc:
        record["outcome"] = OUTCOME_FAIL
        record["notes"].append(f"execute failed ({exc.response.status_code})")
        return record
    except Exception as exc:  # noqa: BLE001 - recorded, never raised
        record["outcome"] = OUTCOME_FAIL
        record["notes"].append(f"execute error: {exc}")
        return record

    final_plan, poll_notes = poll_until_terminal(
        client,
        base_url,
        plan_id,
        int(spec["timeout"]),
        int(args.poll_interval),
    )
    record["notes"].extend(poll_notes)

    finished_at = datetime.now(timezone.utc)
    record["plan_status"] = final_plan.get("status")
    record["steps"] = final_plan.get("steps") or []
    record["outcome_detail"] = final_plan.get("outcome")
    record["window"] = {
        "queued_at": queued_at.isoformat(),
        "finished_at": finished_at.isoformat(),
    }

    timed_out = final_plan.get("status") not in TERMINAL_PLAN_STATUSES
    record["checks"]["executed"] = not timed_out
    record["checks"]["verified"] = outcome_verified(final_plan)

    command_id = command_id_from_plan(final_plan)
    record["command_id"] = command_id
    # The dispatched command's terminal status mirrors the plan result.
    record["command_status"] = "completed" if record["checks"]["verified"] else None

    verify_recorded(
        client,
        base_url,
        device_id,
        record,
        queued_at,
        finished_at,
        errors_before,
    )

    record["timings"].update(
        {
            "query_s": record["timings"].get("query_s"),
            "total_s": round(time.monotonic() - started, 1),
        }
    )
    record["outcome"] = classify_outcome(record, timed_out)
    return record


# --- Reporting --------------------------------------------------------------


def format_elapsed(seconds: Optional[float]) -> str:
    """Render an elapsed time compactly for the table."""
    if seconds is None:
        return "-"
    return f"{seconds:.1f}s"


def print_table(records: List[Dict[str, Any]]) -> None:
    """Print one evidence row per command."""
    print(
        f"{'#':>3}  {'tier':4s}  {'action':26s}  {'prop':4s} {'match':5s} {'plan':4s} "
        f"{'approv':6s} {'exec':4s} {'verif':5s} {'hist':4s} {'audit':5s} "
        f"{'err':>3s} {'elapsed':>8s}  outcome"
    )
    for record in records:
        checks = record["checks"]
        if record["outcome"] == OUTCOME_SKIPPED:
            print(
                f"{record['index']:>3}  {record['tier']:4s}  "
                f"{record['action']:26s}  "
                f"{'':57s} {OUTCOME_SKIPPED}"
            )
            continue

        def mark(name: str) -> str:
            return "ok" if checks.get(name) else "--"

        print(
            f"{record['index']:>3}  {record['tier']:4s}  "
            f"{record['action']:26s}  "
            f"{mark('proposed'):4s} {mark('action_match'):5s} "
            f"{mark('persisted'):4s} {mark('approved'):6s} "
            f"{mark('executed'):4s} {mark('verified'):5s} "
            f"{mark('history'):4s} {mark('audit'):5s} "
            f"{len(record['new_errors']):>3d} "
            f"{format_elapsed(record['timings'].get('total_s')):>8s}  "
            f"{record['outcome']}"
        )


def print_failure_detail(record: Dict[str, Any], device_id: str) -> None:
    """Print everything needed to investigate one command."""
    window = record.get("window") or {}
    proposed = ", ".join(record.get("proposed_actions") or []) or "-"
    print(
        f"#{record['index']} {record['action']} [{record['tier']}] "
        f"({record['label']}) — {record['outcome']}"
    )
    print(f"    prompt     : {record['prompt']}")
    print(f"    plan_id    : {record.get('plan_id') or '(never created)'}")
    print(f"    plan status: {record.get('plan_status') or '-'}")
    print(f"    proposed   : {proposed}")
    if record.get("gate_failure"):
        print(f"    gate       : {record['gate_failure']} (not actionable)")
    checks = ", ".join(
        f"{name}={'ok' if value else 'no'}" for name, value in record["checks"].items()
    )
    print(f"    checks     : {checks}")
    for approval in record.get("step_approvals") or []:
        if not approval.get("ok"):
            print(f"    step gate  : {approval}")
    print(f"    command_id : {record.get('command_id') or '-'}")
    if record.get("outcome_detail") is not None:
        print(f"    outcome    : {json.dumps(record['outcome_detail'])[:300]}")
    for note in record.get("notes") or []:
        print(f"    note       : {note}")
    for row in record["new_errors"][:5]:
        print(f"    new log    : {row}")
    print(
        f"    device logs: {window.get('queued_at', '-')} .. "
        f"{window.get('finished_at', 'now')}"
    )
    print(f"    look up    : AI Action Plans / Push History for {device_id}")


def print_failures(records: List[Dict[str, Any]], device_id: str) -> None:
    """Print the closing section: commands that need a human look."""
    problem_records = [
        record
        for record in records
        if record["outcome"]
        in (OUTCOME_FAIL, OUTCOME_TIMEOUT, OUTCOME_BLOCKED, OUTCOME_NOTE)
    ]
    if not problem_records:
        print("\nNo failures to investigate.")
        return

    print("\nCOMMANDS THAT NEED A LOOK")
    print("-" * 78)
    for record in problem_records:
        print_failure_detail(record, device_id)
        print()


def print_timings(records: List[Dict[str, Any]]) -> None:
    """Print per-command latency: query -> execute -> terminal."""
    print("\nTIMINGS (seconds)")
    print("-" * 78)
    print(
        f"{'#':>3}  {'tier':4s}  {'action':26s}  "
        f"{'query':>7s} {'total':>8s} {'plan_status':>12s}"
    )
    for record in records:
        timings = record["timings"]

        def cell(value: Optional[float]) -> str:
            return "-" if value is None else f"{value:.1f}"

        print(
            f"{record['index']:>3}  {record['tier']:4s}  "
            f"{record['action']:26s}  "
            f"{cell(timings.get('query_s')):>7s} "
            f"{cell(timings.get('total_s')):>8s} "
            f"{str(record.get('plan_status') or ''):>12s}"
        )


def print_readiness(
    device: Dict[str, Any], problems: List[str], warnings: List[str]
) -> None:
    """Print the preflight block: what the device is and what it may do."""
    print(f"\nReadiness: {device.get('name') or device.get('device_id')}")
    print(f"  lifecycle_state : {device.get('lifecycle_state')}")
    print(f"  connectivity    : {device.get('connectivity_state') or '(unknown)'}")
    print(f"  last_seen       : {device.get('last_seen')}")
    print(f"  agent_restarts  : {device.get('agent_restart_count')}")
    permissions = device.get("device_permissions")
    granted = sorted(key for key, value in (permissions or {}).items() if value is True)
    print(f"  grants          : {', '.join(granted) or '(none)'}")
    for warning in warnings:
        print(f"  warning         : {warning}")
    for problem in problems:
        print(f"  problem         : {problem}")


def summarize(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count records per outcome."""
    counts: Dict[str, int] = {}
    for record in records:
        counts[record["outcome"]] = counts.get(record["outcome"], 0) + 1
    return counts


# --- Entry point ------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse and validate the command line."""
    ap = argparse.ArgumentParser(description="AI-delegation soak test.")
    ap.add_argument("--base-url", default="https://homepot.cabera.com/api/v1")
    ap.add_argument("--email")
    ap.add_argument(
        "--password",
        help="Prefer the HOMEPOT_PASSWORD env var or the prompt; inline values "
        "land in shell history and process listings.",
    )
    ap.add_argument("--device-id")
    ap.add_argument(
        "--provider",
        choices=("ollama", "openai", "anthropic"),
        help="LLM provider to pin for the run. Switches the server via "
        "PUT /ai/provider (admin only) when it differs; when omitted the run "
        "records whatever provider is already active.",
    )
    ap.add_argument(
        "--poll-interval", type=int, default=5, help="Seconds between status polls"
    )
    ap.add_argument(
        "--settle-delay", type=int, default=5, help="Seconds between commands"
    )
    ap.add_argument(
        "--query-timeout",
        type=int,
        default=300,
        help="Seconds to wait for each AI query (the LLM can be slow on CPU)",
    )
    ap.add_argument(
        "--restart-wait",
        type=int,
        default=180,
        help="Seconds to wait for the agent to check back in after restart_agent",
    )
    default_output = (
        "soak-runs/ai-soak-results-"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    ap.add_argument(
        "--output",
        default=default_output,
        help="Evidence JSON path (default: a timestamped file under soak-runs/)",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Run even when the readiness checks fail",
    )
    ap.add_argument(
        "--list", action="store_true", help="Print the delegated list and exit"
    )
    args = ap.parse_args()

    if not args.list and not (args.email and args.device_id):
        ap.error("--email and --device-id are required (unless --list)")
    return args


def print_command_list() -> None:
    """Print the delegated command set without sending anything."""
    print(f"{'#':>2}  {'tier':4s}  {'action':28s}  {'timeout':>7s}  prompt")
    for i, cmd in enumerate(SOAK_COMMANDS, 1):
        print(
            f"{i:>2}  {action_tier(cmd['action']):4s}  "
            f"{cmd['action']:28s}  {cmd['timeout']:>6}s  {cmd['prompt']}"
        )


def resolve_password(args: argparse.Namespace) -> str:
    """Take the password from argv, the environment, or an interactive prompt."""
    return (
        args.password
        or os.environ.get("HOMEPOT_PASSWORD")
        or getpass.getpass(f"Password for {args.email}: ")
    )


def run_sequence(
    client: httpx.Client,
    base_url: str,
    device_id: str,
    args: argparse.Namespace,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Run every delegated command in order.

    Returns the evidence records and, when a command broke the run, the reason
    the rest were skipped. Nothing here aborts on a single command failure.
    """
    records: List[Dict[str, Any]] = []
    abort_reason: Optional[str] = None

    for index, spec in enumerate(SOAK_COMMANDS, 1):
        if abort_reason is not None:
            skipped = new_record(
                index,
                spec["action"],
                spec["label"],
                str(spec["prompt"]).format(device=device_id),
            )
            skipped["outcome"] = OUTCOME_SKIPPED
            skipped["notes"].append(f"not run: {abort_reason}")
            records.append(skipped)
            continue

        print(f"[{index}/{len(SOAK_COMMANDS)}] {spec['label']} ({spec['action']})")
        record = run_one(client, base_url, device_id, index, spec, args)
        records.append(record)
        print(
            f"  {record['outcome']}"
            f"  plan={record.get('plan_id') or '-'}"
            f"  status={record.get('plan_status')}"
            f"  {format_elapsed(record['timings'].get('total_s'))}"
        )

        # An agent restart is the only step whose success the command itself
        # cannot prove: it returns before the process actually exits.
        if spec.get("verify_agent") and record["outcome"] == OUTCOME_PASS:
            abort_reason = verify_restart(
                client, base_url, device_id, record, int(args.restart_wait)
            )

        if abort_reason is None:
            time.sleep(int(spec.get("settle", args.settle_delay)))

    return records, abort_reason


def print_report(
    records: List[Dict[str, Any]], device_id: str, wall_seconds: float
) -> None:
    """Print the evidence table, timings and the closing failure section."""
    counts = summarize(records)
    print("\n" + "=" * 78)
    print(f"AI DELEGATION SOAK TEST — {device_id}")
    print("=" * 78)
    print_table(records)
    print("-" * 78)
    print(
        f"TOTAL {len(records)} | "
        + " | ".join(f"{name} {count}" for name, count in sorted(counts.items()))
        + f" | wall clock {wall_seconds}s"
    )
    print_timings(records)
    print_failures(records, device_id)


def write_evidence(
    path: str,
    device_id: str,
    base_url: str,
    records: List[Dict[str, Any]],
    counts: Dict[str, int],
    wall_seconds: float,
    provider: str,
    model: str,
) -> None:
    """Write the full evidence bundle so a failure can be reviewed later."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "device_id": device_id,
                "base_url": base_url,
                "provider": provider,
                "model": model,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "wall_seconds": wall_seconds,
                "counts": counts,
                "records": records,
            },
            handle,
            indent=2,
            default=str,
        )
    print(f"Evidence written to {path}")


def main() -> int:
    """Run the AI-delegation soak test and print an evidence summary."""
    args = parse_args()
    if args.list:
        print_command_list()
        return 0

    password = resolve_password(args)
    base_url = args.base_url.rstrip("/")
    run_started = time.monotonic()

    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        try:
            login(client, base_url, args.email, password)
        except Exception as exc:  # noqa: BLE001 - nothing to report without auth
            print(f"Login failed: {exc}")
            return 1
        print(f"Logged in. Device: {args.device_id}")

        provider, model = resolve_provider(client, base_url, args.provider)
        print(f"LLM provider: {provider} (model: {model})")

        try:
            device = get_device(client, base_url, args.device_id)
        except Exception as exc:  # noqa: BLE001 - preflight failure is fatal
            print(f"Could not read device state: {exc}")
            return 1

        ready, problems, warnings = evaluate_readiness(device, SOAK_COMMANDS)
        print_readiness(device, problems, warnings)
        if not ready and not args.force:
            print("\nAborting before sending anything. Fix the above or pass --force.")
            return 1
        print()

        records, _ = run_sequence(client, base_url, args.device_id, args)

    wall_seconds = round(time.monotonic() - run_started, 1)
    counts = summarize(records)
    print_report(records, args.device_id, wall_seconds)
    write_evidence(
        args.output,
        args.device_id,
        base_url,
        records,
        counts,
        wall_seconds,
        provider,
        model,
    )

    blocking = (
        counts.get(OUTCOME_FAIL, 0)
        + counts.get(OUTCOME_TIMEOUT, 0)
        + counts.get(OUTCOME_BLOCKED, 0)
    )
    return 0 if blocking == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
