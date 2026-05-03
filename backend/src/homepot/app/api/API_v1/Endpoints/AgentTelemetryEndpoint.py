"""API endpoint for storing agent telemetry metrics."""

import logging
from typing import Any, Dict, List, Union

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from homepot.app.schemas.agent import AgentTelemetryRequest
from homepot.app.services.agent_service import AgentService
from homepot.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/telemetry", tags=["Agent"])
def save_telemetry(
    payload: Union[AgentTelemetryRequest, List[AgentTelemetryRequest]],
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Save one or many telemetry records for a device."""
    try:
        telemetry_count = len(payload) if isinstance(payload, list) else 1
        device_ref = (
            payload[0].device_id if isinstance(payload, list) else payload.device_id
        )
        logger.info(
            "Telemetry request received for device_id=%s count=%s",
            device_ref,
            telemetry_count,
        )

        service = AgentService(db)
        result = service.save_telemetry(payload)
        return {
            "status": "success",
            "message": "Telemetry saved successfully",
            "data": result,
        }
    except (LookupError, ValueError) as e:
        logger.error("Telemetry validation failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected telemetry error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
