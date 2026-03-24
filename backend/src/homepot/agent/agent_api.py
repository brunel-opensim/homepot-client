"""API routes for agent-related operations in the Homepot backend."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from homepot.agent.utils.device_dna import collect_device_dna
from homepot.app.auth_utils import authenticate_device_credentials
from homepot.database import get_db
from homepot.models import Site

logger = logging.getLogger(__name__)
router = APIRouter()


class DeviceRegister(BaseModel):
    """Schema for device registration request."""

    device_id: str
    site_id: str
    backend_url: str
    api_key: str


@router.post("/register")
async def register_device(
    payload: DeviceRegister, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Register a pre-authorized device and return collected device DNA."""
    try:
        device = authenticate_device_credentials(
            db=db,
            device_id=payload.device_id,
            api_key=payload.api_key,
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
            "dna_received": collect_device_dna(payload),
        }
    except HTTPException:
        raise
    except Exception:
        logger.error("Device registration failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to register device")
