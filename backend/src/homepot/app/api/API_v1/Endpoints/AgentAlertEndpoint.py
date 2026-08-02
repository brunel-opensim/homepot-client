"""API endpoint for device alert reporting.

Devices (or emulators mimicking them) push alert events here so the Dashboard's
"Alerts" tab can display real-time device issues.
"""

import logging
from typing import Any, Dict, cast

from fastapi import APIRouter, Depends, HTTPException

from homepot.app.auth_utils import get_current_device
from homepot.app.schemas.agent import AgentAlertRequest
from homepot.database import get_database_service
from homepot.models import Device

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/alert", tags=["Agent"])
async def report_alert(
    payload: AgentAlertRequest,
    current_device: Device = Depends(get_current_device),
) -> Dict[str, Any]:
    """Store a single device alert for Dashboard display."""
    logger.info("Alert report received for device_id=%s", payload.device_id)
    if current_device.device_id != payload.device_id:
        raise HTTPException(
            status_code=403,
            detail="Authenticated device does not match payload device_id",
        )
    try:
        db_service = await get_database_service()
        await db_service.create_alert(
            device_id=cast(str, current_device.device_id),
            site_id=cast(Any, current_device.site_id),
            title=payload.title,
            description=payload.description,
            severity=payload.severity,
            category=payload.category,
            timestamp=payload.timestamp,
        )
        return {"status": "success", "message": "Alert stored"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to store device alert: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
