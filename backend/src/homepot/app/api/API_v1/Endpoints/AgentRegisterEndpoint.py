"""API endpoint for agent device registration."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from homepot.app.auth_utils import get_current_device
from homepot.app.schemas.agent import AgentRegisterRequest
from homepot.app.services.agent_service import AgentService
from homepot.database import get_db
from homepot.models import Device

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/device-dna", tags=["Agent"])
def register_and_update_device_dna(
    payload: AgentRegisterRequest,
    current_device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update the authenticated device's DNA payload."""
    logger.info("Agent register request received for device_id=%s", payload.device_id)
    try:
        if current_device.device_id != payload.device_id:
            raise HTTPException(
                status_code=403,
                detail="Authenticated device does not match payload device_id",
            )
        service = AgentService(db)
        result = service.update_device(payload)
        return {
            "status": "success",
            "message": "Device registered successfully",
            "data": result,
        }
    except (LookupError, ValueError) as e:
        logger.error("Agent register validation failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected register error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
