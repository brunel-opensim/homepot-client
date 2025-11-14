"""API endpoints for managing Device in the HomePot system."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from homepot.client import HomepotClient
from homepot.database import get_database_service
from homepot.models import DeviceType

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

        json_schema_extra = {
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
        logger.error(f"Failed to create device: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to create device. Please check server logs."
        )


@router.get("/device", tags=["Devices"])
async def list_device() -> Dict[str, List[Dict]]:
    """List all devices."""
    try:
        db_service = await get_database_service()

        # For demo, we'll create a simple query (in real app, add pagination)
        from sqlalchemy import select

        from homepot.models import Device

        async with db_service.get_session() as session:
            result = await session.execute(
                select(Device)
                .where(Device.is_active.is_(True))
                .order_by(Device.created_at.desc())
            )
            devices = result.scalars().all()

            device_list = []
            for device in devices:
                device_list.append(
                    {
                        "site_id": device.site_id,
                        "device_id": device.device_id,
                        "name": device.name,
                        "ip_address": device.ip_address,
                        "created_at": (
                            device.created_at.isoformat() if device.created_at else None
                        ),
                    }
                )

            return {"devices": device_list}

    except Exception as e:
        logger.error(f"Failed to list device: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to list device. Please check server logs."
        )


@router.get("/device/{device_id}", tags=["Devices"])
async def get_device(device_id: str) -> Dict[str, Any]:
    """Get a specific device by device_id."""
    try:
        db_service = await get_database_service()

        # Look up device by device_id
        device = await db_service.get_device_by_device_id(device_id)

        if not device:
            raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")

        return {
            "site_id": device.site_id,
            "device_id": device.device_id,
            "name": device.name,
            "ip_address": device.ip_address,
            "created_at": device.created_at.isoformat() if device.created_at else None,
            "updated_at": device.updated_at.isoformat() if device.updated_at else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get Device {device_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to get Device. Please check server logs."
        )
