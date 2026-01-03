"""API endpoints for managing agents in the HomePot system."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from homepot.client import HomepotClient

client_instance: Optional[HomepotClient] = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


router = APIRouter()


def get_client() -> HomepotClient:
    """Dependency to get the client instance."""
    if client_instance is None:
        raise HTTPException(status_code=503, detail="Client not available")
    return client_instance


@router.get("/agents", tags=["Agents"])
async def list_agents() -> Dict[str, List[Dict]]:
    """List all active agents and their status from the database."""
    try:
        from sqlalchemy import and_, func, select

        from homepot.database import get_database_service
        from homepot.models import Device, DeviceStatus, HealthCheck

        db_service = await get_database_service()
        agents_status = []

        async with db_service.get_session() as session:
            # Get all devices
            result = await session.execute(select(Device))
            devices = result.scalars().all()

            if not devices:
                return {"agents": []}

            # Optimization: Fetch latest health checks in a single query
            # instead of N+1 queries
            device_ids = [d.id for d in devices]

            # Subquery to find the max timestamp for each device
            subq = (
                select(
                    HealthCheck.device_id,
                    func.max(HealthCheck.timestamp).label("max_ts"),
                )
                .where(HealthCheck.device_id.in_(device_ids))
                .group_by(HealthCheck.device_id)
                .subquery()
            )

            # Join to get the full row
            stmt = select(HealthCheck).join(
                subq,
                and_(
                    HealthCheck.device_id == subq.c.device_id,
                    HealthCheck.timestamp == subq.c.max_ts,
                ),
            )

            hc_result = await session.execute(stmt)
            latest_hcs = hc_result.scalars().all()

            # Map device_id -> HealthCheck
            hc_map = {hc.device_id: hc for hc in latest_hcs}

            for device in devices:
                latest_hc = hc_map.get(device.id)

                status_data = {
                    "device_id": device.device_id,
                    "state": device.status,
                    "config_version": device.firmware_version or "unknown",
                    "last_health_check": latest_hc.response_data if latest_hc else None,
                    "uptime": (
                        "running" if device.status == DeviceStatus.ONLINE else "stopped"
                    ),
                }
                agents_status.append(status_data)

        return {"agents": agents_status}

    except Exception as e:
        logger.error(f"Failed to list agents: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to list agents. Please check server logs."
        )


@router.get("/agents/{device_id}", tags=["Agents"])
async def get_agent_status(device_id: str) -> Dict[str, Any]:
    """Get detailed status of a specific agent from the database."""
    try:
        from sqlalchemy import desc, select

        from homepot.database import get_database_service
        from homepot.models import Device, DeviceStatus, HealthCheck

        db_service = await get_database_service()

        async with db_service.get_session() as session:
            # Get device
            result = await session.execute(
                select(Device).where(Device.device_id == device_id)
            )
            device = result.scalar_one_or_none()

            if not device:
                raise HTTPException(
                    status_code=404, detail=f"Agent for device {device_id} not found"
                )

            # Get latest health check
            hc_result = await session.execute(
                select(HealthCheck)
                .where(HealthCheck.device_id == device.id)
                .order_by(desc(HealthCheck.timestamp))
                .limit(1)
            )
            latest_hc = hc_result.scalar_one_or_none()

            return {
                "device_id": device.device_id,
                "state": device.status,
                "config_version": device.firmware_version or "unknown",
                "last_health_check": latest_hc.response_data if latest_hc else None,
                "uptime": (
                    "running" if device.status == DeviceStatus.ONLINE else "stopped"
                ),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to get agent status. Please check server logs.",
        )


@router.post("/agents/{device_id}/push", tags=["Agents"])
async def send_push_notification(
    device_id: str, notification_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Send a direct push notification to a POS agent for testing."""
    try:
        from homepot.agents import get_agent_manager

        agent_manager = await get_agent_manager()
        response = await agent_manager.send_push_notification(
            device_id, notification_data
        )

        if not response:
            raise HTTPException(
                status_code=404, detail=f"Agent for device {device_id} not found"
            )

        return {
            "message": f"Push notification sent to {device_id}",
            "device_id": device_id,
            "response": response,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send push notification: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to send push notification. Please check server logs.",
        )


@router.post("/agents/simulation/start", tags=["Agents"])
async def start_simulation() -> Dict[str, str]:
    """Start the device agent simulation."""
    try:
        from homepot.agents import get_agent_manager

        agent_manager = await get_agent_manager()
        if not agent_manager.is_running:
            await agent_manager.start()
        return {"message": "Simulation started"}
    except Exception as e:
        logger.error(f"Failed to start simulation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/simulation/stop", tags=["Agents"])
async def stop_simulation() -> Dict[str, str]:
    """Stop the device agent simulation."""
    try:
        from homepot.agents import get_agent_manager

        agent_manager = await get_agent_manager()
        if agent_manager.is_running:
            await agent_manager.stop()
        return {"message": "Simulation stopped"}
    except Exception as e:
        logger.error(f"Failed to stop simulation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/simulation/status", tags=["Agents"])
async def get_simulation_status() -> Dict[str, bool]:
    """Get the status of the device agent simulation."""
    try:
        from homepot.agents import get_agent_manager

        agent_manager = await get_agent_manager()
        return {"is_running": agent_manager.is_running}
    except Exception as e:
        logger.error(f"Failed to get simulation status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
