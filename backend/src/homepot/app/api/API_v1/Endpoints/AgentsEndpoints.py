"""API endpoints for managing agents in the HomePot system."""

import logging
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from homepot.app.api.API_v1.Endpoints.DevicesEndpoints import _compute_connectivity
from homepot.app.auth_utils import UserDict, require_user, verify_device_belongs_to_user
from homepot.client import HomepotClient
from homepot.database import get_db
from homepot.models import ConnectivityState, HealthState, User

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
        from sqlalchemy.orm import joinedload

        from homepot.app.models.AnalyticsModel import DeviceMetrics
        from homepot.database import get_database_service
        from homepot.models import Device, HealthCheck

        db_service = await get_database_service()
        agents_status = []

        async with db_service.get_session() as session:
            # Get all active devices (exclude suspended/unpaired so the Data
            # Collection page reflects only live, managed agents).
            result = await session.execute(
                select(Device)
                .options(joinedload(Device.site))
                .where(Device.is_active.is_(True))
            )
            devices = result.unique().scalars().all()

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
                    # No HealthCheck for this device — e.g. an emulator that
                    # reports telemetry (device_metrics) but not health checks.
                    # Fall back to the latest metrics so the Data Collection
                    # page shows live data for emulated devices too.
                    metrics_stmt = (
                        select(DeviceMetrics)
                        .where(DeviceMetrics.device_id == device.id)
                        .order_by(DeviceMetrics.timestamp.desc())
                        .limit(1)
                    )
                    latest_metrics = (
                        await session.execute(metrics_stmt)
                    ).scalar_one_or_none()
                    if latest_metrics:
                        extra: dict = (
                            latest_metrics.extra_metrics
                            if isinstance(latest_metrics.extra_metrics, dict)
                            else {}
                        )
                        hc_data = {
                            "metrics": {
                                "cpu_usage_percent": latest_metrics.cpu_percent,
                                "memory_usage_percent": latest_metrics.memory_percent,
                                "disk_usage_percent": latest_metrics.disk_percent,
                                "network_latency_ms": latest_metrics.network_latency_ms,
                                "error_rate": latest_metrics.error_rate,
                                "transaction_count": latest_metrics.transaction_count,
                                "transaction_volume": latest_metrics.transaction_volume,
                                "active_connections": latest_metrics.active_connections,
                                "uptime_seconds": extra.get("uptime_seconds"),
                            },
                            "timestamp": (
                                latest_metrics.timestamp.isoformat()
                                if latest_metrics.timestamp
                                else None
                            ),
                        }
                    else:
                        # Log warning if no health check found for active device
                        if (
                            _compute_connectivity(device)
                            == ConnectivityState.ONLINE.value
                        ):
                            logger.warning(
                                f"No health check found for online device {device.device_id}"
                            )

                conn = _compute_connectivity(device)
                status_data = {
                    "device_id": device.device_id,
                    "lifecycle_state": device.lifecycle_state,
                    "connectivity_state": conn,
                    "health_state": device.health_state or HealthState.UNKNOWN.value,
                    "config_version": device.firmware_version or "unknown",
                    "name": device.name,
                    "site_id": device.site.site_id if device.site else None,
                    "site_name": device.site.name if device.site else None,
                    "device_type": device.device_type,
                    "os_details": device.os_details,
                    "ip_address": device.local_ip or device.ip_address,
                    "enrollment_method": device.enrollment_method or "pre-provisioned",
                    "is_simulated": device.is_simulated,
                    "device_source": (
                        device.config.get("device_source") if device.config else None
                    ),
                    "last_seen": (
                        device.last_seen.isoformat() if device.last_seen else None
                    ),
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
    device_id: str,
    notification_data: Dict[str, Any],
    sync_db: Session = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Send a non-executable notification to a POS agent.

    Executable actions must use the authenticated, permission-gated device
    command endpoint instead.
    """
    from datetime import datetime, timezone

    from homepot.database import get_database_service

    db_service = await get_database_service()
    device = await db_service.get_device_by_device_id(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    db_user = cast(
        User, sync_db.query(User).filter(User.email == current_user["email"]).first()
    )
    verify_device_belongs_to_user(db_user, device, sync_db, minimum_role="operator")
    notification_data = {**notification_data, "action": "notification"}

    # Persist the push lifecycle record so the device can pick it up and ack it
    import uuid

    from homepot.app.models.AnalyticsModel import PushNotificationLog

    message_id = str(uuid.uuid4())
    notification_data = {**notification_data, "message_id": message_id}
    try:
        push_log = PushNotificationLog(
            message_id=message_id,
            device_id=device_id,
            provider="web_push",
            payload=notification_data,
            sent_at=datetime.utcnow(),
            status="sent",
        )
        sync_db.add(push_log)
        sync_db.commit()
    except Exception as e:
        logger.warning(f"Failed to persist push log for {device_id}: {e}")

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
            "message": "Notification accepted for device agent",
            "device_id": device_id,
            "message_id": message_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return {
        "message": f"Push notification sent to {device_id}",
        "device_id": device_id,
        "message_id": message_id,
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
