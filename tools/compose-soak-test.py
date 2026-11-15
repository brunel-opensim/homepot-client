#!/usr/bin/env python3
r"""Compose-command soak test for a single device (no AI).

This automates the loop an operator otherwise runs by hand in the dashboard:

1. send the command from the Compose Command page,
2. wait for it to execute on the device,
3. read the device's Live Logs,
4. confirm the command and its result in Push History.

Every one of those steps becomes an assertion, so a run produces evidence
instead of a status line to eyeball:

=========  ==================================================================
accepted   the API queued the command (HTTP 201, ``command_id`` returned)
delivered  ``sent_at`` is set, so the device polled and acknowledged it
executed   ``executed_at`` is set and the status is terminal
history    Push History lists the command with the same status polling saw
audit      ``command_queued`` -> ``command_sent`` -> ``command_completed``
           appears in the device audit log for this command
errors     no *new* Live Logs rows appeared inside the command's window
=========  ==================================================================

Each command additionally records timings (queued -> sent -> executed ->
observed), which is the actual "soak" signal: it shows latency drifting
across a long run, especially after ``restart_agent``.

Failure policy
--------------
A single failing command never stops the run: all 24 are exercised, then the
report ends with an explicit "failures to investigate" section listing the
command ids, which checks failed, the agent's result, and the Live Logs time
window to compare against. The only early exit is when the device stops
polling after ``restart_agent`` — the remaining commands are then marked
``SKIPPED`` and the run still ends with the same report.

Disruptive commands are excluded by design (see ``SOAK_COMMANDS``):
``restart``, ``shutdown``, ``lock_screen``, ``update_app``, ``rollback_app``,
``upgrade_all_programs`` and ``disk_cleanup``. This keeps the device logged in
(the operator's PIN is never needed) and avoids touching files they care about.

Known side effects on the operator's own machine: ``update_config`` leaves the
volume at 50 and the brightness at 75, ``notify_user`` pops a modal on screen,
and ``start_program``/``stop_program`` open and close Notepad. The stop step
targets the PID returned by the start step, so a Notepad window the operator
already had open is never touched.

Usage:
    HOMEPOT_PASSWORD='...' python tools/compose-soak-test.py \\
        --base-url https://homepot.cabera.com/api/v1 \\
        --email maziar.ghorbani@brunel.ac.uk \\
        --device-id DEVICE-HSZK-T24Y-TSCX

    # Preview only (prints the command list, sends nothing):
    python tools/compose-soak-test.py --list
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

# Terminal command statuses: polling stops at any of these.
TERMINAL_STATUSES = {"completed", "failed", "expired", "cancelled"}

# Command and audit timestamps are written by the server, while window edges are
# taken on this machine. A little clock skew between the two must not make a
# correctly recorded command look missing.
CLOCK_SKEW_TOLERANCE_S = 300

# Outcomes reported for one command.
OUTCOME_PASS = "PASS"
OUTCOME_NOTE = "PASS_NOTE"
OUTCOME_FAIL = "FAIL"
OUTCOME_BLOCKED = "BLOCKED"
OUTCOME_TIMEOUT = "TIMEOUT"
OUTCOME_SKIPPED = "SKIPPED"

# Device grant each command type is gated on. Mirrors REQUIRED_PERMISSION in
# backend/src/homepot/agent/utils/command_poller.py; the queue endpoint rejects
# a command with 403 before it is ever stored when the grant is missing.
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

# Result keys the agent returns for a successful execution. Used to catch a
# command that reports "completed" with an empty or malformed result.
EXPECTED_RESULT_KEYS: Dict[str, Tuple[str, ...]] = {
    "health_check": ("results",),
    "list_processes": ("processes", "count"),
    "list_connections": ("connections", "count"),
    "list_drives": ("drives", "count"),
    "tail_system_log": ("events", "count"),
    "network_test": ("results",),
    "list_sessions": ("sessions", "count"),
    "get_system_info": ("hostname", "os"),
    "collect_support_bundle": ("path", "file_count"),
    "list_installed_programs": ("programs", "count"),
    "scan_filesystem": ("entries", "count"),
    "notify_user": ("message",),
    "update_config": ("applied_keys", "results"),
    "run_command_unprivileged": ("exit_code", "stdout"),
    "start_program": ("pid",),
    "stop_program": ("killed",),
    "set_service_state": ("exit_code",),
    "restart_service": ("exit_code",),
    "run_command": ("exit_code", "stdout"),
    "run_script": ("exit_code", "stdout"),
    "install_program": ("exit_code",),
    "update_program": ("exit_code",),
    "uninstall_program": ("exit_code",),
}

# These report status="failed" when a sub-test verdict fails, not when the
# command itself failed to run. They are scored as executed + verdict instead
# of pass/fail, otherwise a busy laptop reads as a broken command.
VERDICT_ACTIONS = {"health_check", "network_test"}

# (action, label, payload, timeout_seconds, settle_seconds)
# timeouts are generous on purpose (the winget commands are slow); settle is an
# extra pause after the command before the next one (longer for restart_agent).
# The "$PID" placeholder is replaced with the pid returned by start_program.
SOAK_COMMANDS: List[Dict[str, Any]] = [
    # --- T1 read-only diagnostics ---
    {
        "action": "health_check",
        "label": "Health Check",
        "payload": {"tests": ["network", "storage", "memory"]},
        "timeout": 300,
    },
    {
        "action": "list_processes",
        "label": "List Processes",
        "payload": {"max_results": 50, "sort_by": "cpu", "include_memory": True},
        "timeout": 300,
    },
    {
        "action": "list_connections",
        "label": "List Connections",
        "payload": {"filter_state": "ESTABLISHED", "limit": 100},
        "timeout": 300,
    },
    {"action": "list_drives", "label": "List Drives", "payload": {}, "timeout": 300},
    {
        "action": "tail_system_log",
        "label": "Tail System Log",
        "payload": {"lines": 50},
        "timeout": 300,
    },
    {
        # The device already reaches the platform, so this host plus a TCP 443
        # probe is a far more reliable signal than ICMP to an external site.
        "action": "network_test",
        "label": "Network Test",
        "payload": {"host": "homepot.cabera.com", "port": 443, "timeout_seconds": 10},
        "timeout": 300,
    },
    {
        "action": "list_sessions",
        "label": "List Sessions",
        "payload": {},
        "timeout": 300,
    },
    {
        "action": "get_system_info",
        "label": "Get System Info",
        "payload": {},
        "timeout": 300,
    },
    {
        "action": "collect_support_bundle",
        "label": "Collect Support Bundle",
        "payload": {},
        "timeout": 300,
    },
    {
        "action": "list_installed_programs",
        "label": "List Installed Programs",
        "payload": {},
        "timeout": 300,
    },
    {
        "action": "scan_filesystem",
        "label": "Scan Filesystem",
        "payload": {"path": "C:\\ProgramData", "max_depth": 2, "include_sizes": True},
        "timeout": 300,
    },
    # --- T2 reversible control ---
    {
        "action": "notify_user",
        "label": "Notify User",
        "payload": {"title": "HOMEPOT Soak Test", "message": "Soak-test notification."},
        "timeout": 300,
    },
    {
        "action": "update_config",
        "label": "Update Config",
        "payload": {"volume": 50, "brightness": 75},
        "timeout": 300,
    },
    {
        "action": "run_command_unprivileged",
        "label": "Run Command (Unprivileged)",
        "payload": {"command": "ipconfig", "timeout_seconds": 30},
        "timeout": 300,
    },
    {
        "action": "start_program",
        "label": "Start Program",
        "payload": {"path": "notepad.exe", "args": []},
        "timeout": 300,
    },
    {
        # Stops only the pid captured from start_program, so a Notepad window
        # the operator already has open with unsaved text is left alone.
        "action": "stop_program",
        "label": "Stop Program (started pid)",
        "payload": {"pid": "$PID", "force": False},
        "timeout": 300,
    },
    {
        "action": "set_service_state",
        "label": "Set Service State (start Spooler)",
        "payload": {"service_name": "Spooler", "action": "start"},
        "timeout": 300,
    },
    # --- Service / agent restart (no PIN, recover quickly) ---
    {
        "action": "restart_service",
        "label": "Restart Service (Spooler)",
        "payload": {"service_name": "Spooler"},
        "timeout": 300,
    },
    {
        "action": "restart_agent",
        "label": "Restart Agent",
        "payload": {},
        "timeout": 300,
        "settle": 5,
        "verify_agent": True,
    },
    # --- Elevated commands with safe payloads ---
    {
        "action": "run_command",
        "label": "Run Command (systeminfo)",
        "payload": {"command": "systeminfo", "timeout_seconds": 60},
        "timeout": 300,
    },
    {
        "action": "run_script",
        "label": "Run Script (hostname)",
        "payload": {"script": "hostname", "timeout_seconds": 30},
        "timeout": 300,
    },
    # --- Winget (slow, network) — last ---
    {
        "action": "install_program",
        "label": "Install Program (Notepad++)",
        "payload": {"package": "Notepad++.Notepad++", "timeout_seconds": 300},
        "timeout": 900,
    },
    {
        "action": "update_program",
        "label": "Update Program (Notepad++)",
        "payload": {"package": "Notepad++.Notepad++", "timeout_seconds": 300},
        "timeout": 900,
    },
    {
        "action": "uninstall_program",
        "label": "Uninstall Program (Notepad++)",
        "payload": {"package": "Notepad++.Notepad++", "timeout_seconds": 300},
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


def queue_command(
    client: httpx.Client,
    base_url: str,
    device_id: str,
    command_type: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Queue a command and return the created command record."""
    r = client.post(
        f"{base_url}/devices/{device_id}/commands",
        json={"command_type": command_type, "payload": payload},
    )
    r.raise_for_status()
    created = r.json()
    return created if isinstance(created, dict) else {}


