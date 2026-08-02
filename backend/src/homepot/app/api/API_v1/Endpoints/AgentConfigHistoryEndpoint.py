"""API endpoint for device push-command history reporting.

Devices (or emulators mimicking them) call this after completing a composed
push command so the record appears on the Dashboard's "Push History" page,
which reads from the device-level ConfigurationHistory entries.
"""

from datetime import timezone
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from homepot.app.auth_utils import get_current_device
from homepot.app.models.AnalyticsModel import ConfigurationHistory
from homepot.app.schemas.agent import AgentConfigHistoryRequest
from homepot.database import get_database_service
from homepot.models import Device

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/config-history", tags=["Agent"])
async def report_config_history(
    payload: AgentConfigHistoryRequest,
    current_device: Device = Depends(get_current_device),
) -> Dict[str, Any]:
    """Record a completed push command as a ConfigurationHistory entry."""
    logger.info(
        "Config history report received for device_id=%s action=%s",
        payload.device_id,
        payload.action,
    )
    if current_device.device_id != payload.device_id:
        raise HTTPException(
            status_code=403,
            detail="Authenticated device does not match payload device_id",
        )
    try:
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            entry = ConfigurationHistory(
                timestamp=payload.timestamp.astimezone(timezone.utc).replace(
                    tzinfo=None
                ),
                entity_type="device",
                entity_id=payload.device_id,
                parameter_name=payload.parameter_name,
                old_value=payload.old_value,
                new_value=payload.new_value,
                changed_by="agent",
                change_reason=payload.change_reason,
                change_type="automated",
                was_successful=payload.success,
            )
            session.add(entry)
        return {"status": "success", "message": "Push history record stored"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to store push history record: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
