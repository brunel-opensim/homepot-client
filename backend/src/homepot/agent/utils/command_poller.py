"""Command polling and processing for the real device agent."""

from datetime import datetime, timezone
import logging
import os
import platform
import shlex
import socket
import subprocess  # noqa: S404 - arguments are parsed and permission-gated
from typing import Any, Dict, List, Optional

import psutil

logger = logging.getLogger(__name__)

COMMAND_TYPES = frozenset(
    {
        "ping",
        "health_check",
        "request_permission",
        "restart",
        "run_command",
        "run_script",
        "shutdown",
        "status_request",
        "update_config",
        "list_processes",
        "list_connections",
        "scan_filesystem",
    }
)

# Each command type requires a specific device_permission key. Commands that
# execute, modify, or reboot/shut down the host system are gated on the
# owner-facing "root_access" grant; read-only management (diagnostics,
# monitoring) is gated on the "manage" group keys.
REQUIRED_PERMISSION: Dict[str, str] = {
    "health_check": "command_execution",
    "restart": "root_access",
    "run_command": "root_access",
    "run_script": "root_access",
    "shutdown": "root_access",
    "update_config": "root_access",
    "list_processes": "process_monitoring",
    "list_connections": "network_monitoring",
    "scan_filesystem": "root_access",
}

MAX_COMMAND_OUTPUT = 64 * 1024
MAX_COMMAND_TIMEOUT = 300


def _command_data(command: Dict[str, Any]) -> Dict[str, Any]:
    payload = command.get("payload")
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def required_permissions_for_command(
    command_type: str, payload: Optional[Dict[str, Any]] = None
) -> List[str]:
    """Return every user grant required to execute a command."""
    required: List[str] = []
    base_permission = REQUIRED_PERMISSION.get(command_type)
    if base_permission:
        required.append(base_permission)
    return required


def parse_pending_commands(response_data: Any) -> List[Dict[str, Any]]:
    """Parse the response from ``GET /api/v1/devices/pending`` into a list of commands.

    Accepts ``None``, a dict with a ``"commands"`` key, or a list directly.
    Returns an empty list when there are no pending commands.
    """
    if response_data is None:
        return []
    if isinstance(response_data, list):
        return [cmd for cmd in response_data if isinstance(cmd, dict)]
    if isinstance(response_data, dict):
        inner = response_data.get("commands")
        if isinstance(inner, list):
            return [cmd for cmd in inner if isinstance(cmd, dict)]
    return []


async def fetch_device_permissions(
    client: Any, config: Dict[str, Any], headers: Dict[str, str]
) -> Optional[Dict[str, bool]]:
    """Fetch the current ``device_permissions`` from the backend.

    Returns a dict like ``{"root_access": True, …}`` or ``None`` on failure.
    """
    device_id = config.get("device_id", "")
    url = f"{config['backend_url'].rstrip('/')}/api/v1/devices/device/{device_id}/permissions"
    try:
        resp = await client.get(url, headers=headers, timeout=5.0)
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data") or {}
        perms: Dict[str, bool] = data.get("permissions") or {}
        return perms
    except Exception as exc:
        logger.warning("Failed to fetch device permissions: %s", exc)
        return None