def get_command(
    client: httpx.Client, base_url: str, device_id: str, command_id: str
) -> Dict[str, Any]:
    """Fetch one command with its full result."""
    r = client.get(f"{base_url}/devices/device/{device_id}/commands/{command_id}")
    r.raise_for_status()
    detail = r.json()
    return detail if isinstance(detail, dict) else {}


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
    """Return recent Live Logs rows as stable fingerprint strings.

    Live Logs are populated by device error reporting, so a fetch failure is
    never fatal: an empty list simply disables the new-error comparison.
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
    return [
        "{0}|{1}|{2}".format(
            row.get("timestamp"),
            row.get("error_code"),
            str(row.get("error_message") or "")[:120],
        )
        for row in rows
        if isinstance(row, dict)
    ]


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
    """Like ``elapsed_seconds`` but never negative.

    The server stamps the events, the script stamps the request; when the two
    clocks disagree by a second the raw delta can come out slightly negative.
    Reporting "-0.4s" looks like a bug, so it is clamped at zero.
    """
    raw = elapsed_seconds(start, end)
    if raw is None:
        return None
    return max(0.0, raw)


def result_shape_problems(command_type: str, result: Any) -> List[str]:
    """Return why a command result looks wrong, or an empty list when fine."""
    if not isinstance(result, dict):
        return ["result is missing"]
    problems: List[str] = []
    if result.get("error"):
        problems.append(f"agent reported error: {result['error']}")
    for key in EXPECTED_RESULT_KEYS.get(command_type, ()):
        if key not in result:
            problems.append(f"result is missing '{key}'")
    return problems


def subtests_of(command_type: str, result: Any) -> Tuple[Optional[str], Dict[str, Any]]:
    """Return the pass/fail verdict and per-test detail for verdict commands."""
    if command_type not in VERDICT_ACTIONS or not isinstance(result, dict):
        return None, {}
    tests = result.get("results")
    if not isinstance(tests, dict) or not tests:
        return None, {}
    failed = {
        name: detail
        for name, detail in tests.items()
        if not isinstance(detail, dict) or detail.get("status") != "pass"
    }
    return ("pass" if not failed else "fail"), tests


def verify_history(
    history: List[Dict[str, Any]], command_id: str, status: Optional[str]
) -> Dict[str, Any]:
    """Check that Push History lists this command with the polled status."""
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

    ``command_sent`` and ``command_completed``/``command_failed`` descriptions
    carry the command id. ``command_queued`` does not, so it is correlated by
    command type inside the command's own time window (commands run strictly
    sequentially, so windows never overlap). The window is padded by
    ``CLOCK_SKEW_TOLERANCE_S`` because the event timestamps come from the
    server clock while the window edges come from this machine.
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
            if command_type not in str(event.get("description") or ""):
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


def wait_for_agent_recovery(
    client: httpx.Client,
    base_url: str,
    device_id: str,
    since: Optional[datetime],
    restart_count_before: Any,
    timeout: int,
) -> Dict[str, Any]:
    """Poll the device until it checks in again after an agent restart.

    A failed restart would otherwise cost the full timeout of every remaining
    command (the winget trio alone is 45 minutes), so this is the one place the
    run gives up early.
    """
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        try:
            device = get_device(client, base_url, device_id)
        except Exception:  # noqa: BLE001 - transient errors while it restarts
            time.sleep(5)
            continue
        last_seen = parse_timestamp(device.get("last_seen"))
        restart_count = device.get("agent_restart_count")
        recovered = last_seen is not None and since is not None and last_seen > since
        if (
            isinstance(restart_count, int)
            and isinstance(restart_count_before, int)
            and restart_count > restart_count_before
        ):
            recovered = True
        if recovered:
            return {
                "recovered": True,
                "waited_s": round(time.monotonic() - started, 1),
                "last_seen": device.get("last_seen"),
                "agent_restart_count": restart_count,
            }
        time.sleep(5)
    return {"recovered": False, "waited_s": round(time.monotonic() - started, 1)}


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


def run_one(
    client: httpx.Client,
    base_url: str,
    device_id: str,
    index: int,
    spec: Dict[str, Any],
    state: Dict[str, Any],
    args: argparse.Namespace,
) -> Dict[str, Any]:
    """Exercise a single command end to end and return its evidence record."""
    action = str(spec["action"])
    label = str(spec["label"])
    payload = dict(spec.get("payload") or {})

    record: Dict[str, Any] = {
        "index": index,
        "action": action,
        "label": label,
        "payload": payload,
        "command_id": None,
        "status": None,
        "outcome": OUTCOME_FAIL,
        "checks": {
            "accepted": False,
            "delivered": False,
            "executed": False,
            "result_shape": False,
            "history": False,
            "audit": False,
        },
        "verdict": None,
        "subtests": {},
        "timings": {},
        "new_errors": [],
        "notes": [],
        "result": None,
        "window": {},
    }

    # A $-prefixed payload value is filled from an earlier command's result.
    for key, value in list(payload.items()):
        if value == "$PID":
            captured = state.get("last_started_pid")
            if captured is None:
                record["outcome"] = OUTCOME_SKIPPED
                record["notes"].append("start_program returned no pid to stop")
                return record
            payload[key] = captured
            record["payload"] = payload

    errors_before = error_fingerprints(client, base_url, device_id)
    queued_at = datetime.now(timezone.utc)
    started = time.monotonic()

    try:
        created = queue_command(client, base_url, device_id, action, payload)
    except httpx.HTTPStatusError as exc:
        body: Any = None
        try:
            body = exc.response.json().get("detail")
        except Exception:  # noqa: BLE001 - error body is best effort
            body = exc.response.text[:400]
        record["http_status"] = exc.response.status_code
        record["detail"] = body
        if exc.response.status_code in (400, 403, 422):
            record["outcome"] = OUTCOME_BLOCKED
            record["notes"].append(f"queue rejected ({exc.response.status_code})")
        else:
            record["outcome"] = OUTCOME_FAIL
            record["notes"].append(f"queue failed ({exc.response.status_code})")
        record["timings"] = {"total_s": round(time.monotonic() - started, 1)}
        record["window"] = {"queued_at": queued_at.isoformat()}
        return record
    except Exception as exc:  # noqa: BLE001 - network errors are recorded, not raised
        record["outcome"] = OUTCOME_FAIL
        record["notes"].append(f"queue error: {exc}")
        record["timings"] = {"total_s": round(time.monotonic() - started, 1)}
        record["window"] = {"queued_at": queued_at.isoformat()}
        return record

    command_id = str(created.get("command_id") or "")
    record["command_id"] = command_id
    record["checks"]["accepted"] = bool(command_id)
    if not command_id:
        record["notes"].append("queue response had no command_id")
        return record

    # Poll until a terminal status or the per-command timeout.
    deadline = time.monotonic() + int(spec["timeout"])
    detail: Dict[str, Any] = {}
    polled_errors = 0
    while time.monotonic() < deadline:
        try:
            detail = get_command(client, base_url, device_id, command_id)
        except Exception as exc:  # noqa: BLE001 - retry until the deadline
            # A device that stops polling can produce one error per attempt for
            # the whole timeout, so only the first few are recorded.
            polled_errors += 1
            if polled_errors <= 3:
                record["notes"].append(f"poll error: {exc}")
            time.sleep(args.poll_interval)
            continue
        if detail.get("status") in TERMINAL_STATUSES:
            break
        time.sleep(args.poll_interval)

    finished_at = datetime.now(timezone.utc)
    status = detail.get("status")
    result = detail.get("result")
    record["status"] = status
    record["result"] = result
    record["sent_at"] = detail.get("sent_at")
    record["executed_at"] = detail.get("executed_at")
    record["window"] = {
        "queued_at": queued_at.isoformat(),
        "finished_at": finished_at.isoformat(),
    }

    timed_out = status not in TERMINAL_STATUSES
    record["checks"]["delivered"] = parse_timestamp(detail.get("sent_at")) is not None
    record["checks"]["executed"] = (
        parse_timestamp(detail.get("executed_at")) is not None
    )
    problems = result_shape_problems(action, result)
    record["checks"]["result_shape"] = not problems and result is not None
    record["notes"].extend(problems)

    verdict, subtests = subtests_of(action, result)
    record["verdict"] = verdict
    record["subtests"] = subtests

    # Push History: the command must be listed with the status polling saw.
    try:
        history = get_history(client, base_url, device_id)
    except Exception as exc:  # noqa: BLE001 - report, do not lose the run
        history = []
        record["notes"].append(f"history fetch failed: {exc}")
    record["history"] = verify_history(history, command_id, status)
    record["checks"]["history"] = bool(record["history"]["ok"])

    # Audit trail: queued -> sent -> terminal for this command id.
    try:
        events = get_audit_events(client, base_url, device_id)
    except Exception as exc:  # noqa: BLE001 - report, do not lose the run
        events = []
        record["notes"].append(f"audit fetch failed: {exc}")
    record["audit"] = verify_audit(
        events,
        command_id,
        action,
        queued_at,
        finished_at,
        expect_sent=record["checks"]["delivered"],
        expect_terminal=not timed_out,
    )
    record["checks"]["audit"] = bool(record["audit"]["ok"])

    # New Live Logs rows inside this command's window are a lead, not a verdict:
    # device error reporting lags, and winget legitimately emits warnings.
    errors_after = error_fingerprints(client, base_url, device_id)
    if errors_before and errors_after:
        seen = set(errors_before)
        record["new_errors"] = [row for row in errors_after if row not in seen]

    record["timings"] = {
        "queued_to_sent_s": clamped_seconds(
            queued_at.isoformat(), detail.get("sent_at")
        ),
        "sent_to_executed_s": clamped_seconds(
            detail.get("sent_at"), detail.get("executed_at")
        ),
        "executed_to_observed_s": clamped_seconds(
            detail.get("executed_at"), finished_at.isoformat()
        ),
        "total_s": round(time.monotonic() - started, 1),
    }

    skew = elapsed_seconds(finished_at.isoformat(), detail.get("executed_at"))
    if skew is not None and skew < -5:
        record["notes"].append(
            f"clock skew: the device's executed_at is {-skew:.0f}s ahead of this host"
        )

    record["outcome"] = classify_outcome(record, timed_out)

    if action == "start_program" and isinstance(result, dict):
        pid = result.get("pid")
        if isinstance(pid, int) and pid > 0:
            state["last_started_pid"] = pid

    return record


def classify_outcome(record: Dict[str, Any], timed_out: bool) -> str:
    """Map a command's evidence onto one of the reported outcomes."""
    checks = record["checks"]
    if timed_out:
        return OUTCOME_TIMEOUT
    core_ok = all(
        checks[name]
        for name in ("accepted", "delivered", "executed", "history", "audit")
    )
    if not core_ok or not checks["result_shape"]:
        return OUTCOME_FAIL
    if record["action"] in VERDICT_ACTIONS:
        # The command ran; the sub-test verdict is reported separately.
        return OUTCOME_PASS if record["verdict"] == "pass" else OUTCOME_NOTE
    if record["status"] != "completed":
        return OUTCOME_FAIL
    if record["new_errors"]:
        return OUTCOME_NOTE
    return OUTCOME_PASS


