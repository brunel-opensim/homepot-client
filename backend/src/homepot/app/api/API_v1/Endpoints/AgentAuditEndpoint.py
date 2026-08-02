"""API endpoint for device audit event reporting.

Devices (or emulators mimicking them) push audit events here so the Dashboard's
"Audit Trail" tab can display real-time device activity.
"""

import logging
from typing import Any, Dict, cast

from fastapi import APIRouter, Depends, HTTPException

from homepot.app.auth_utils import get_current_device
from homepot.app.schemas.agent import AgentAuditRequest
from homepot.database import get_database_service
from homepot.models import Device

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/audit", tags=["Agent"])
async def report_audit_event(
    payload: AgentAuditRequest,
    current_device: Device = Depends(get_current_device),
) -> Dict[str, Any]:
    """Store a single device audit event for Dashboard display."""
    logger.info("Audit event report received for device_id=%s", payload.device_id)
    if current_device.device_id != payload.device_id:
        raise HTTPException(
            status_code=403,
            detail="Authenticated device does not match payload device_id",
        )
    try:
        db_service = await get_database_service()
        await db_service.create_audit_log(
            event_type=payload.event_type,
            description=payload.description,
            device_id=cast(Any, current_device.id),
            site_id=cast(Any, current_device.site_id),
            event_metadata=payload.metadata,
        )
        return {"status": "success", "message": "Audit event stored"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to store device audit event: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
