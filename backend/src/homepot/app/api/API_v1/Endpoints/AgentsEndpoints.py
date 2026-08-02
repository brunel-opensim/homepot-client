"""API endpoints for managing agents in the HomePot system."""

import logging
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, HTTPException

from homepot.app.api.API_v1.Endpoints.DevicesEndpoints import _compute_connectivity
from homepot.client import HomepotClient
from homepot.models import ConnectivityState, HealthState

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
        from sqlalchemy import select

        from homepot.database import get_database_service
        from homepot.models import Device, HealthCheck

        db_service = await get_database_service()
        agents_status = []

        async with db_service.get_session() as session:
            # Get all devices
            result = await session.execute(select(Device))
            devices = result.scalars().all()

            if not devices:
                return {"agents": []}

            for device in devices:
                # Fetch latest health check for this device
                # Using a direct query per device is more reliable than complex joins
                # with timestamps across different DB backends (SQLite vs Postgres)
                stmt = (
                    select(HealthCheck)
                    .where(HealthCheck.device_id == device.id)
                    .order_by(HealthCheck.timestamp.desc())
                    .limit(1)
                )
                hc_result = await session.execute(stmt)
                latest_hc = hc_result.scalar_one_or_none()

                # Prepare health check data
                hc_data = None
                if latest_hc:
                    # Ensure response_data is a dict
                    if isinstance(latest_hc.response_data, dict):
                        hc_data = latest_hc.response_data.copy()
                    elif isinstance(latest_hc.response_data, str):
                        try:
                            import json

                            hc_data = json.loads(latest_hc.response_data)
                        except Exception:
                            logger.error(
                                f"Failed to parse JSON for device {device.device_id}",
                                exc_info=True,
                            )
                            hc_data = {}
                    else:
                        hc_data = {}

                    # Inject timestamp from the record if not present in the JSON data
                    # The frontend expects 'timestamp' at the root of the health check object
                    if "timestamp" not in hc_data and latest_hc.timestamp:
                        hc_data["timestamp"] = latest_hc.timestamp.isoformat()
                else:
                    # Log warning if no health check found for active device
                    if _compute_connectivity(device) == ConnectivityState.ONLINE.value:
                        logger.warning(
                            f"No health check found for online device {device.device_id} (PK: {device.id})"
                        )

                conn = _compute_connectivity(device)
                status_data = {
                    "device_id": device.device_id,
                    "lifecycle_state": device.lifecycle_state,
                    "connectivity_state": conn,
                    "health_state": device.health_state or HealthState.UNKNOWN.value,
                    "config_version": device.firmware_version or "unknown",
                    "last_health_check": hc_data,
                    "uptime": (
                        "running"
                        if conn == ConnectivityState.ONLINE.value
                        else "stopped"
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
        from homepot.models import Device, HealthCheck

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

            conn = _compute_connectivity(device)
            return {
                "device_id": device.device_id,
                "lifecycle_state": device.lifecycle_state,
                "connectivity_state": conn,
                "health_state": device.health_state or HealthState.UNKNOWN.value,
                "config_version": device.firmware_version or "unknown",
                "last_health_check": latest_hc.response_data if latest_hc else None,
                "uptime": (
                    "running" if conn == ConnectivityState.ONLINE.value else "stopped"
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
    """Send a direct push notification to a POS agent for testing.

    The composed payload is relayed to the device command queue so real or
    emulated device agents can consume it via the pending-commands channel,
    in addition to any in-process simulated agent.
    """
    from datetime import datetime, timezone

    action = str(notification_data.get("action") or "unknown")

    try:
        from homepot.database import get_database_service

        db_service = await get_database_service()
        device = await db_service.get_device_by_device_id(device_id)
        if device is not None:
            await db_service.create_device_command(
                device_id=cast(int, device.id),
                command_type=action,
                payload=notification_data,
            )
    except Exception as e:
        logger.warning(f"Failed to queue push command for {device_id}: {e}")

    try:
        from homepot.agents import get_agent_manager

        agent_manager = await get_agent_manager()
        response = await agent_manager.send_push_notification(
            device_id, notification_data
        )
    except Exception as e:
        logger.warning(f"In-process agent dispatch failed for {device_id}: {e}")
        response = None

    if response is None:
        response = {
            "status": "success",
            "message": f"Command '{action}' queued for device agent",
            "device_id": device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return {
        "message": f"Push notification sent to {device_id}",
        "device_id": device_id,
        "response": response,
    }


@router.post("/agents/simulation/start", tags=["Agents"])
async def start_simulation() -> Dict[str, str]:
    """Start the device agent simulation."""
    _require_simulation_enabled()
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
    _require_simulation_enabled()
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
    _require_simulation_enabled()
    try:
        from homepot.agents import get_agent_manager

        agent_manager = await get_agent_manager()
        return {"is_running": agent_manager.is_running}
    except Exception as e:
        logger.error(f"Failed to get simulation status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _require_simulation_enabled() -> None:
    """Raise 404 if agent simulation is disabled via ENABLE_AGENT_SIMULATION."""
    from homepot.config import get_settings

    if not get_settings().enable_agent_simulation:
        raise HTTPException(
            status_code=404,
            detail="Agent simulation is disabled (ENABLE_AGENT_SIMULATION=false)",
        )
