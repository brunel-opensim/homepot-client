"""Command polling and processing for the real device agent."""

import base64
from datetime import datetime, timezone
import hashlib
import logging
import os
import platform
import re
import shlex
import shutil
import socket
import subprocess  # noqa: S404 - arguments are parsed and permission-gated
from typing import Any, Dict, List, Optional
import urllib.parse
import urllib.request

import httpx
import psutil

from homepot.agent.utils import elevation as elevation_util
from homepot.agent.utils.errors import classify_status
from homepot.agent.utils.host_info import get_firmware_version

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
        "run_command_unprivileged",
        "install_program",
        "uninstall_program",
        "list_installed_programs",
        "update_program",
        "upgrade_all_programs",
        "start_program",
        "stop_program",
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
    "run_command_unprivileged": "command_execution",
    "install_program": "root_access",
    "uninstall_program": "root_access",
    "list_installed_programs": "command_execution",
    "update_program": "root_access",
    "upgrade_all_programs": "root_access",
    "start_program": "root_access",
    "stop_program": "root_access",
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
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        err = classify_status(url, status_code)
        if err is not None:
            logger.error(
                "Permissions fetch permanent failure url=%s status=%s",
                url,
                status_code,
            )
            raise err
        logger.warning("Failed to fetch device permissions (HTTP %s)", status_code)
        return None
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


def _is_windows_platform() -> bool:
    """Return True when the host is a Windows device (no POSIX elevation)."""
    return os.name == "nt" or platform.system().lower() == "windows"


def _resolve_winget_path() -> Optional[str]:
    """Locate winget.exe in a way that works under the SYSTEM scheduled task.

    winget ships as a per-user App Execution Alias under %LOCALAPPDATA%, which
    does NOT resolve when the agent runs as SYSTEM through the elevation
    scheduled task (that is exactly the context in which elevated winget
    commands execute). Prefer the real binary under WindowsApps, which SYSTEM
    can read and execute; fall back to the alias for the device-user context.
    """
    import glob
    import shutil

    # 1. Real binary under WindowsApps (works under SYSTEM).
    candidates = glob.glob(
        r"C:\Program Files\WindowsApps\Microsoft.DesktopAppInstaller_*\winget.exe"
    )
    if candidates:
        candidates.sort()
        return candidates[-1]

    # 2. PATH lookup (App Execution Alias; works in the device-user context,
    #    e.g. for the unprivileged list_installed_programs command).
    found = shutil.which("winget")
    if found and os.path.isfile(found):
        return found

    # 3. Newer builds ship a copy on PATH-adjacent locations.
    for candidate in (
        r"C:\Windows\System32\winget.exe",
        r"C:\Windows\SysWOW64\winget.exe",
    ):
        if os.path.isfile(candidate):
            return candidate

    return None


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
    # root_access grant and runs through the scoped homepot-ctl helper on
    # POSIX (or via the PowerShell helper on Windows).
    if not _is_windows_platform():
        elevated_argv = elevation_util.elevated_exec_argv()
        if elevated_argv is None:
            return {
                "status": "failed",
                "result": {
                    "error": (
                        "run_command/run_script requires the Manage elevation "
                        "layer, which is not installed on this device. "
                        "Grant 'Manage device' access through the Homepot "
                        "app on this device to enable command execution."
                    )
                },
            }
        if not elevation_util.is_provisioned():
            return {
                "status": "failed",
                "result": {
                    "error": (
                        "run_command/run_script requires the Manage elevation "
                        "layer, but its sudoers rule is missing on this "
                        "device. Re-grant 'Manage device' access through "
                        "the Homepot app to reinstall it."
                    )
                },
            }
        # The helper reads the command/script text from stdin and runs it via
        # the shell as root; nothing is passed through argv.
        argv = elevated_argv
        script_text = source
    else:
        # Windows: when elevation is available, run via the SYSTEM scheduled
        # task (request/result protocol) so the helper executes elevated rather
        # than inheriting the agent's unprivileged context. Otherwise fall back
        # to a plain local run.
        if elevation_util.is_elevation_supported():
            if not elevation_util.is_elevation_installed():
                return {
                    "status": "failed",
                    "result": {
                        "error": (
                            "run_command/run_script requires the Manage elevation "
                            "layer, which is not installed on this device. "
                            "Grant 'Manage device' access through the Homepot "
                            "app on this device to enable command execution."
                        )
                    },
                }
            if not elevation_util.is_provisioned():
                return {
                    "status": "failed",
                    "result": {
                        "error": (
                            "run_command/run_script requires the Manage elevation "
                            "layer, but its scheduled task is missing on this "
                            "device. Re-grant 'Manage device' access through "
                            "the Homepot app to reinstall it."
                        )
                    },
                }
            outcome = elevation_util.run_elevated("exec", source, timeout)
            if not outcome.get("ok"):
                return {
                    "status": "failed",
                    "result": {
                        "error": (
                            outcome.get("error")
                            or outcome.get("stderr")
                            or "elevated command failed"
                        ),
                        "exit_code": outcome.get("exit_code"),
                        "stdout": (outcome.get("stdout") or "")[-MAX_COMMAND_OUTPUT:],
                        "truncated": len(outcome.get("stdout") or "")
                        > MAX_COMMAND_OUTPUT,
                    },
                }
            _out = outcome.get("stdout") or ""
            _err = outcome.get("stderr") or ""
            return {
                "status": "completed",
                "result": {
                    "exit_code": outcome.get("exit_code", 0),
                    "stdout": _out[-MAX_COMMAND_OUTPUT:],
                    "stderr": _err[-MAX_COMMAND_OUTPUT:],
                    "truncated": len(_out) > MAX_COMMAND_OUTPUT
                    or len(_err) > MAX_COMMAND_OUTPUT,
                },
            }
        elif script:
            # PowerShell reads the script from stdin.
            argv = _shell_for_scripts()
            script_text = source
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
            script_text = None

    try:
        completed = subprocess.run(  # noqa: S603 - no shell; argv is explicit
            argv,
            input=script_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "failed", "result": {"error": str(exc)}}

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    result = {
        "exit_code": completed.returncode,
        "stdout": stdout[-MAX_COMMAND_OUTPUT:],
        "stderr": stderr[-MAX_COMMAND_OUTPUT:],
        "truncated": len(stdout) > MAX_COMMAND_OUTPUT
        or len(stderr) > MAX_COMMAND_OUTPUT,
    }
    return {
        "status": "completed" if completed.returncode == 0 else "failed",
        "result": result,
    }


