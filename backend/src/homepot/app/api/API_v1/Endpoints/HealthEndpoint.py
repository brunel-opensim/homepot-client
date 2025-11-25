"""API endpoints for managing Health in the HOMEPOT system."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from homepot.app.schemas.schemas import HealthCheckRequest
from homepot.client import HomepotClient
from homepot.database import get_database_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
device_metrics_router = APIRouter()  # Separate router for device metrics endpoints
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
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": asyncio.get_event_loop().time(),
        }


@router.get(
    "/sites/{site_id}/health", tags=["Health"], response_model=SiteHealthResponse
)
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
        from homepot.models import DeviceStatus

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
        logger.error(f"Failed to get site health: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to get site health. Please check server logs.",
        )


@router.get("/devices/{device_id}/health", tags=["Health"])
async def get_device_health(device_id: str) -> Dict[str, Any]:
    """Get detailed health status of a specific device."""
    try:
        from homepot.agents import get_agent_manager

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
        logger.error(f"Failed to get device health: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to get device health. Please check server logs.",
        )


@router.post("/devices/{device_id}/health")
async def trigger_health_check(device_id: str) -> Dict[str, Any]:
    """Trigger an immediate health check for a device."""
    try:
        from homepot.agents import get_agent_manager

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
        logger.error(f"Failed to trigger health check: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to trigger health check. Please check server logs.",
        )


@device_metrics_router.post("/devices/{device_id}/health", tags=["Health"])
async def submit_device_health_check(
    device_id: str, health_check: HealthCheckRequest
) -> Dict[str, Any]:
    """Submit device health check with enhanced metrics (alias for /metrics endpoint)."""
    return await submit_device_metrics(device_id, health_check)


@device_metrics_router.post("/devices/{device_id}/metrics", tags=["Health"])
async def submit_device_metrics(
    device_id: str, health_check: HealthCheckRequest
) -> Dict[str, Any]:
    """Submit device health check with enhanced metrics.

    This endpoint allows devices to report their health status including:
    - System metrics (CPU, memory, disk usage)
    - Application metrics (transactions, errors, performance)
    - Network metrics (latency, bandwidth)
    - Environmental metrics (temperature, humidity)

    All metric fields are optional to support gradual adoption.

    Args:
        device_id: Device identifier (e.g., "pos-terminal-001")
        health_check: Health check data with optional enhanced metrics

    Returns:
        Confirmation with stored health check ID

    Example:
        POST /api/v1/devices/pos-terminal-001/metrics
        {
            "is_healthy": true,
            "response_time_ms": 150,
            "status_code": 200,
            "endpoint": "/health",
            "response_data": {
                "status": "healthy",
                "timestamp": "2025-11-19T10:00:00Z",
                "system": {
                    "cpu_percent": 65.5,
                    "memory_percent": 80.0,
                    "disk_percent": 60.0
                },
                "app_metrics": {
                    "transactions_count": 150,
                    "errors_count": 2
                }
            }
        }
    """
    try:
        db_service = await get_database_service()

        # Try to find device (optional - devices can report before being registered)
        device = None
        try:
            device = await db_service.get_device_by_device_id(device_id)
        except Exception as e:
            logger.warning(f"Could not find device {device_id}: {e}")

        # Convert response_data to dict if present
        response_data_dict = (
            health_check.response_data if health_check.response_data else None
        )

        # Store health check in database (with or without device_id link)
        health_check_record = None
        health_check_id = None
        try:
            health_check_record = await db_service.create_health_check(
                device_id=device.id if device else None,
                device_name=device_id,
                is_healthy=health_check.is_healthy,
                response_time_ms=health_check.response_time_ms or 0,
                status_code=health_check.status_code or 200,
                endpoint=health_check.endpoint,
                response_data=response_data_dict,
            )
            health_check_id = health_check_record.id
            logger.info(
                f"Stored health check for device {device_id} "
                f"(ID: {health_check_id})"
            )
        except Exception as db_error:
            # Log metrics even if database storage fails (e.g., device not registered yet)
            logger.warning(
                f"Could not store health check for {device_id} in database: {db_error}. "
                f"Metrics logged but not persisted."
            )

        # Log metrics if present for monitoring
        if response_data_dict:
            metrics_summary = []
            if "system" in response_data_dict:
                system = response_data_dict["system"]
                if "cpu_percent" in system:
                    metrics_summary.append(f"CPU: {system['cpu_percent']}%")
                if "memory_percent" in system:
                    metrics_summary.append(f"MEM: {system['memory_percent']}%")
                if "disk_percent" in system:
                    metrics_summary.append(f"DISK: {system['disk_percent']}%")

            if "app_metrics" in response_data_dict:
                app = response_data_dict["app_metrics"]
                if "errors_count" in app and app["errors_count"] > 0:
                    metrics_summary.append(f"ERRORS: {app['errors_count']}")

            if metrics_summary:
                logger.info(f"Device {device_id} metrics: {', '.join(metrics_summary)}")

        return {
            "message": "Health check recorded successfully",
            "device_id": device_id,
            "health_check_id": health_check_id,
            "is_healthy": health_check.is_healthy,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to submit device metrics for {device_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to submit device metrics. Please check server logs.",
        )


@device_metrics_router.post("/simulator/device-metrics", tags=["Health", "Simulator"])
async def simulate_device_metrics(
    device_id: str = "simulated-pos-001", is_healthy: bool = True
) -> Dict[str, Any]:
    """Generate and submit realistic simulated device metrics for testing.

    This endpoint generates realistic device metrics without requiring actual devices.
    Useful for testing, demonstrations, and development.

    Args:
        device_id: Device identifier to simulate (default: "simulated-pos-001")
        is_healthy: Whether to simulate a healthy (true) or unhealthy (false) device

    Returns:
        Confirmation with simulated metrics and health check ID

    Example:
        POST /api/v1/simulator/device-metrics?device_id=test-pos-001&is_healthy=false
    """
    import random

    from homepot.app.schemas.schemas import (
        ApplicationMetrics,
        NetworkMetrics,
        SystemMetrics,
    )

    try:
        # Generate realistic metrics based on health status
        if is_healthy:
            cpu = round(random.uniform(20, 70), 1)
            memory = round(random.uniform(40, 75), 1)
            disk = round(random.uniform(30, 60), 1)
            errors = random.randint(0, 2)
            response_time = random.randint(50, 200)
        else:
            cpu = round(random.uniform(80, 98), 1)
            memory = round(random.uniform(85, 99), 1)
            disk = round(random.uniform(70, 95), 1)
            errors = random.randint(5, 20)
            response_time = random.randint(500, 2000)

        # Create metrics objects
        system_metrics = SystemMetrics(
            cpu_percent=cpu,
            memory_percent=memory,
            disk_percent=disk,
            memory_used_mb=int(memory * 20.48),  # Assuming 2GB total
            memory_total_mb=2048,
            disk_used_gb=round(disk * 2.0, 2),  # Assuming 200GB total
            disk_total_gb=200,
            uptime_seconds=random.randint(3600, 864000),  # 1 hour to 10 days
        )

        app_metrics = ApplicationMetrics(
            app_version="1.2.3",
            transactions_count=(
                random.randint(100, 500) if is_healthy else random.randint(0, 50)
            ),
            errors_count=errors,
            warnings_count=random.randint(0, 10),
            avg_response_time_ms=round(random.uniform(100, 500), 2),
            active_connections=random.randint(1, 10) if is_healthy else 0,
        )

        network_metrics = NetworkMetrics(
            latency_ms=round(
                random.uniform(10, 100) if is_healthy else random.uniform(200, 1000), 2
            ),
            rx_bytes=random.randint(100000, 10000000),
            tx_bytes=random.randint(50000, 5000000),
            connection_quality="good" if is_healthy else "poor",
        )

        # Create enhanced health check data as dict
        enhanced_data = {
            "status": "healthy" if is_healthy else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "system": system_metrics.model_dump(exclude_none=True),
            "app_metrics": app_metrics.model_dump(exclude_none=True),
            "network": network_metrics.model_dump(exclude_none=True),
        }

        # Create health check request
        health_check = HealthCheckRequest(
            is_healthy=is_healthy,
            response_time_ms=response_time,
            status_code=200 if is_healthy else 500,
            endpoint="/health",
            response_data=enhanced_data,
        )

        # Submit via the metrics endpoint
        result = await submit_device_metrics(device_id, health_check)

        # Add simulated metrics to response
        result["simulated_metrics"] = {
            "system": system_metrics.model_dump(),
            "app_metrics": app_metrics.model_dump(),
            "network": network_metrics.model_dump(),
        }
        result["simulation_note"] = "This data was generated for testing purposes"

        logger.info(
            f"Generated simulated metrics for {device_id} (healthy={is_healthy})"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to simulate device metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to simulate device metrics. Please check server logs.",
        )
