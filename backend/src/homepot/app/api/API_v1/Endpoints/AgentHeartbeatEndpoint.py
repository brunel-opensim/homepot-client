"""API endpoint for device heartbeat updates."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from homepot.app.schemas.agent import AgentHeartbeatRequest
from homepot.app.services.agent_service import AgentService
from homepot.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/heartbeat", tags=["Agent"])
def update_heartbeat(
    payload: AgentHeartbeatRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Update heartbeat timestamp for a registered device."""
    logger.info("Heartbeat request received for device_id=%s", payload.device_id)
    try:
        service = AgentService(db)
        result = service.update_heartbeat(payload)
        return {
            "status": "success",
            "message": "Heartbeat updated successfully",
            "data": result,
        }
    except LookupError as e:
        logger.error("Heartbeat failed: %s", e)
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected heartbeat error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