def _check_permission(
    command_type: str,
    permissions: Optional[Dict[str, bool]],
    payload: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Return an error message if the required permission is missing or ``False``.

    ``None`` means the command is allowed.
    """
    required_keys = required_permissions_for_command(command_type, payload)
    if not required_keys:
        return None
    if permissions is None:
        return "Device permissions not available — cannot verify access"
    missing = [key for key in required_keys if not permissions.get(key, False)]
    if missing:
        return (
            f"Permission denied: {', '.join(missing)} not granted for '{command_type}'"
        )
    return None


def _elevation_prefix() -> List[str]:
    """Return the argv prefix used to elevate a privileged command.

    On POSIX platforms the agent runs commands through non-interactive sudo
    (``sudo -n --``). On Windows there is no ``sudo`` — the agent typically
    runs as an elevated service — so no prefix is added. ``run_command``,
    ``run_script``, ``restart`` and ``shutdown`` all use this so they work on
    both families.
    """
    if os.name == "nt" or platform.system().lower() == "windows":
        return []
    return ["sudo", "-n", "--"]


def _shell_for_scripts() -> List[str]:
    """Return the argv for a script interpreter on the current platform."""
    if os.name == "nt" or platform.system().lower() == "windows":
        return ["powershell", "-NoProfile", "-NonInteractive", "-Command", "-"]
    return ["/bin/sh", "-s"]


def _execute_local(command: Dict[str, Any], script: bool) -> Dict[str, Any]:
    data = _command_data(command)
    source_key = "script" if script else "command"
    source = data.get(source_key)
    if not isinstance(source, str) or not source.strip():
        return {
            "status": "failed",
            "result": {"error": f"A non-empty '{source_key}' value is required"},
        }

    timeout_value = data.get("timeout_seconds", 30)
    try:
        timeout = max(1, min(int(timeout_value), MAX_COMMAND_TIMEOUT))
    except (TypeError, ValueError):
        return {
            "status": "failed",
            "result": {"error": "timeout_seconds must be an integer"},
        }

    # Command/script execution is always elevated: it is gated on the
    # root_access grant and runs through non-interactive sudo on POSIX
    # (or directly when the process already runs elevated, e.g. Windows
    # service).
    elevation = _elevation_prefix()
    if script:
        argv = [*elevation, *_shell_for_scripts()]
    else:
        try:
            argv = shlex.split(source)
        except ValueError as exc:
            return {"status": "failed", "result": {"error": str(exc)}}
        if not argv:
            return {
                "status": "failed",
                "result": {"error": "Command produced no executable arguments"},
            }
        argv = [*elevation, *argv]

    try:
        completed = subprocess.run(  # noqa: S603 - no shell; argv is explicit
            argv,
            input=source if script else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "failed", "result": {"error": str(exc)}}

    result = {
        "exit_code": completed.returncode,
        "stdout": completed.stdout[-MAX_COMMAND_OUTPUT:],
        "stderr": completed.stderr[-MAX_COMMAND_OUTPUT:],
    }
    return {
        "status": "completed" if completed.returncode == 0 else "failed",
        "result": result,
    }


def _run_argv(argv: List[str]) -> Dict[str, Any]:
    """Run an explicit argv list (no shell) and return a status dict."""
    try:
        completed = subprocess.run(  # noqa: S603 - explicit argv, no shell
            argv,
            capture_output=True,
            text=True,
            timeout=MAX_COMMAND_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "stdout": completed.stdout[-MAX_COMMAND_OUTPUT:],
        "stderr": completed.stderr[-MAX_COMMAND_OUTPUT:],
    }


# --- health_check -----------------------------------------------------------

_HEALTH_THRESHOLDS = {
    "cpu": 90.0,
    "memory": 90.0,
    "storage": 90.0,
}

_HEALTH_METRIC_KEYS = {
    "cpu": "cpu_usage",
    "memory": "memory_usage",
    "storage": "disk_usage",
}


def _run_health_check(data: Dict[str, Any]) -> Dict[str, Any]:
    """Run the requested diagnostics against the host and report pass/fail."""
    from homepot.agent.utils.telemetry import collect_system_telemetry

    requested = data.get("tests") or ["network", "storage", "memory"]
    if isinstance(requested, str):
        requested = [requested]
    metrics = collect_system_telemetry()

    results: Dict[str, Dict[str, Any]] = {}
    all_pass = True
    for test in requested:
        name = str(test)
        if name in _HEALTH_THRESHOLDS:
            value = metrics[_HEALTH_METRIC_KEYS[name]]
            passed = float(value) < _HEALTH_THRESHOLDS[name]
            results[name] = {"status": "pass" if passed else "fail", "value": value}
        elif name == "network":
            up = any(
                addr.family == socket.AF_INET
                and not (addr.address or "").startswith("127.")
                for iface in psutil.net_if_addrs().values()
                for addr in iface
            )
            results[name] = {
                "status": "pass" if up else "fail",
                "value": "ok" if up else "unreachable",
            }
        else:
            results[name] = {"status": "fail", "error": f"unknown test: {name}"}
        if results[name]["status"] != "pass":
            all_pass = False

    return {
        "status": "completed" if all_pass else "failed",
        "result": {
            "message": (
                "health check completed"
                if all_pass
                else "one or more diagnostics failed"
            ),
            "results": results,
        },
    }


# --- list_processes ---------------------------------------------------------


def _run_list_processes(data: Dict[str, Any]) -> Dict[str, Any]:
    """Snapshot running processes, sorted and limited like the Dashboard asks."""
    sort_by = str(data.get("sort_by") or "cpu")
    try:
        max_results = max(1, min(int(data.get("max_results", 50)), 500))
    except (TypeError, ValueError):
        max_results = 50
    include_memory = bool(data.get("include_memory", True))

    processes = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            processes.append(
                {
                    "pid": proc.info["pid"],
                    "name": proc.info["name"] or "",
                    "cpu": round(float(proc.info["cpu_percent"] or 0.0), 2),
                    "memory": (
                        round(float(proc.info["memory_percent"] or 0.0), 2)
                        if include_memory
                        else None
                    ),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    processes.sort(
        key=lambda p: p.get(sort_by, 0.0) if p.get(sort_by) is not None else 0.0,
        reverse=True,
    )
    return {
        "status": "completed",
        "result": {
            "count": len(processes),
            "processes": processes[:max_results],
        },
    }


# --- list_connections -------------------------------------------------------


def _run_list_connections(data: Dict[str, Any]) -> Dict[str, Any]:
    """Snapshot active network connections, optionally filtered by state."""
    filter_state = data.get("filter_state")
    try:
        limit = max(1, min(int(data.get("limit", 100)), 1000))
    except (TypeError, ValueError):
        limit = 100

    connections = []
    try:
        conns = psutil.net_connections(kind="inet")
    except (psutil.AccessDenied, OSError) as exc:
        return {
            "status": "failed",
            "result": {
                "error": f"connection listing requires elevated privileges: {exc}"
            },
        }

    for conn in conns:
        if filter_state and filter_state != "ALL" and conn.status != filter_state:
            continue
        connections.append(
            {
                "pid": conn.pid,
                "status": conn.status,
                "laddr": f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None,
                "raddr": f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None,
            }
        )

    return {
        "status": "completed",
        "result": {
            "count": len(connections),
            "connections": connections[:limit],
        },
    }


# --- scan_filesystem --------------------------------------------------------


def _run_scan_filesystem(data: Dict[str, Any]) -> Dict[str, Any]:
    """Walk the filesystem within a bounded depth/entry cap."""
    root = str(data.get("path") or "/")
    try:
        max_depth = max(1, min(int(data.get("max_depth", 2)), 10))
    except (TypeError, ValueError):
        max_depth = 2
    include_sizes = bool(data.get("include_sizes", True))
    max_entries = 200

    entries: List[Dict[str, Any]] = []

    def _entry(path: str, kind: str) -> Dict[str, Any]:
        entry: Dict[str, Any] = {"path": path, "type": kind}
        if include_sizes:
            try:
                entry["size"] = os.path.getsize(path)
            except OSError:
                entry["size"] = None
        return entry

    for base, dirs, files in os.walk(root, topdown=True):
        depth = base[len(root) :].count(os.sep)
        if depth >= max_depth:
            dirs[:] = []
        for name in dirs[: max_entries - len(entries)]:
            if len(entries) >= max_entries:
                break
            entries.append(_entry(os.path.join(base, name), "directory"))
        for name in files:
            if len(entries) >= max_entries:
                break
            entries.append(_entry(os.path.join(base, name), "file"))
        if len(entries) >= max_entries:
            break

    return {
        "status": "completed",
        "result": {
            "count": len(entries),
            "root": root,
            "truncated": len(entries) >= max_entries,
            "entries": entries,
        },
    }


# --- update_config (OS settings adapter) ------------------------------------


def _config_appliers(platform_name: str) -> Dict[str, Any]:
    """Return key -> argv builder for host settings that have a real OS action."""
    if platform_name == "darwin":
        return {
            "brightness": lambda value: ["brightness", str(int(value))],
            "volume": lambda value: [
                "osascript",
                "-e",
                f"set volume output volume {int(value)}",
            ],
        }
    return {
        "brightness": lambda value: ["brightnessctl", "set", f"{int(value)}%"],
        "volume": lambda value: ["amixer", "-q", "set", "Master", f"{int(value)}%"],
    }


def _apply_config(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Apply a config update; keys with a known OS action run it on the host."""
    new_config = payload if isinstance(payload, dict) else {}
    platform_name = platform.system().lower()
    appliers = _config_appliers(platform_name)

    applied_keys: List[str] = []
    results: Dict[str, Any] = {}
    for key, value in new_config.items():
        applier = appliers.get(key)
        if applier is None:
            applied_keys.append(key)
            results[key] = {"status": "acknowledged", "message": "no OS action defined"}
            continue
        try:
            outcome = _run_argv(applier(value))
            applied_keys.append(key)
            results[key] = {
                "status": "applied" if outcome["ok"] else "failed",
                **(outcome if not outcome["ok"] else {}),
            }
        except Exception as exc:  # noqa: BLE001 - report any applier failure
            applied_keys.append(key)
            results[key] = {"status": "error", "message": str(exc)}

    return {
        "status": "completed",
        "result": {
            "message": "config update applied",
            "applied_keys": applied_keys,
            "results": results,
        },
    }


# --- restart / shutdown -----------------------------------------------------


def _system_control(command_type: str) -> Dict[str, Any]:
    """Reboot or power off the host system via elevation on POSIX."""
    elevation = _elevation_prefix()
    if os.name == "nt" or platform.system().lower() == "windows":
        action = "/r /t 0" if command_type == "restart" else "/s /t 0"
        outcome = _run_argv(["shutdown", *shlex.split(action)])
    else:
        action = "-r" if command_type == "restart" else "-h"
        outcome = _run_argv([*elevation, "shutdown", action, "now"])
    if outcome["ok"]:
        return {
            "status": "completed",
            "result": {"message": f"{command_type} initiated"},
        }
    return {
        "status": "failed",
        "result": {
            "error": (
                f"{command_type} failed: "
                f"{outcome.get('stderr') or outcome.get('error') or outcome.get('exit_code')}"
            )
        },
    }


def process_command(
    command: Dict[str, Any],
    permissions: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    """Execute a single command locally and return a result dict.

    Parameters
    ----------
    permissions:
        Current device permissions dict (e.g. ``{"root_access": True, …}``).
        When ``None`` the agent has not yet fetched permissions — any
        privileged command is rejected with a "not available" error.

    Returns
    -------
    dict with keys ``command_id``, ``status`` (``"completed"`` or ``"failed"``),
    and optionally ``result``.
    """
    command_id = command.get("command_id", "")
    command_type = command.get("command_type", "")

    if command_type not in COMMAND_TYPES:
        logger.warning("Unknown command type=%s id=%s", command_type, command_id)
        return {
            "command_id": command_id,
            "status": "failed",
            "result": {"error": f"Unknown command type: {command_type}"},
        }

    # Permission gate
    denial = _check_permission(command_type, permissions, command.get("payload"))
    if denial is not None:
        logger.warning(
            "Command denied id=%s type=%s reason=%s", command_id, command_type, denial
        )
        return {
            "command_id": command_id,
            "status": "failed",
            "result": {"error": denial},
        }

    logger.info("Processing command id=%s type=%s", command_id, command_type)

    if command_type == "ping":
        return {
            "command_id": command_id,
            "status": "completed",
            "result": {"message": "pong"},
        }

    if command_type == "health_check":
        return _run_health_check(_command_data(command))

    if command_type == "list_processes":
        return _run_list_processes(_command_data(command))

    if command_type == "list_connections":
        return _run_list_connections(_command_data(command))

    if command_type == "scan_filesystem":
        return _run_scan_filesystem(_command_data(command))

    if command_type == "restart":
        return _system_control("restart")

    if command_type == "shutdown":
        return _system_control("shutdown")

    if command_type == "update_config":
        return _apply_config(_command_data(command))

    if command_type in {"run_command", "run_script"}:
        return _execute_local(command, script=command_type == "run_script")

    return {
        "command_id": command_id,
        "status": "failed",
        "result": {"error": f"Unhandled command type: {command_type}"},
    }


def build_status_report(config: Dict[str, Any]) -> Dict[str, Any]:
    """Build a live device status snapshot for a ``status_request`` command.

    Uses the same system telemetry sources as the telemetry loop so the
    reported values reflect the host in near real time.
    """
    from homepot.agent.utils.telemetry import (
        collect_system_telemetry,
        collect_uptime_seconds,
        utc_now_iso,
    )

    metrics = collect_system_telemetry()
    return {
        "device_id": config["device_id"],
        "device_name": config.get("device_name", ""),
        "device_type": config.get("device_type", "pos_terminal"),
        "status": "online",
        "connectivity_state": "online",
        "hostname": socket.gethostname(),
        "os_details": config.get("os_details", ""),
        "local_ip": config.get("local_ip", ""),
        "firmware_version": config.get("firmware_version", ""),
        "uptime_seconds": collect_uptime_seconds(),
        "cpu_usage": metrics["cpu_usage"],
        "memory_usage": metrics["memory_usage"],
        "disk_usage": metrics["disk_usage"],
        "timestamp": utc_now_iso(),
    }


def build_status_update_payload(
    command_id: str, status: str, result: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build the JSON body for ``PUT /api/v1/devices/{command_id}/status``."""
    payload: Dict[str, Any] = {
        "status": status,
        "executed_at": datetime.now(timezone.utc).isoformat(),
    }
    if result is not None:
        payload["result"] = result
    return payload