# --- Reporting --------------------------------------------------------------


def format_elapsed(seconds: Optional[float]) -> str:
    """Render an elapsed time compactly for the table."""
    if seconds is None:
        return "-"
    return f"{seconds:.1f}s"


def print_table(records: List[Dict[str, Any]]) -> None:
    """Print one evidence row per command."""
    print(
        f"{'#':>3}  {'action':26s}  {'accept':6s} {'deliv':5s} {'exec':4s} "
        f"{'hist':4s} {'audit':5s} {'err':>3s} {'elapsed':>8s}  outcome"
    )
    for record in records:
        checks = record["checks"]
        if record["outcome"] == OUTCOME_SKIPPED:
            print(
                f"{record['index']:>3}  {record['action']:26s}  {'':46s} {OUTCOME_SKIPPED}"
            )
            continue

        def mark(name: str) -> str:
            return "ok" if checks.get(name) else "--"

        print(
            f"{record['index']:>3}  {record['action']:26s}  "
            f"{mark('accepted'):6s} {mark('delivered'):5s} {mark('executed'):4s} "
            f"{mark('history'):4s} {mark('audit'):5s} "
            f"{len(record['new_errors']):>3d} "
            f"{format_elapsed(record['timings'].get('total_s')):>8s}  "
            f"{record['outcome']}"
        )


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
        window = record.get("window") or {}
        print(
            f"#{record['index']} {record['action']} ({record['label']}) — "
            f"{record['outcome']}"
        )
        print(f"    command_id : {record.get('command_id') or '(never queued)'}")
        if record.get("status"):
            print(f"    status     : {record['status']}")
        if record.get("verdict"):
            failed = [
                name
                for name, detail in record["subtests"].items()
                if not isinstance(detail, dict) or detail.get("status") != "pass"
            ]
            print(f"    verdict    : {record['verdict']} (failed: {', '.join(failed)})")
        checks = ", ".join(
            f"{name}={'ok' if value else 'no'}"
            for name, value in record["checks"].items()
        )
        print(f"    checks     : {checks}")
        if record.get("history") and not record["history"].get("ok"):
            print(
                "    history    : listed={listed} status={status} "
                "result_present={result_present}".format(**record["history"])
            )
        if record.get("audit") and not record["audit"].get("ok"):
            print(
                "    audit      : queued={queued} sent={sent} "
                "terminal={terminal}".format(**record["audit"])
            )
        for note in record.get("notes") or []:
            print(f"    note       : {note}")
        if record.get("detail"):
            print(f"    api detail : {json.dumps(record['detail'])[:400]}")
        if record.get("result") is not None:
            print(f"    result     : {json.dumps(record['result'])[:500]}")
        for row in record["new_errors"][:5]:
            print(f"    new log    : {row}")
        if window.get("queued_at"):
            print(
                f"    device logs: {window['queued_at']} .. "
                f"{window.get('finished_at', 'now')}"
            )
        print(f"    look up    : Push History / Live Logs for device {device_id}")
        print()


