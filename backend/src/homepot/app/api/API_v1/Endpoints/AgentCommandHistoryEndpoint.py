"""API endpoint for device command history retrieval.

The device (or emulator) owner views command history in the HOMEPOT User App.
Devices authenticate via ``X-Device-ID`` / ``X-API-Key`` and may only read
their own command history. Reading is gated behind the Manage (``root_access``)
permission so the Monitor-vs-Manage access model governs history collection.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from homepot.app.api.API_v1.Endpoints.agent_permission_gate import require_manage
from homepot.app.auth_utils import get_current_device
from homepot.database import get_database_service
from homepot.models import Device

logger = logging.getLogger(__name__)
router = APIRouter()

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def _iso(value: Any) -> Any:
    """Format a datetime as ISO, returning None for missing values."""
    return value.isoformat() if value is not None else None


def _envelope(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "status": "success",
        "message": "Device command history fetched",
        "data": data,
    }


@router.get("/{device_id}/commands", tags=["Agent"])
async def get_device_command_history(
    device_id: str,
    limit: int = DEFAULT_LIMIT,
    current_device: Device = Depends(get_current_device),
) -> Dict[str, Any]:
    """Return the latest commands for the authenticated device.

    Requires the device owner to have granted the Manage (``root_access``)
    permission. The device can only read its own command history.
    """
    if current_device.device_id != device_id:
        raise HTTPException(
            status_code=403,
            detail="Authenticated device can only read its own command history",
        )
    require_manage(current_device)

    capped_limit = max(1, min(int(limit), MAX_LIMIT))
    try:
        db_service = await get_database_service()
        commands = await db_service.get_commands_for_device(
            int(current_device.id), limit=capped_limit
        )

        return _envelope(
            [
                {
                    "command_id": command.command_id,
                    "command_type": command.command_type,
                    "payload": command.payload,
                    "status": command.status,
                    "result": command.result,
                    "created_at": _iso(command.created_at),
                    "sent_at": _iso(command.sent_at),
                    "executed_at": _iso(command.executed_at),
                }
                for command in commands
            ]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to fetch command history for %s: %s", device_id, e, exc_info=True
        )
        raise HTTPException(
            status_code=500, detail="Failed to fetch device command history"
        )
