"""Command polling and processing for the real device agent."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

COMMAND_TYPES = frozenset({"ping", "restart", "update_config", "shutdown"})


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


def process_command(command: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a single command locally and return a result dict.

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

    logger.info("Processing command id=%s type=%s", command_id, command_type)

    if command_type == "ping":
        return {
            "command_id": command_id,
            "status": "completed",
            "result": {"message": "pong"},
        }

    if command_type == "restart":
        logger.warning(
            "Restart command received id=%s — not yet implemented", command_id
        )
        return {
            "command_id": command_id,
            "status": "completed",
            "result": {"message": "restart acknowledged (not yet implemented)"},
        }

    if command_type == "shutdown":
        logger.warning(
            "Shutdown command received id=%s — not yet implemented", command_id
        )
        return {
            "command_id": command_id,
            "status": "completed",
            "result": {"message": "shutdown acknowledged (not yet implemented)"},
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
