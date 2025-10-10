from fastapi import APIRouter, Depends, HTTPException
from typing import Any, AsyncIterator, Dict, List, Optional
import logging
import asyncio
from homepot_client.client import HomepotClient
from pydantic import BaseModel
from homepot_client.database import close_database_service, get_database_service
from homepot_client.audit import AuditEventType, get_audit_logger
from homepot_client.models import DeviceType, JobPriority


client_instance: Optional[HomepotClient] = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


router = APIRouter()


class CreateDeviceRequest(BaseModel):
    """Request model for creating a new device."""

    device_id: str
    name: str
    device_type: str = DeviceType.POS_TERMINAL
    ip_address: Optional[str] = None
    config: Optional[Dict] = None

    class Config:
        """Pydantic model configuration with example data."""

        schema_extra = {
            "example": {
                "device_id": "pos-terminal-001",
                "name": "POS Terminal 1",
                "device_type": "pos_terminal",
                "ip_address": "192.168.1.10",
                "config": {"gateway_url": "https://payments.example.com"},
            }
        }


@router.post(
    "/sites/{site_id}/devices", tags=["Devices"], response_model=Dict[str, str]
)
async def create_device(
    site_id: str, device_request: CreateDeviceRequest
) -> Dict[str, str]:
    """Create a new device for a site."""
    try:
        db_service = await get_database_service()

        # Get site
        site = await db_service.get_site_by_site_id(site_id)
        if not site:
            raise HTTPException(status_code=404, detail=f"Site {site_id} not found")

        # Create device
        device = await db_service.create_device(
            device_id=device_request.device_id,
            name=device_request.name,
            device_type=device_request.device_type,
            site_id=int(site.id),
            ip_address=device_request.ip_address,
            config=device_request.config,
        )

        logger.info(f"Created device {device.device_id} for site {site_id}")
        return {
            "message": f"Device {device.device_id} created successfully",
            "device_id": str(device.device_id),
            "site_id": site_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create device: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create device: {e}")
