"""API endpoint for checking agent online/offline status."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from homepot.app.services.agent_service import AgentService
from homepot.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{device_id}/status", tags=["Agent"])
def get_device_status(device_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Return computed ONLINE or OFFLINE status for a device."""
    logger.info("Agent status request received for device_id=%s", device_id)
    try:
        service = AgentService(db)
        result = service.get_device_status(device_id)
        return {
            "status": "success",
            "message": "Device status fetched successfully",
            "data": result,
        }
    except LookupError as e:
        logger.error("Status lookup failed: %s", e)
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected status error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