def print_timings(records: List[Dict[str, Any]]) -> None:
    """Print delivery and execution latency per command."""
    print("\nTIMINGS (seconds)")
    print("-" * 78)
    print(
        f"{'#':>3}  {'action':26s}  {'q->sent':>8s} {'sent->exec':>10s} "
        f"{'exec->seen':>10s} {'total':>8s}"
    )
    for record in records:
        timings = record["timings"]

        def cell(value: Optional[float]) -> str:
            return "-" if value is None else f"{value:.1f}"

        print(
            f"{record['index']:>3}  {record['action']:26s}  "
            f"{cell(timings.get('queued_to_sent_s')):>8s} "
            f"{cell(timings.get('sent_to_executed_s')):>10s} "
            f"{cell(timings.get('executed_to_observed_s')):>10s} "
            f"{cell(timings.get('total_s')):>8s}"
        )


def summarize(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count records per outcome."""
    counts: Dict[str, int] = {}
    for record in records:
        counts[record["outcome"]] = counts.get(record["outcome"], 0) + 1
    return counts


# --- Entry point ------------------------------------------------------------


def main() -> int:
    """Run the compose-command soak test and print an evidence summary."""
    ap = argparse.ArgumentParser(description="Compose-command soak test (no AI).")
    ap.add_argument("--base-url", default="https://homepot.cabera.com/api/v1")
    ap.add_argument("--email")
    ap.add_argument(
        "--password",
        help="Prefer the HOMEPOT_PASSWORD env var or the prompt; inline values "
        "land in shell history and process listings.",
    )
    ap.add_argument("--device-id")
    ap.add_argument(
        "--poll-interval", type=int, default=5, help="Seconds between status polls"
    )
    ap.add_argument(
        "--settle-delay", type=int, default=5, help="Seconds between commands"
    )
    ap.add_argument(
        "--restart-wait",
        type=int,
        default=180,
        help="Seconds to wait for the agent to check back in after restart_agent",
    )
    ap.add_argument(
        "--output", default="compose-soak-results.json", help="Evidence JSON path"
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Run even when the readiness checks fail",
    )
    ap.add_argument(
        "--list", action="store_true", help="Print the command list and exit"
    )
    args = ap.parse_args()

    if args.list:
        print(f"{'#':>2}  {'action':28s}  {'timeout':>7s}  payload")
        for i, cmd in enumerate(SOAK_COMMANDS, 1):
            print(
                f"{i:>2}  {cmd['action']:28s}  {cmd['timeout']:>6}s  "
                f"{json.dumps(cmd['payload'])}"
            )
        return 0

    if not (args.email and args.device_id):
        ap.error("--email and --device-id are required (unless --list)")

    password = args.password or os.environ.get("HOMEPOT_PASSWORD")
    if not password:
        password = getpass.getpass(f"Password for {args.email}: ")

    base_url = args.base_url.rstrip("/")
    records: List[Dict[str, Any]] = []
    state: Dict[str, Any] = {}
    run_started = time.monotonic()
    abort_reason: Optional[str] = None

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        try:
            login(client, base_url, args.email, password)
        except Exception as exc:  # noqa: BLE001 - nothing to report without auth
            print(f"Login failed: {exc}")
            return 1
        print(f"Logged in. Device: {args.device_id}")

        # Readiness: never spend two hours discovering the device is suspended
        # or that a grant is missing.
        try:
            device = get_device(client, base_url, args.device_id)
        except Exception as exc:  # noqa: BLE001 - preflight failure is fatal
            print(f"Could not read device state: {exc}")
            return 1

        ready, problems, warnings = evaluate_readiness(device, SOAK_COMMANDS)
        print(f"\nReadiness: {device.get('name') or args.device_id}")
        print(f"  lifecycle_state : {device.get('lifecycle_state')}")
        print(f"  last_seen       : {device.get('last_seen')}")
        print(f"  agent_restarts  : {device.get('agent_restart_count')}")
        permissions = device.get("device_permissions")
        granted = sorted(
            key for key, value in (permissions or {}).items() if value is True
        )
        print(f"  grants          : {', '.join(granted) or '(none)'}")
        for warning in warnings:
            print(f"  warning         : {warning}")
        for problem in problems:
            print(f"  problem         : {problem}")
        if not ready and not args.force:
            print("\nAborting before sending anything. Fix the above or pass --force.")
            return 1
        print()

        restart_count_before: Any = None

        for i, spec in enumerate(SOAK_COMMANDS, 1):
            if abort_reason is not None:
                records.append(
                    {
                        "index": i,
                        "action": spec["action"],
                        "label": spec["label"],
                        "payload": spec.get("payload") or {},
                        "command_id": None,
                        "outcome": OUTCOME_SKIPPED,
                        "checks": {},
                        "verdict": None,
                        "subtests": {},
                        "timings": {},
                        "new_errors": [],
                        "notes": [f"not run: {abort_reason}"],
                        "result": None,
                        "window": {},
                    }
                )
                continue

            # The restart probe compares server-stamped values only: last_seen
            # and agent_restart_count are written by the server, whereas the
            # command's executed_at comes from the device clock, so the two can
            # disagree by minutes on a skewed device.
            agent_baseline: Optional[datetime] = None
            if spec.get("verify_agent"):
                try:
                    snapshot = get_device(client, base_url, args.device_id)
                except Exception as exc:  # noqa: BLE001 - probe is best effort
                    print(f"  could not read agent baseline: {exc}")
                    snapshot = {}
                agent_baseline = parse_timestamp(snapshot.get("last_seen"))
                restart_count_before = snapshot.get("agent_restart_count")

            print(f"[{i}/{len(SOAK_COMMANDS)}] {spec['label']} ({spec['action']})")
            record = run_one(client, base_url, args.device_id, i, spec, state, args)
            records.append(record)
            print(
                f"  {record['outcome']}"
                f"  status={record.get('status')}"
                f"  {format_elapsed(record['timings'].get('total_s'))}"
                + (f"  verdict={record['verdict']}" if record.get("verdict") else "")
            )

            # An agent restart is the only step whose success the command
            # itself cannot prove: it returns before the process actually exits.
            if spec.get("verify_agent"):
                if agent_baseline is None and restart_count_before is None:
                    print("  no baseline to verify the restart against; skipping probe")
                else:
                    probe = wait_for_agent_recovery(
                        client,
                        base_url,
                        args.device_id,
                        agent_baseline,
                        restart_count_before,
                        args.restart_wait,
                    )
                    record["agent_recovery"] = probe
                    if probe["recovered"]:
                        print(f"  agent back after {probe['waited_s']}s")
                        restart_count_before = probe.get("agent_restart_count")
                    else:
                        abort_reason = (
                            f"agent did not check back in within "
                            f"{args.restart_wait}s after restart_agent"
                        )
                        record["outcome"] = OUTCOME_FAIL
                        record["notes"].append(abort_reason)
                        print(f"  {abort_reason}; remaining commands marked SKIPPED")

            if abort_reason is None:
                time.sleep(int(spec.get("settle", args.settle_delay)))

    wall_seconds = round(time.monotonic() - run_started, 1)
    counts = summarize(records)

    print("\n" + "=" * 78)
    print(f"COMPOSE SOAK TEST — {args.device_id}")
    print("=" * 78)
    print_table(records)
    print("-" * 78)
    print(
        f"TOTAL {len(records)} | "
        + " | ".join(f"{name} {count}" for name, count in sorted(counts.items()))
        + f" | wall clock {wall_seconds}s"
    )
    print_timings(records)
    print_failures(records, args.device_id)

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "device_id": args.device_id,
                "base_url": base_url,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "wall_seconds": wall_seconds,
                "counts": counts,
                "records": records,
            },
            handle,
            indent=2,
            default=str,
        )
    print(f"Evidence written to {args.output}")

    blocking = (
        counts.get(OUTCOME_FAIL, 0)
        + counts.get(OUTCOME_TIMEOUT, 0)
        + counts.get(OUTCOME_BLOCKED, 0)
    )
    return 0 if blocking == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
