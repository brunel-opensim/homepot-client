"""API endpoint for device provisioning."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from homepot.app.schemas.provision import (
    DeviceProvisionRequest,
    DeviceProvisionResponse,
)
from homepot.app.services.agent_service import AgentService
from homepot.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/provision",
    tags=["Devices"],
    response_model=Dict[str, Any],
)
def provision_device(
    payload: DeviceProvisionRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Provision a new device and return one-time credentials."""
    logger.info(
        "Device provision request received for site_id=%s user_identity=%s",
        payload.site_id,
        payload.user_identity,
    )
    try:
        service = AgentService(db)
        result = service.provision_device(payload)
        response_data = DeviceProvisionResponse(**result)
        return {
            "status": "success",
            "message": "Device provisioned successfully",
            "data": response_data.model_dump(),
        }
    except (LookupError, ValueError) as e:
        logger.error("Provision validation failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected provision error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