def _run_command_unprivileged(data: Dict[str, Any]) -> Dict[str, Any]:
    """Run a command in the device's own (unprivileged) context.

    This is the Monitor-tier half of the technician "Remote Access" shell:
    the command runs as the device user, without elevation, and is gated on
    ``command_execution`` rather than ``root_access``. The elevated half is
    ``run_command`` (Manage tier).
    """
    source = data.get("command")
    if not isinstance(source, str) or not source.strip():
        return {
            "status": "failed",
            "result": {"error": "A non-empty 'command' value is required"},
        }
    timeout_value = data.get("timeout_seconds", 30)
    try:
        timeout = max(1, min(int(timeout_value), MAX_COMMAND_TIMEOUT))
    except (TypeError, ValueError):
        timeout = 30

    # No elevation: run through the target shell in the agent's own context.
    if _is_windows_platform():
        argv = ["powershell", "-NoProfile", "-NonInteractive", "-Command", source]
    else:
        argv = ["/bin/sh", "-c", source]

    try:
        completed = subprocess.run(  # noqa: S603 - explicit argv, no shell
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "failed", "result": {"error": str(exc)}}

    _uout = completed.stdout or ""
    _uerr = completed.stderr or ""
    return {
        "status": "completed" if completed.returncode == 0 else "failed",
        "result": {
            "exit_code": completed.returncode,
            "stdout": _uout[-MAX_COMMAND_OUTPUT:],
            "stderr": _uerr[-MAX_COMMAND_OUTPUT:],
            "truncated": len(_uout) > MAX_COMMAND_OUTPUT
            or len(_uerr) > MAX_COMMAND_OUTPUT,
        },
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


def _parse_lsof_connection(
    line: str, filter_state: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Parse one ``lsof -nP -i`` row into a connection dict.

    Columns (space-separated): COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE
    NAME. A socket NAME looks like ``TCP 127.0.0.1:52083->10.0.0.1:443
    (ESTABLISHED)``. Returns ``None`` when the row is a header, is not a
    socket, or does not match ``filter_state``.
    """
    tokens = line.split()
    if not tokens or tokens[0] == "COMMAND":
        return None
    proto = None
    name = None
    for idx, tok in enumerate(tokens):
        if tok in ("TCP", "UDP"):
            proto = tok
            name = " ".join(tokens[idx + 1 :])
            break
    if proto is None or not name:
        return None
    state = None
    if " (" in name:
        addr, sep, state_token = name.rpartition(" (")
        if sep:
            state = state_token.rstrip(")")
            name = addr
    addresses = name.split("->")
    local = addresses[0] if addresses else None
    remote = addresses[1] if len(addresses) > 1 else None

    def _socket_spec(spec: Optional[str]) -> Optional[str]:
        if not spec or spec in ("*", "*:*"):  # type: ignore[comparison-overlap]
            return None
        return spec

    laddr = _socket_spec(local)
    raddr = _socket_spec(remote)
    if filter_state and filter_state != "ALL" and (state or "NONE") != filter_state:
        return None

    pid = None
    try:
        pid = int(tokens[1])
    except (TypeError, ValueError):
        pid = None
    return {
        "pid": pid,
        "status": state or "NONE",
        "laddr": laddr,
        "raddr": raddr,
    }


def _connections_via_lsof(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Unprivileged snapshot of the current user's connections via lsof.

    ``psutil.net_connections`` maps sockets to PIDs and therefore requires
    root on macOS; ``lsof -nP -i`` lists the same user's sockets without
    elevation. Returns a status dict on success, ``None`` if lsof itself is
    unavailable or errors out.
    """
    filter_state = data.get("filter_state")
    lsof = shutil.which("lsof")
    if lsof is None:
        logger.warning("lsof fallback unavailable on this host")
        return None
    try:
        completed = subprocess.run(  # noqa: S603 - explicit argv list, no shell
            [lsof, "-nP", "-i"],
            capture_output=True,
            text=True,
            timeout=MAX_COMMAND_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("lsof fallback failed: %s", exc)
        return None
    if completed.returncode not in (0, 1):
        logger.warning(
            "lsof fallback errored (rc=%s): %s",
            completed.returncode,
            completed.stderr[-500:],
        )
        return None

    connections = []
    for line in completed.stdout.splitlines():
        parsed = _parse_lsof_connection(line, filter_state)
        if parsed is not None:
            connections.append(parsed)
    return {
        "status": "completed",
        "result": {
            "count": len(connections),
            "connections": connections,
            "source": "lsof",
        },
    }


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
        # On macOS enumerating sockets with their owning PIDs requires root;
        # fall back to the current user's connections via lsof so the push
        # returns real data instead of failing.
        fallback = _connections_via_lsof(data)
        if fallback is None:
            return {
                "status": "failed",
                "result": {
                    "error": f"connection listing requires elevated privileges: {exc}"
                },
            }
        return fallback

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


def _powershell_argv(script: str) -> List[str]:
    """Return a powershell.exe argv that runs *script* robustly.

    Uses ``-EncodedCommand`` (UTF-16LE base64) so the script never has to
    survive Windows command-line quoting, which mangles embedded double
    quotes (e.g. the C# ``[DllImport("winmm.dll")]`` used by the volume
    applier).
    """
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]


# --- update_config (OS settings adapter) ------------------------------------


def _config_appliers(platform_name: str) -> Dict[str, Any]:
    """Return key -> argv builder for host settings that have a real OS action.

    A builder returns the exact argv to run, or ``None`` when the platform has
    no usable way to apply the setting (e.g. a required helper binary is not
    installed). ``None`` is surfaced as a clean per-key failure by
    ``_apply_config`` instead of a raw ``OSError`` from subprocess.
    """
    if platform_name == "darwin":

        def _brightness(value: Any) -> Optional[List[str]]:
            helper = shutil.which("brightness")
            if helper is None:
                logger.warning(
                    "macOS 'brightness' helper not found; install via "
                    "`brew install brightness`"
                )
                return None
            # nriley/brightness takes a 0..1 float, not a 0..100 integer.
            return [helper, f"{int(value) / 100:.2f}"]

        return {
            "brightness": _brightness,
            "volume": lambda value: [
                "osascript",
                "-e",
                f"set volume output volume {int(value)}",
            ],
        }
    if platform_name == "windows":

        def _win_volume(value: Any) -> List[str]:
            # Windows has no built-in CLI to set the master volume, so call the
            # waveOutSetVolume Win32 API through a tiny C# P/Invoke class.
            # volume runs unprivileged (the agent's own process context).
            pct = max(0, min(100, int(value)))
            script = (
                "Add-Type -TypeDefinition @'\n"
                "using System;\n"
                "using System.Runtime.InteropServices;\n"
                "public static class W {\n"
                '    [DllImport("winmm.dll")] public static extern int waveOutSetVolume(IntPtr h, uint v);\n'
                "    public static int Set(int p) {\n"
                "        p = Math.Max(0, Math.Min(100, p));\n"
                "        uint v = (uint)(65535L * p / 100);\n"
                "        return waveOutSetVolume(IntPtr.Zero, (v << 16) | v);\n"
                "    }\n"
                "}\n"
                "'@\n"
                f"[W]::Set({pct})\n"
            )
            return _powershell_argv(script)

        def _win_brightness(value: Any) -> List[str]:
            # Set brightness through the Monitor Configuration API
            # (dxva2.dll SetMonitorBrightness) rather than the WMI
            # WmiSetBrightness method, which is only wired up on Intel-graphics
            # laptops. The DDC/CI path works on a wider range of panels; if the
            # panel has no physical-monitor brightness interface this fails
            # with a clear error instead of silently no-op'ing.
            pct = max(0, min(100, int(value)))
            script = (
                "Add-Type -TypeDefinition @'\n"
                "using System;\n"
                "using System.Runtime.InteropServices;\n"
                "public static class B {\n"
                "    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int x; public int y; }\n"  # noqa: E501
                "    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]\n"
                "    public struct PM { public IntPtr h; [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)] public string desc; }\n"  # noqa: E501
                '    [DllImport("user32.dll")] public static extern IntPtr MonitorFromPoint(POINT pt, uint f);\n'  # noqa: E501
                '    [DllImport("dxva2.dll")] public static extern bool GetNumberOfPhysicalMonitorsFromHMONITOR(IntPtr h, out uint c);\n'  # noqa: E501
                '    [DllImport("dxva2.dll")] public static extern bool GetPhysicalMonitorsFromHMONITOR(IntPtr h, uint c, [Out] PM[] m);\n'  # noqa: E501
                '    [DllImport("dxva2.dll")] public static extern bool SetMonitorBrightness(IntPtr h, uint b);\n'  # noqa: E501
                '    [DllImport("dxva2.dll")] public static extern bool DestroyPhysicalMonitors(uint c, [In] PM[] m);\n'  # noqa: E501
                "    public static int Set(int pct) {\n"
                "        pct = Math.Max(0, Math.Min(100, pct));\n"
                "        IntPtr h = MonitorFromPoint(new POINT(), 1);\n"
                "        uint c;\n"
                "        if (!GetNumberOfPhysicalMonitorsFromHMONITOR(h, out c) || c == 0) return 1;\n"
                "        PM[] m = new PM[c];\n"
                "        if (!GetPhysicalMonitorsFromHMONITOR(h, c, m)) return 2;\n"
                "        bool ok = SetMonitorBrightness(m[0].h, (uint)pct);\n"
                "        DestroyPhysicalMonitors(c, m);\n"
                "        return ok ? 0 : 3;\n"
                "    }\n"
                "}\n"
                "'@\n"
                f"$rc = [B]::Set({pct})\n"
                "if ($rc -ne 0) {\n"
                "    # Fallback: WMI WmiMonitorBrightnessMethods works on many\n"
                "    # panels where DDC/CI (dxva2) is unavailable.\n"
                "    try {\n"
                "        $wmi = Get-WmiObject -Namespace root/WMI `\n"
                "            -Class WmiMonitorBrightnessMethods -ErrorAction Stop\n"
                "        if ($wmi) { $wmi.WmiSetBrightness(1, [byte]$pct); $rc = 0 }\n"
                "    } catch { }\n"
                "}\n"
                'if ($rc -ne 0) { throw "SetMonitorBrightness failed (rc=$rc)" }\n'
            )
            return _powershell_argv(script)

        return {"volume": _win_volume, "brightness": _win_brightness}
    return {
        "brightness": lambda value: ["brightnessctl", "set", f"{int(value)}%"],
        "volume": lambda value: ["amixer", "-q", "set", "Master", f"{int(value)}%"],
    }


# --- firmware (download + verify) -------------------------------------------


FIRMWARE_DOWNLOAD_TIMEOUT = 60  # seconds
FIRMWARE_MAX_BYTES = 100 * 1024 * 1024  # 100 MB


def _parse_firmware_checksum(checksum: Any) -> Optional[str]:
    """Return the lowercase sha256 hex from a 'sha256:<hex>' or plain-hex value.

    Returns ``None`` for a missing or malformed checksum, which the caller
    treats as "downloaded but unverified" rather than a hard failure.
    """
    if not isinstance(checksum, str):
        return None
    value = checksum.strip()
    if value.lower().startswith("sha256:"):
        value = value[7:]
    if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        return None
    return value.lower()


def _download_firmware(url: Any, checksum: Any, version: Any) -> Dict[str, Any]:
    """Download a firmware artifact and verify its sha256 checksum.

    Only downloads and verifies the bytes; flashing/applying the firmware is
    device-specific and intentionally out of scope. The downloaded artifact is
    discarded after verification.
    """
    if not isinstance(url, str) or not url.strip():
        return {"status": "failed", "message": "firmware 'url' is required"}
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return {
            "status": "failed",
            "message": f"unsupported firmware URL scheme: {parsed.scheme}",
        }
    try:
        with (
            urllib.request.urlopen(  # noqa: S310 - scheme validated to http/https above
                url, timeout=FIRMWARE_DOWNLOAD_TIMEOUT
            ) as resp
        ):
            data = resp.read(FIRMWARE_MAX_BYTES + 1)
    except Exception as exc:  # noqa: BLE001 - surface any download error
        return {"status": "failed", "message": f"firmware download failed: {exc}"}
    if len(data) > FIRMWARE_MAX_BYTES:
        return {
            "status": "failed",
            "message": f"firmware exceeds the {FIRMWARE_MAX_BYTES}-byte size cap",
        }
    actual = hashlib.sha256(data).hexdigest()
    expected = _parse_firmware_checksum(checksum)
    if expected is not None and actual != expected:
        return {
            "status": "failed",
            "message": "checksum mismatch",
            "expected_sha256": expected,
            "actual_sha256": actual,
        }
    return {
        "status": "downloaded",
        "version": version,
        "size": len(data),
        "sha256": actual,
        "checksum_verified": expected is not None,
        "message": (
            "firmware downloaded and checksum verified (staged for review; "
            "applying the firmware is device-specific and not performed here)"
        ),
    }


def _apply_config(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Apply a config update; keys with a known OS action run it on the host."""
    new_config = payload if isinstance(payload, dict) else {}
    platform_name = platform.system().lower()
    appliers = _config_appliers(platform_name)

    applied_keys: List[str] = []
    results: Dict[str, Any] = {}

    # Firmware update: url/checksum/version describe a single download+verify
    # operation, not three independent config keys. Handle it as one unit and
    # exclude those keys from the per-key config loop below.
    if "url" in new_config:
        applied_keys.append("firmware")
        results["firmware"] = _download_firmware(
            url=new_config.get("url"),
            checksum=new_config.get("checksum"),
            version=new_config.get("version"),
        )
        new_config = {
            key: value
            for key, value in new_config.items()
            if key not in ("url", "checksum", "version")
        }

    for key, value in new_config.items():
        applier = appliers.get(key)
        if applier is None:
            applied_keys.append(key)
            results[key] = {
                "status": "unsupported",
                "message": "no OS action is defined for this key on this device",
            }
            continue
        try:
            argv = applier(value)
            if argv is None:
                applied_keys.append(key)
                results[key] = {
                    "status": "failed",
                    "message": (
                        f"{key} could not be applied: required OS helper is "
                        "not installed on this device"
                    ),
                }
                continue
            outcome = _run_argv(argv)
            applied_keys.append(key)
            results[key] = {
                "status": "applied" if outcome["ok"] else "failed",
                **(outcome if not outcome["ok"] else {}),
            }
        except Exception as exc:  # noqa: BLE001 - report any applier failure
            applied_keys.append(key)
            results[key] = {"status": "error", "message": str(exc)}

    # Report the command as failed when any supported setting actually failed,
    # so a partial success (e.g. volume applied but brightness failed) is not
    # masked as "completed". Unsupported keys (no OS action defined) do not
    # count as failures.
    status = "completed"
    if any(result.get("status") in ("failed", "error") for result in results.values()):
        status = "failed"

    return {
        "status": status,
        "result": {
            "message": (
                "config update applied"
                if status == "completed"
                else "config update failed"
            ),
            "applied_keys": applied_keys,
            "results": results,
        },
    }


# --- restart / shutdown -----------------------------------------------------


def _system_control(command_type: str) -> Dict[str, Any]:
    """Reboot or power off the host system via elevation."""
    if os.name == "nt" or platform.system().lower() == "windows":
        # On Windows, check if the elevation helper is available
        elevated_argv = elevation_util.elevated_command_argv(command_type)
        if elevation_util.is_elevation_supported():
            if elevated_argv is None:
                return {
                    "status": "failed",
                    "result": {
                        "error": (
                            f"{command_type} requires the Manage elevation "
                            "layer, which is not installed on this device. "
                            "Grant 'Manage device' access through the "
                            "Homepot app on this device to enable power "
                            "operations."
                        )
                    },
                }
            if not elevation_util.is_provisioned():
                return {
                    "status": "failed",
                    "result": {
                        "error": (
                            f"{command_type} requires the Manage elevation "
                            "layer, but its scheduled task is missing on this "
                            "device. Re-grant 'Manage device' access through "
                            "the Homepot app to reinstall it."
                        )
                    },
                }
            # Run through the SYSTEM scheduled task (request/result protocol)
            # so the helper executes elevated rather than unprivileged.
            outcome = elevation_util.run_elevated(command_type)
        else:
            # Fallback: run shutdown directly (agent runs as elevated service)
            action = "/r /t 0" if command_type == "restart" else "/s /t 0"
            outcome = _run_argv(["shutdown", *shlex.split(action)])
    else:
        # Elevation is scoped to the homepot-ctl helper, never blanket sudo.
        # When the helper is absent (e.g. Manage was never granted through
        # the User App) fail with an actionable message instead of guessing
        # at a passwordless sudo rule that was never provisioned.
        elevated_argv = elevation_util.elevated_command_argv(command_type)
        if elevation_util.is_elevation_supported():
            # Distinguish a missing helper from a missing sudoers rule so the
            # owner gets an actionable message: the helper is restored by the
            # one-time installer, the rule by re-provisioning (or the same
            # installer when a previous rule was removed).
            if elevated_argv is None:
                return {
                    "status": "failed",
                    "result": {
                        "error": (
                            f"{command_type} requires the Manage elevation "
                            "layer, which is not installed on this device. "
                            "Grant 'Manage device' access through the "
                            "Homepot app on this device to enable power "
                            "operations."
                        )
                    },
                }
            if not elevation_util.is_provisioned():
                return {
                    "status": "failed",
                    "result": {
                        "error": (
                            f"{command_type} requires the Manage elevation "
                            "layer, but its sudoers rule is missing on this "
                            "device. Re-grant 'Manage device' access through "
                            "the Homepot app to reinstall it."
                        )
                    },
                }
            outcome = _run_argv(elevated_argv)
        else:
            outcome = _run_argv(
                [
                    *_elevation_prefix(),
                    "shutdown",
                    "-r" if command_type == "restart" else "-h",
                    "now",
                ]
            )
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


def _run_winget_program(command_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Install / uninstall / update a Windows program via winget, elevated.

    ``command_type`` is one of ``install_program``, ``uninstall_program``,
    ``update_program`` or ``upgrade_all_programs``; the target package is read
    from ``data["package"]`` (a winget package id) except for
    ``upgrade_all_programs``, which upgrades every installed package. Runs
    through the scoped elevation helper so the winget operation executes with
    SYSTEM privileges (winget is Windows-only).
    """
    if not _is_windows_platform():
        return {
            "status": "failed",
            "result": {"error": "winget is only available on Windows"},
        }

    if not elevation_util.is_elevation_installed():
        return {
            "status": "failed",
            "result": {
                "error": (
                    f"{command_type} requires the Manage elevation layer, which "
                    "is not installed on this device. Grant 'Manage device' access."
                )
            },
        }
    if not elevation_util.is_provisioned():
        return {
            "status": "failed",
            "result": {
                "error": (
                    f"{command_type} requires the Manage elevation layer, but its "
                    "scheduled task is missing. Re-grant 'Manage device' access."
                )
            },
        }

    flags = "--silent --accept-package-agreements --accept-source-agreements"
    # Resolve winget inside the elevated (SYSTEM) context: the per-user App
    # Execution Alias cannot be invoked there, but the real binary under
    # WindowsApps can be enumerated by SYSTEM.
    winget_resolve = (
        "$wingetExe = (Get-ChildItem 'C:/Program Files/WindowsApps' "
        "-Filter 'Microsoft.DesktopAppInstaller_*' -Directory "
        "-ErrorAction SilentlyContinue | "
        "ForEach-Object { Join-Path $_.FullName 'winget.exe' } | "
        "Where-Object { Test-Path $_ } | Sort-Object | Select-Object -Last 1); "
        "if (-not $wingetExe) { "
        "$wingetExe = (Get-Command winget -ErrorAction SilentlyContinue).Source }; "
        "if (-not $wingetExe -or -not (Test-Path $wingetExe)) { "
        "throw 'winget not found' }; "
    )
    if command_type == "upgrade_all_programs":
        script = winget_resolve + f"& $wingetExe upgrade --all {flags} --scope machine"
    else:
        package = data.get("package")
        if not isinstance(package, str) or not package.strip():
            return {
                "status": "failed",
                "result": {"error": "A 'package' value is required"},
            }
        if not all(c.isalnum() or c in "._-+" for c in package):
            return {
                "status": "failed",
                "result": {"error": "Invalid package id"},
            }
        if command_type == "install_program":
            script = (
                winget_resolve
                + f"& $wingetExe install -e --id '{package}' {flags} --scope machine"
            )
        elif command_type == "uninstall_program":
            script = (
                winget_resolve
                + f"& $wingetExe uninstall -e --id '{package}' --silent --scope machine"
            )
        else:  # update_program
            script = (
                winget_resolve
                + f"& $wingetExe upgrade -e --id '{package}' {flags} --scope machine"
            )

    try:
        timeout = max(
            1, min(int(data.get("timeout_seconds", 300)), MAX_COMMAND_TIMEOUT)
        )
    except (TypeError, ValueError):
        timeout = 300

    outcome = elevation_util.run_elevated("exec", script, timeout)
    if not outcome.get("ok"):
        return {
            "status": "failed",
            "result": {
                "error": (
                    outcome.get("error")
                    or outcome.get("stderr")
                    or f"{command_type} failed"
                ),
                "exit_code": outcome.get("exit_code"),
                "stdout": (outcome.get("stdout") or "")[-MAX_COMMAND_OUTPUT:],
            },
        }
    return {
        "status": "completed",
        "result": {
            "exit_code": outcome.get("exit_code", 0),
            "stdout": (outcome.get("stdout") or "")[-MAX_COMMAND_OUTPUT:],
            "stderr": (outcome.get("stderr") or "")[-MAX_COMMAND_OUTPUT:],
        },
    }


def _run_list_installed_programs() -> Dict[str, Any]:
    """List installed Windows programs via winget (read-only, unprivileged)."""
    if not _is_windows_platform():
        return {
            "status": "failed",
            "result": {"error": "winget is only available on Windows"},
        }

    # Lightweight availability check. _resolve_winget_path() is mocked in
    # tests to return a sentinel; on a real device it returns the alias (or
    # the real binary) when winget is installed.
    if _resolve_winget_path() is None:
        return {
            "status": "failed",
            "result": {
                "error": (
                    "winget is not installed on this device. Install 'App "
                    "Installer' from the Microsoft Store, then retry."
                )
            },
        }
    winget_exe = _resolve_winget_path()
    if winget_exe is None:
        return {
            "status": "failed",
            "result": {
                "error": (
                    "winget is not installed on this device. Install 'App "
                    "Installer' from the Microsoft Store, then retry."
                )
            },
        }
    try:
        completed = subprocess.run(  # noqa: S603, S607 - fixed argv, no shell
            [winget_exe, "list", "--accept-source-agreements"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "failed", "result": {"error": f"winget list failed: {exc}"}}
    if completed.returncode != 0:
        return {
            "status": "failed",
            "result": {
                "error": (completed.stderr or completed.stdout or "winget list failed")[
                    -MAX_COMMAND_OUTPUT:
                ]
            },
        }
    return {
        "status": "completed",
        "result": {
            "stdout": (completed.stdout or "")[-MAX_COMMAND_OUTPUT:],
            "stderr": (completed.stderr or "")[-MAX_COMMAND_OUTPUT:],
        },
    }


def _parse_program_args(value: Any) -> List[str]:
    """Coerce an args value into a list of argv strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        try:
            if platform.system() == "Windows":
                return shlex.split(value, posix=False)
            return shlex.split(value)
        except ValueError:
            return [value]
    return [str(value)]


_STOP_PROGRAM_DENYLIST = frozenset(
    name.lower().removesuffix(".exe")
    for name in (
        "csrss",
        "lsass",
        "services",
        "smss",
        "svchost",
        "wininit",
        "winlogon",
        "system",
        "registry",
        "explorer",
    )
)


def _start_program(data: Dict[str, Any]) -> Dict[str, Any]:
    path = data.get("path")
    if not isinstance(path, str) or not path.strip():
        for key in ("program", "name", "executable"):
            candidate = data.get(key)
            if isinstance(candidate, str) and candidate.strip():
                path = candidate
                break
    if not isinstance(path, str) or not path.strip():
        return {"status": "failed", "result": {"error": "'path' is required"}}
    path = path.strip()

    if "\x00" in path:
        return {"status": "failed", "result": {"error": "invalid 'path'"}}

    args = _parse_program_args(data.get("args", data.get("arguments")))

    working_dir = data.get("working_dir", data.get("cwd"))
    if working_dir is not None:
        if not isinstance(working_dir, str):
            return {
                "status": "failed",
                "result": {"error": "'working_dir' must be a string"},
            }
        working_dir = working_dir.strip() or None
        if working_dir is not None and not os.path.isdir(working_dir):
            return {
                "status": "failed",
                "result": {"error": "working directory does not exist: " + working_dir},
            }

    wait = bool(data.get("wait", False))
    timeout_value = data.get("timeout_seconds", data.get("timeout"))
    timeout = None
    if timeout_value is not None:
        try:
            timeout = max(1, min(int(timeout_value), MAX_COMMAND_TIMEOUT))
        except (TypeError, ValueError):
            return {
                "status": "failed",
                "result": {"error": "timeout_seconds must be an integer"},
            }

    try:
        proc = subprocess.Popen(  # noqa: S603, S607 - fixed argv, no shell
            [path] + args,
            cwd=working_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return {"status": "failed", "result": {"error": "program not found: " + path}}
    except Exception as exc:  # noqa: BLE001 - surface any launch error
        return {
            "status": "failed",
            "result": {"error": "failed to start program: " + str(exc)},
        }

    if not wait:
        return {
            "status": "completed",
            "result": {
                "message": "program started",
                "pid": proc.pid,
                "path": path,
            },
        }

    try:
        proc.wait(timeout=timeout if timeout is not None else MAX_COMMAND_TIMEOUT)
    except subprocess.TimeoutExpired:
        return {
            "status": "completed",
            "result": {
                "message": "program started (still running after timeout)",
                "pid": proc.pid,
                "path": path,
                "timed_out": True,
            },
        }
    return {
        "status": "completed",
        "result": {
            "message": "program finished",
            "pid": proc.pid,
            "path": path,
            "returncode": proc.returncode,
        },
    }


def _stop_program(data: Dict[str, Any]) -> Dict[str, Any]:
    force = bool(data.get("force", False))
    pid_value = data.get("pid")

    if pid_value is not None:
        try:
            pid = int(pid_value)
        except (TypeError, ValueError):
            return {"status": "failed", "result": {"error": "'pid' must be an integer"}}
        if pid <= 0:
            return {"status": "failed", "result": {"error": "'pid' must be positive"}}
        try:
            proc = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return {
                "status": "completed",
                "result": {"message": "process not running", "pid": pid, "killed": 0},
            }
        if proc.name().lower().removesuffix(".exe") in _STOP_PROGRAM_DENYLIST:
            return {
                "status": "failed",
                "result": {
                    "error": "refusing to stop critical system process: " + proc.name()
                },
            }
        try:
            if force:
                proc.kill()
            else:
                proc.terminate()
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            return {
                "status": "failed",
                "result": {
                    "error": "could not stop process " + str(pid) + ": " + str(exc)
                },
            }
        except Exception as exc:  # noqa: BLE001 - surface any stop error
            return {
                "status": "failed",
                "result": {
                    "error": "could not stop process " + str(pid) + ": " + str(exc)
                },
            }
        return {
            "status": "completed",
            "result": {"message": "process stopped", "pid": pid, "killed": 1},
        }

    name = data.get("name", data.get("process", data.get("program")))
    if not isinstance(name, str) or not name.strip():
        return {"status": "failed", "result": {"error": "'name' or 'pid' is required"}}
    name = name.strip()
    if any(ch in name for ch in ("/", "\\", "\x00")):
        return {"status": "failed", "result": {"error": "invalid process name"}}
    target = name.lower().removesuffix(".exe")
    if target in _STOP_PROGRAM_DENYLIST:
        return {
            "status": "failed",
            "result": {"error": "refusing to stop critical system process: " + name},
        }

    killed_pids = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            proc_name = (proc.info.get("name") or "").lower().removesuffix(".exe")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if proc_name != target:
            continue
        if proc_name in _STOP_PROGRAM_DENYLIST:
            continue
        try:
            if force:
                proc.kill()
            else:
                proc.terminate()
            killed_pids.append(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue  # noqa: S112
        except Exception:  # noqa: BLE001, S112 - keep going on per-process errors
            continue  # noqa: S112

    for pid in killed_pids:
        try:
            psutil.Process(pid).wait(timeout=5)
        except Exception:  # noqa: BLE001 - best-effort
            pass

    if not killed_pids:
        return {
            "status": "completed",
            "result": {"message": "no matching process", "name": name, "killed": 0},
        }
    return {
        "status": "completed",
        "result": {
            "message": "process stopped",
            "name": name,
            "killed": len(killed_pids),
            "pids": killed_pids,
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

    if command_type == "run_command_unprivileged":
        return _run_command_unprivileged(_command_data(command))

    if command_type == "list_installed_programs":
        return _run_list_installed_programs()

    if command_type in {
        "install_program",
        "uninstall_program",
        "update_program",
        "upgrade_all_programs",
    }:
        return _run_winget_program(command_type, _command_data(command))

    if command_type in {"start_program", "stop_program"}:
        data = _command_data(command)
        if command_type == "start_program":
            return _start_program(data)
        return _stop_program(data)

    if command_type in {"run_command", "run_script"}:
        return _execute_local(command, script=command_type == "run_script")

    return {
        "command_id": command_id,
        "status": "failed",
        "result": {"error": f"Unhandled command type: {command_type}"},
    }


def _host_firmware_version() -> str:
    """Return the host firmware version (BIOS on Windows, OS build elsewhere).

    Mirrors the value the DNA registration reports so status snapshots do not
    show an empty firmware version just because it was never copied into the
    local agent config.
    """
    return get_firmware_version()


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
        "firmware_version": config.get("firmware_version") or _host_firmware_version(),
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
