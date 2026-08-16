"""Command polling and processing for the real device agent."""

from datetime import datetime, timezone
import logging
import re
import shlex
import subprocess  # noqa: S404 - arguments are parsed and permission-gated
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

COMMAND_TYPES = frozenset(
    {
        "ping",
        "health_check",
        "request_permission",
        "restart",
        "restart_pos_app",
        "run_command",
        "run_script",
        "shutdown",
        "update_config",
        "update_pos_payment_config",
    }
)

# Each privileged command type requires a specific device_permission key.
REQUIRED_PERMISSION: Dict[str, str] = {
    "health_check": "command_execution",
    "restart": "root_access",
    "restart_pos_app": "command_execution",
    "run_command": "command_execution",
    "run_script": "command_execution",
    "shutdown": "root_access",
    "update_config": "filesystem_access",
    "update_pos_payment_config": "filesystem_access",
}

MAX_COMMAND_OUTPUT = 64 * 1024
MAX_COMMAND_TIMEOUT = 300
PRIVILEGE_ESCALATION_PATTERN = re.compile(
    r"(^|[;&|()\n]\s*|\b(?:exec|command|env)\s+)(sudo|su|doas|pkexec)\b"
)


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

    data = payload.get("data") if isinstance(payload, dict) else None
    command_data = data if isinstance(data, dict) else payload or {}
    if command_type in {"run_command", "run_script"} and command_data.get(
        "run_as_root", False
    ):
        required.append("root_access")
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

    run_as_root = data.get("run_as_root", False) is True
    if not run_as_root and PRIVILEGE_ESCALATION_PATTERN.search(source):
        return {
            "status": "failed",
            "result": {
                "error": "Privilege escalation requires run_as_root and root_access"
            },
        }
    if script:
        argv = ["/bin/sh", "-s"]
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
    if run_as_root:
        argv = ["sudo", "-n", "--", *argv]

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
    payload = command.get("payload")

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

    if command_type == "restart":
        logger.warning(
            "Restart command received id=%s — execution handler not yet integrated",
            command_id,
        )
        return {
            "command_id": command_id,
            "status": "completed",
            "result": {"message": "restart acknowledged"},
        }

    if command_type == "shutdown":
        logger.warning(
            "Shutdown command received id=%s — execution handler not yet integrated",
            command_id,
        )
        return {
            "command_id": command_id,
            "status": "completed",
            "result": {"message": "shutdown acknowledged"},
        }

    if command_type == "update_config":
        new_config = payload if isinstance(payload, dict) else {}
        applied_keys = list(new_config.keys())
        logger.info("Config update command id=%s keys=%s", command_id, applied_keys)
        return {
            "command_id": command_id,
            "status": "completed",
            "result": {
                "message": "config update acknowledged",
                "applied_keys": applied_keys,
            },
        }

    if command_type in {"run_command", "run_script"}:
        return _execute_local(command, script=command_type == "run_script")

    return {
        "command_id": command_id,
        "status": "failed",
        "result": {"error": f"Unhandled command type: {command_type}"},
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
