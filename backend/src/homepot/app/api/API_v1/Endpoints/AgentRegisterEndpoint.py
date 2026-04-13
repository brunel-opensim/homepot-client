"""API endpoint for agent device registration."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from homepot.app.schemas.agent import AgentRegisterRequest
from homepot.app.services.agent_service import AgentService
from homepot.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/device-dna", tags=["Agent"])
def register_and_update_device_dna(
    payload: AgentRegisterRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Register a device or update its DNA payload."""
    logger.info("Agent register request received for device_id=%s", payload.device_id)
    try:
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

