#!/usr/bin/env python3
r"""Compose-command soak test for a single device (no AI).

Sends each compose command directly via the device-command API, waits for the
command lifecycle to reach a terminal status, then records pass/fail. Commands
run strictly sequentially; a settle delay after each command (longer after
``restart_agent``) gives the agent time to recover before the next command.

Disruptive commands are excluded by design (see ``SOAK_COMMANDS``): ``restart``,
``shutdown``, ``lock_screen``, ``update_app``, ``rollback_app``,
``upgrade_all_programs`` and ``disk_cleanup``. This keeps the device logged in
(the operator's PIN is never needed) and avoids touching files the operator
cares about on their own machine.

Usage:
    python tools/compose-soak-test.py \\
        --base-url https://homepot.cabera.com/api/v1 \\
        --email maziar.ghorbani@brunel.ac.uk --password '...' \\
        --device-id DEVICE-HSZK-T24Y-TSCX

    # Preview only (prints the command list, sends nothing):
    python tools/compose-soak-test.py --list
"""

import argparse
import json
import sys
import time
from typing import Any, Dict, List, Optional

import httpx

# Terminal command statuses: polling stops at any of these.
TERMINAL_STATUSES = {"completed", "failed", "expired", "cancelled"}

# (action, label, payload, timeout_seconds, settle_seconds)
# timeouts are generous on purpose (the winget commands are slow); settle is an
# extra pause after the command before the next one (longer for restart_agent).
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
        "action": "network_test",
        "label": "Network Test",
        "payload": {"host": "example.com", "timeout_seconds": 10},
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
        "action": "stop_program",
        "label": "Stop Program",
        "payload": {"name": "notepad.exe", "force": False},
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
        "settle": 30,
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


def login(client: httpx.Client, base_url: str, email: str, password: str) -> None:
    """Authenticate so the session cookie is set on the client."""
    r = client.post(
        f"{base_url}/auth/login", json={"email": email, "password": password}
    )
    r.raise_for_status()


def queue_command(
    client: httpx.Client,
    base_url: str,
    device_id: str,
    command_type: str,
    payload: Dict[str, Any],
) -> str:
    """Queue a command and return its command_id."""
    r = client.post(
        f"{base_url}/devices/{device_id}/commands",
        json={"command_type": command_type, "payload": payload},
    )
    r.raise_for_status()
    return r.json()["command_id"]


def get_command(
    client: httpx.Client, base_url: str, device_id: str, command_id: str
) -> Dict[str, Any]:
    """Fetch one command with its full result."""
    r = client.get(f"{base_url}/devices/device/{device_id}/commands/{command_id}")
    r.raise_for_status()
    return r.json()


def summarize_result(result: Optional[Dict[str, Any]]) -> str:
    """Extract a short human-readable note from a command result dict."""
    if not isinstance(result, dict):
        return ""
    if result.get("error"):
        return f"error={result['error']}"
    if result.get("message"):
        return f"message={result['message']}"
    if result.get("command_executed"):
        return f"executed={result['command_executed']}"
    if isinstance(result.get("count"), int):
        return f"count={result['count']}"
    return ""


def main() -> int:
    """Run the compose-command soak test and print a pass/fail summary."""
    ap = argparse.ArgumentParser(description="Compose-command soak test (no AI).")
    ap.add_argument("--base-url", default="https://homepot.cabera.com/api/v1")
    ap.add_argument("--email")
    ap.add_argument("--password")
    ap.add_argument("--device-id")
    ap.add_argument(
        "--poll-interval", type=int, default=5, help="Seconds between status polls"
    )
    ap.add_argument(
        "--settle-delay", type=int, default=5, help="Seconds between commands"
    )
    ap.add_argument("--output", default="compose_soak_results.json")
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

    if not (args.email and args.password and args.device_id):
        ap.error("--email, --password and --device-id are required (unless --list)")

    base_url = args.base_url.rstrip("/")
    results: List[Dict[str, Any]] = []

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        try:
            login(client, base_url, args.email, args.password)
        except Exception as e:
            print(f"Login failed: {e}")
            return 1
        print(f"Logged in. Device: {args.device_id}")

        for i, cmd in enumerate(SOAK_COMMANDS, 1):
            action = cmd["action"]
            label = cmd["label"]
            settle = cmd.get("settle", args.settle_delay)
            print(f"\n[{i}/{len(SOAK_COMMANDS)}] {label} ({action})")
            record: Dict[str, Any] = {
                "action": action,
                "label": label,
                "result": "not_run",
            }
            try:
                command_id = queue_command(
                    client, base_url, args.device_id, action, cmd["payload"]
                )
                record["command_id"] = command_id
                print(f"  queued: {command_id}")

                # Poll until a terminal status or the per-command timeout.
                deadline = time.time() + cmd["timeout"]
                final_status: Optional[str] = None
                final_result: Optional[Dict[str, Any]] = None
                while time.time() < deadline:
                    detail = get_command(client, base_url, args.device_id, command_id)
                    final_status = detail.get("status")
                    final_result = detail.get("result")
                    if final_status in TERMINAL_STATUSES:
                        break
                    time.sleep(args.poll_interval)

                if final_status not in TERMINAL_STATUSES:
                    record["result"] = "timeout"
                    print(
                        f"  TIMEOUT after {cmd['timeout']}s (last status={final_status})"
                    )
                elif final_status == "completed":
                    record["result"] = "PASS"
                    note = summarize_result(final_result)
                    print("  PASS (completed)" + (f" — {note}" if note else ""))
                else:
                    record["result"] = "FAIL"
                    note = summarize_result(final_result)
                    print(f"  FAIL ({final_status})" + (f" — {note}" if note else ""))
                record["status"] = final_status
                record["note"] = summarize_result(final_result)
            except Exception as e:
                record["result"] = "error"
                record["error"] = str(e)
                print(f"  ERROR: {e}")
            results.append(record)

            # Settle before the next command so an agent/service restart can
            # finish before the next command is queued.
            time.sleep(settle)

    # Summary table.
    print("\n" + "=" * 90)
    print("COMPOSE SOAK TEST SUMMARY")
    print("=" * 90)
    passed = failed = 0
    for r in results:
        mark = r["result"]
        if mark == "PASS":
            passed += 1
        elif mark in ("FAIL", "timeout", "error"):
            failed += 1
        note = r.get("note") or r.get("error") or ""
        print(f"{r['label']:36s} {mark:8s}  {note}")
    print("-" * 90)
    print(f"TOTAL {len(results)} | PASS {passed} | FAIL/OTHER {failed}")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults written to {args.output}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
