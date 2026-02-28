import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.utils.device_dna import collect_device_dna

logger = logging.getLogger(__name__)
agent_router = APIRouter()


class DeviceRegister(BaseModel):
    device_id: str
    site_id: str
    backend_url: str
    api_key: str


@agent_router.post("/register")
async def register_device(payload: DeviceRegister):
    try:
        return {
            "status": "success",
            "device_id": payload.device_id,
            "site_id": payload.site_id,
            "dna_received": collect_device_dna(payload),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Device registration failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to register device")
