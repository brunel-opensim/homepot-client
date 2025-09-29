from fastapi import APIRouter, HTTPException, Depends
from typing import Any, Dict
from datetime import datetime
import logging
from homepot_client.client import HomepotClient
from typing import Any, AsyncIterator, Dict, List, Optional
import asyncio
from pydantic import BaseModel
from homepot_client.database import close_database_service, get_database_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
client_instance: Optional[HomepotClient] = None

class SiteHealthResponse(BaseModel):
    """Response model for site health status."""

    site_id: str
    total_devices: int
    healthy_devices: int
    offline_devices: int
    error_devices: int
    health_percentage: float
    status_summary: str
    devices: List[Dict]
    last_updated: str

def get_client() -> HomepotClient:
    """Dependency to get the client instance."""
    if client_instance is None:
        raise HTTPException(status_code=503, detail="Client not available")
    return client_instance

@router.get("/health", tags=["Health"])
async def health_check(client: HomepotClient = Depends(get_client)) -> Dict[str, Any]:
    """Health check endpoint for monitoring and load balancers."""
    try:
        is_connected = client.is_connected()
        version = client.get_version()

        return {
            "status": "healthy" if is_connected else "degraded",
            "client_connected": is_connected,
            "version": version,
            "timestamp": asyncio.get_event_loop().time(),
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": asyncio.get_event_loop().time(),
        }
@router.get("/sites/{site_id}/health", tags=["Health"], response_model=SiteHealthResponse)
async def get_site_health(site_id: str) -> SiteHealthResponse:
    """Get site health status (Step 5: '5/5 terminals healthy')."""
    try:
        db_service = await get_database_service()

        # Get site
        site = await db_service.get_site_by_site_id(site_id)
        if not site:
            raise HTTPException(status_code=404, detail=f"Site {site_id} not found")

        # Get all devices for the site
        devices = await db_service.get_devices_by_site_and_segment(int(site.id))

        if not devices:
            return SiteHealthResponse(
                site_id=site_id,
                total_devices=0,
                healthy_devices=0,
                offline_devices=0,
                error_devices=0,
                health_percentage=0.0,
                status_summary="No devices found",
                devices=[],
                last_updated=datetime.utcnow().isoformat(),
            )

        # Count device statuses
        from homepot_client.models import DeviceStatus

        healthy_count = sum(1 for d in devices if d.status == DeviceStatus.ONLINE)
        offline_count = sum(1 for d in devices if d.status == DeviceStatus.OFFLINE)
        error_count = sum(1 for d in devices if d.status == DeviceStatus.ERROR)

        total_count = len(devices)
        health_percentage = (
            (healthy_count / total_count * 100) if total_count > 0 else 0
        )

        # Create status summary
        if healthy_count == total_count:
            status_summary = f"{healthy_count}/{total_count} terminals healthy"
        elif healthy_count == 0:
            status_summary = f"All {total_count} terminals offline/error"
        else:
            status_summary = f"{healthy_count}/{total_count} terminals healthy"

        # Device details
        device_list = []
        for device in devices:
            device_list.append(
                {
                    "device_id": device.device_id,
                    "name": device.name,
                    "type": device.device_type,
                    "status": device.status,
                    "ip_address": device.ip_address,
                    "last_seen": (
                        device.last_seen.isoformat() if device.last_seen else None
                    ),
                }
            )

        return SiteHealthResponse(
            site_id=site_id,
            total_devices=total_count,
            healthy_devices=healthy_count,
            offline_devices=offline_count,
            error_devices=error_count,
            health_percentage=health_percentage,
            status_summary=status_summary,
            devices=device_list,
            last_updated=datetime.utcnow().isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get site health: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get site health: {e}")
    
@router.get("/devices/{device_id}/health", tags=["Health"])
async def get_device_health(device_id: str) -> Dict[str, Any]:
    """Get detailed health status of a specific device."""
    try:
        from homepot_client.agents import get_agent_manager

        agent_manager = await get_agent_manager()
        agent_status = await agent_manager.get_agent_status(device_id)

        if not agent_status:
            raise HTTPException(status_code=404, detail=f"Device {device_id} not found")

        # Get the last health check data
        health_data = agent_status.get("last_health_check")
        if not health_data:
            # Trigger a health check
            response = await agent_manager.send_push_notification(
                device_id, {"action": "health_check", "data": {}}
            )

            if response and response.get("health_check"):
                health_data = response["health_check"]
            else:
                raise HTTPException(status_code=503, detail="Health check failed")

        return {
            "device_id": device_id,
            "health": health_data,
            "agent_state": agent_status.get("state"),
            "last_updated": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get device health: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get device health: {e}")
    


@router.post("/devices/{device_id}/health")
async def trigger_health_check(device_id: str) -> Dict[str, Any]:
    """Trigger an immediate health check for a device."""
    try:
        from homepot_client.agents import get_agent_manager

        agent_manager = await get_agent_manager()

        # Send health check request to agent
        response = await agent_manager.send_push_notification(
            device_id, {"action": "health_check", "data": {}}
        )

        if not response:
            raise HTTPException(status_code=404, detail=f"Device {device_id} not found")

        if response.get("status") != "success":
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Health check failed: {response.get('message', 'Unknown error')}"
                ),
            )

        return {
            "message": f"Health check completed for {device_id}",
            "device_id": device_id,
            "health": response.get("health_check"),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger health check: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to trigger health check: {e}"
        )