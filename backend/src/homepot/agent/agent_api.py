"""API routes for agent-related operations in the Homepot backend."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from sqlalchemy.orm import Session

from homepot.agent.utils.device_dna import collect_device_dna
from homepot.app.auth_utils import authenticate_device_credentials, API_KEY_HEADER_NAME
from homepot.database import get_db
from homepot.models import Site

logger = logging.getLogger(__name__)
router = APIRouter()
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


class DeviceRegister(BaseModel):
    """Schema for device registration request."""

    device_id: str
    site_id: str


@router.post("/register")
async def register_and_collect_device_dna(
    payload: DeviceRegister, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Register a pre-authorized device and return collected device DNA."""
    try:
        device = authenticate_device_credentials(
            db=db,
            device_id=payload.device_id,
        )

        site = db.get(Site, device.site_id)
        if site is None or site.site_id != payload.site_id:
            raise HTTPException(
                status_code=401,
                detail="Device is not authorized for the requested site",
            )

        return {
            "status": "success",
            "device_id": payload.device_id,
            "site_id": payload.site_id,
            "dna_received": collect_device_dna(),
        }
    except HTTPException:
        raise
    except Exception:
        logger.error("Device registration failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to register device")
