"""API endpoints for managing Device in the HomePot system."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from homepot.audit import AuditEventType, get_audit_logger
from homepot.client import HomepotClient
from homepot.database import get_database_service

client_instance: Optional[HomepotClient] = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


router = APIRouter()


class CreateDeviceRequest(BaseModel):
    """Request model for creating a new device."""

    site_id: str
    device_id: str
    name: str
    device_type: str
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    firmware_version: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "site_id": "site-123",
                "device_id": "pos-001",
                "name": "Main POS Terminal",
                "device_type": "pos_terminal",
                "ip_address": "192.168.1.100",
                "mac_address": "00:11:22:33:44:55",
                "firmware_version": "1.0.0",
            }
        }
    )


class UpdateDeviceRequest(BaseModel):
    """Request model for updating an existing device."""

    name: Optional[str] = None
    device_type: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    firmware_version: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Updated POS Terminal",
                "device_type": "pos_terminal",
                "ip_address": "192.168.1.101",
                "mac_address": "00:11:22:33:44:55",
                "firmware_version": "1.0.1",
            }
        }
    )


@router.post("/device", tags=["Devices"])
async def create_device(device_request: CreateDeviceRequest) -> Dict[str, Any]:
    """Create a new device."""
    try:
        db_service = await get_database_service()

        # Check if device already exists
        existing_device = await db_service.get_device_by_device_id(
            device_request.device_id
        )
        if existing_device:
            raise HTTPException(
                status_code=409,
                detail=f"Device {device_request.device_id} already exists",
            )

        # Verify site exists
        site = await db_service.get_site_by_site_id(device_request.site_id)
        if not site:
            raise HTTPException(
                status_code=404, detail=f"Site {device_request.site_id} not found"
            )

        # Create device
        device = await db_service.create_device(
            device_id=device_request.device_id,
            name=device_request.name,
            device_type=device_request.device_type,
            site_id=int(site.id),
            ip_address=device_request.ip_address,
            config={
                "mac_address": device_request.mac_address,
                "firmware_version": device_request.firmware_version,
            },
        )

        # Log audit event
        audit_logger = get_audit_logger()
        await audit_logger.log_event(
            AuditEventType.DEVICE_CREATED,
            f"Device '{device.name}' registered with ID {device.device_id}",
            site_id=int(site.id),
            device_id=int(device.id),
            new_values={
                "device_id": str(device.device_id),
                "name": str(device.name),
                "site_id": str(device.site_id),
                "type": str(device.device_type),
            },
        )

        return {
            "message": "Device created successfully",
            "device_id": device.device_id,
            "name": device.name,
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
        from sqlalchemy.orm import joinedload

        from homepot.models import Device

        async with db_service.get_session() as session:
            result = await session.execute(
                select(Device)
                .options(joinedload(Device.site))
                .where(Device.is_active.is_(True))
                .order_by(Device.created_at.desc())
            )
            devices = result.scalars().all()

            device_list = []
            for device in devices:
                device_list.append(
                    {
                        "site_id": device.site.site_id,
                        "device_id": device.device_id,
                        "name": device.name,
                        "device_type": device.device_type,
                        "status": device.status,
                        "ip_address": device.ip_address,
                        "is_monitored": device.is_monitored,
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
    """Get a specific Device by device_id."""
    try:
        db_service = await get_database_service()

        # Look up site by device_id
        device = await db_service.get_device_by_device_id(device_id)

        if not device:
            raise HTTPException(
                status_code=404, detail=f"Device '{device_id}' not found"
            )

        return {
            "site_id": device.site.site_id,
            "device_id": device.device_id,
            "name": device.name,
            "device_type": device.device_type,
            "ip_address": device.ip_address,
            "mac_address": device.config.get("mac_address") if device.config else None,
            "firmware_version": (
                device.config.get("firmware_version") if device.config else None
            ),
            "is_monitored": device.is_monitored,
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


@router.put("/device/{device_id}", tags=["Devices"])
async def update_device(
    device_id: str, device_request: UpdateDeviceRequest
) -> Dict[str, Any]:
    """Update an existing device."""
    try:
        db_service = await get_database_service()

        # Prepare config update
        config_update = {}
        if device_request.mac_address:
            config_update["mac_address"] = device_request.mac_address
        if device_request.firmware_version:
            config_update["firmware_version"] = device_request.firmware_version

        # Update device
        updated_device = await db_service.update_device(
            device_id=device_id,
            name=device_request.name,
            device_type=device_request.device_type,
            ip_address=device_request.ip_address,
            config=config_update if config_update else None,
        )

        if not updated_device:
            raise HTTPException(
                status_code=404, detail=f"Device '{device_id}' not found"
            )

        # Get site for audit logging (need integer ID)
        site_pk = int(updated_device.site_id)

        # Log audit event
        audit_logger = get_audit_logger()
        await audit_logger.log_event(
            AuditEventType.DEVICE_UPDATED,
            f"Device '{updated_device.name}' updated",
            device_id=int(updated_device.id),
            site_id=site_pk,
            new_values={
                "name": str(updated_device.name),
                "type": str(updated_device.device_type),
                "ip": str(updated_device.ip_address),
            },
        )

        return {
            "message": "Device updated successfully",
            "device_id": updated_device.device_id,
            "name": updated_device.name,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update device {device_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to update device. Please check server logs."
        )


@router.delete("/device/{device_id}", tags=["Devices"])
async def delete_device(device_id: str) -> Dict[str, Any]:
    """Delete a device and all associated data."""
    try:
        db_service = await get_database_service()

        success = await db_service.delete_device(device_id)

        if not success:
            raise HTTPException(
                status_code=404, detail=f"Device '{device_id}' not found"
            )

        return {"message": f"Device '{device_id}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete device {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.put("/device/{device_id}/monitor", tags=["Devices"])
async def toggle_device_monitor(device_id: str, monitor: bool) -> Dict[str, Any]:
    """Toggle the monitoring status of a device."""
    try:
        db_service = await get_database_service()

        from sqlalchemy import select

        from homepot.models import Device

        async with db_service.get_session() as session:
            result = await session.execute(
                select(Device).where(Device.device_id == device_id)
            )
            device = result.scalars().first()

            if not device:
                raise HTTPException(
                    status_code=404, detail=f"Device '{device_id}' not found"
                )

            device.is_monitored = monitor  # type: ignore
            await session.commit()

            return {
                "message": f"Device monitoring {'enabled' if monitor else 'disabled'}",
                "device_id": device.device_id,
                "is_monitored": device.is_monitored,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update device monitor status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/sites/{site_id}/devices", tags=["Devices"])
async def get_devices_by_site(site_id: str) -> List[Dict[str, Any]]:
    """Get all devices for a specific site.

    Args:
        site_id: The site's business ID (e.g., 'site-123')

    Returns:
        List of devices belonging to the site

    Raises:
        HTTPException: 404 if site not found
    """
    try:
        db_service = await get_database_service()

        # Verify site exists
        site = await db_service.get_site_by_site_id(site_id)
        if not site:
            raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")

        # Get devices for this site
        devices = await db_service.get_devices_by_site_id(site_id)

        return [
            {
                "site_id": site.site_id,
                "device_id": d.device_id,
                "name": d.name,
                "device_type": d.device_type,
                "status": d.status,
                "ip_address": d.ip_address,
                "is_monitored": d.is_monitored,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            }
            for d in devices
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get devices for site {site_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to get devices. Please check server logs."
        )
