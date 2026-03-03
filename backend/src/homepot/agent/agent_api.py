"""API routes for agent-related operations in the Homepot backend."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from homepot.agent.utils.device_dna import collect_device_dna

logger = logging.getLogger(__name__)
router = APIRouter()


class DeviceRegister(BaseModel):
    """Schema for device registration request."""

    device_id: str
    site_id: str
    backend_url: str
    api_key: str


@router.post("/register")
async def register_device(payload: DeviceRegister) -> Dict[str, Any]:
    """Register a device and return collected device DNA information."""
    try:
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
