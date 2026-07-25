"""Command polling and processing for the real device agent."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

COMMAND_TYPES = frozenset({"ping", "restart", "update_config", "shutdown"})

# Each privileged command type requires a specific device_permission key.
REQUIRED_PERMISSION: Dict[str, str] = {
    "restart": "root_access",
    "shutdown": "root_access",
    "update_config": "filesystem_access",
}


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
) -> Optional[str]:
    """Return an error message if the required permission is missing or ``False``.

    ``None`` means the command is allowed.
    """
    required_key = REQUIRED_PERMISSION.get(command_type)
    if required_key is None:
        return None
    if permissions is None:
        return "Device permissions not available — cannot verify access"
    if not permissions.get(required_key, False):
        return (
            f"Permission denied: '{required_key}' is not granted for '{command_type}'"
        )
    return None


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
    denial = _check_permission(command_type, permissions)
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

    return {
        "command_id": command_id,
        "status": "failed",
        "result": {"error": f"Unhandled command type: {command_type}"},
    }


def build_status_update_payload(
    command_id: str, status: str, result: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build the JSON body for ``PUT /api/v1/devices/{command_id}/status``."""
    payload: Dict[str, Any] = {"status": status}
    if result is not None:
        payload["result"] = result
    return payload
