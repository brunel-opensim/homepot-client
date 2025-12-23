"""API endpoints for simulating device metrics submission (testing/demo purposes)."""

import logging
import random
from datetime import datetime
from typing import Dict

from fastapi import APIRouter, HTTPException

from homepot.app.schemas.schemas import (
    ApplicationMetrics,
    EnhancedHealthCheckData,
    HealthCheckRequest,
    NetworkMetrics,
    SystemMetrics,
)
from homepot.database import get_database_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/simulate/device/{device_id}/metrics", tags=["Testing"])
async def simulate_device_metrics(
    device_id: str,
    scenario: str = "healthy",
) -> Dict:
    """Simulate a device submitting metrics for testing purposes.

    Args:
        device_id: Device identifier to simulate
        scenario: Simulation scenario - "healthy", "high_cpu", "low_memory",
                 "high_errors", "degraded", "custom"

    Returns:
        Simulated metrics submission result

    Scenarios:
        - healthy: Normal operation (CPU 50-70%, Memory 60-75%, no errors)
        - high_cpu: CPU spike scenario (CPU 85-95%)
        - low_memory: Memory pressure (Memory 90-95%)
        - high_errors: Application errors (10-20 errors)
        - degraded: Multiple issues (high CPU + errors)
    """
    try:
        db_service = await get_database_service()

        # Verify device exists
        device = await db_service.get_device_by_device_id(device_id)
        if not device:
            raise HTTPException(
                status_code=404, detail=f"Device '{device_id}' not found"
            )

        # Generate metrics based on scenario
        metrics = _generate_metrics_for_scenario(scenario)
        system_metrics = SystemMetrics(**metrics["system"])
        app_metrics_obj = ApplicationMetrics(**metrics["app_metrics"])
        network_metrics = NetworkMetrics(**metrics["network"])

        enhanced_data = EnhancedHealthCheckData(
            status=metrics["status"],
            timestamp=datetime.utcnow().isoformat(),
            system=system_metrics,
            app_metrics=app_metrics_obj,
            network=network_metrics,
            environmental=None,
            custom=None,
        )

        # Create health check request
        health_check = HealthCheckRequest(
            is_healthy=metrics["is_healthy"],
            response_time_ms=metrics["response_time_ms"],
            status_code=200,
            endpoint="/health",
            response_data=enhanced_data.model_dump(exclude_none=True),
            error_message=None,
            system=system_metrics,
            app_metrics=app_metrics_obj,
            network=network_metrics,
        )

        # Store in database
        response_data_dict = (
            health_check.response_data
            if isinstance(health_check.response_data, dict)
            else enhanced_data.model_dump(exclude_none=True)
        )
        health_check_record = await db_service.create_health_check(
            device_id=int(device.id),
            device_name=str(device_id),
            is_healthy=health_check.is_healthy,
            response_time_ms=health_check.response_time_ms or 0,
            status_code=health_check.status_code or 200,
            endpoint=health_check.endpoint,
            response_data=response_data_dict,
        )

        logger.info(
            f"Simulated {scenario} metrics for device {device_id} "
            f"(ID: {health_check_record.id})"
        )

        return {
            "message": f"Simulated {scenario} metrics for device {device_id}",
            "device_id": device_id,
            "scenario": scenario,
            "health_check_id": health_check_record.id,
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to simulate metrics for {device_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to simulate device metrics. Please check server logs.",
        )


@router.post("/simulate/site/{site_id}/metrics", tags=["Testing"])
async def simulate_site_metrics(
    site_id: str,
    scenario: str = "mixed",
) -> Dict:
    """Simulate metrics for all devices in a site.

    Args:
        site_id: Site identifier
        scenario: Simulation scenario - "healthy", "mixed", "degraded"

    Returns:
        Summary of simulated metrics for all devices
    """
    try:
        db_service = await get_database_service()

        # Get site
        site = await db_service.get_site_by_site_id(site_id)
        if not site:
            raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")

        # Get all devices for the site
        devices = await db_service.get_devices_by_site_and_segment(str(site.site_id))

        if not devices:
            raise HTTPException(
                status_code=404, detail=f"No devices found for site '{site_id}'"
            )

        results = []
        scenarios_used = []

        for i, device in enumerate(devices):
            # Vary scenarios based on site-wide scenario
            if scenario == "mixed":
                # Mix of healthy and issues
                device_scenario = random.choice(
                    ["healthy", "healthy", "healthy", "high_cpu", "high_errors"]
                )
            elif scenario == "degraded":
                # Most devices have issues
                device_scenario = random.choice(
                    ["high_cpu", "low_memory", "high_errors", "degraded"]
                )
            else:
                device_scenario = scenario

            scenarios_used.append(device_scenario)

            # Generate and store metrics
            metrics = _generate_metrics_for_scenario(device_scenario)

            health_check_record = await db_service.create_health_check(
                device_id=int(device.id),
                device_name=str(device.device_id),
                is_healthy=metrics["is_healthy"],
                response_time_ms=metrics["response_time_ms"],
                status_code=200,
                endpoint="/health",
                response_data={
                    "status": metrics["status"],
                    "timestamp": datetime.utcnow().isoformat(),
                    "system": metrics["system"],
                    "app_metrics": metrics["app_metrics"],
                    "network": metrics["network"],
                },
            )

            results.append(
                {
                    "device_id": device.device_id,
                    "scenario": device_scenario,
                    "health_check_id": health_check_record.id,
                    "is_healthy": metrics["is_healthy"],
                }
            )

        logger.info(f"Simulated metrics for {len(results)} devices in site {site_id}")

        return {
            "message": (
                f"Simulated metrics for {len(results)} devices in site " f"{site_id}"
            ),
            "site_id": site_id,
            "total_devices": len(results),
            "scenarios_distribution": {
                s: scenarios_used.count(s) for s in set(scenarios_used)
            },
            "devices": results,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to simulate site metrics for {site_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to simulate site metrics. Please check server logs.",
        )


def _generate_metrics_for_scenario(scenario: str) -> Dict:
    """Generate realistic metrics for a given scenario.

    Args:
        scenario: Scenario name

    Returns:
        Dictionary with metrics for system, app, and network
    """
    base_uptime = random.randint(3600, 864000)  # 1 hour to 10 days

    scenarios = {
        "healthy": {
            "is_healthy": True,
            "status": "healthy",
            "response_time_ms": random.randint(100, 200),
            "system": {
                "cpu_percent": round(random.uniform(50, 70), 1),
                "memory_percent": round(random.uniform(60, 75), 1),
                "memory_used_mb": random.randint(1000, 1500),
                "memory_total_mb": 2048,
                "disk_percent": round(random.uniform(50, 65), 1),
                "disk_used_gb": round(random.uniform(100, 130), 1),
                "disk_total_gb": 200.0,
                "uptime_seconds": base_uptime,
            },
            "app_metrics": {
                "app_version": "1.2.3",
                "transactions_count": random.randint(100, 200),
                "errors_count": random.randint(0, 2),
                "warnings_count": random.randint(0, 5),
                "avg_response_time_ms": round(random.uniform(200, 400), 1),
                "active_connections": random.randint(2, 5),
            },
            "network": {
                "latency_ms": round(random.uniform(20, 50), 1),
                "rx_bytes": random.randint(500000, 2000000),
                "tx_bytes": random.randint(300000, 1000000),
                "connection_quality": "good",
            },
        },
        "high_cpu": {
            "is_healthy": False,
            "status": "degraded",
            "response_time_ms": random.randint(300, 500),
            "system": {
                "cpu_percent": round(random.uniform(85, 95), 1),
                "memory_percent": round(random.uniform(70, 80), 1),
                "memory_used_mb": random.randint(1400, 1600),
                "memory_total_mb": 2048,
                "disk_percent": round(random.uniform(55, 70), 1),
                "disk_used_gb": round(random.uniform(110, 140), 1),
                "disk_total_gb": 200.0,
                "uptime_seconds": base_uptime,
            },
            "app_metrics": {
                "app_version": "1.2.3",
                "transactions_count": random.randint(150, 250),
                "errors_count": random.randint(3, 7),
                "warnings_count": random.randint(8, 15),
                "avg_response_time_ms": round(random.uniform(500, 800), 1),
                "active_connections": random.randint(5, 10),
            },
            "network": {
                "latency_ms": round(random.uniform(50, 100), 1),
                "rx_bytes": random.randint(1000000, 3000000),
                "tx_bytes": random.randint(500000, 1500000),
                "connection_quality": "fair",
            },
        },
        "low_memory": {
            "is_healthy": False,
            "status": "degraded",
            "response_time_ms": random.randint(400, 600),
            "system": {
                "cpu_percent": round(random.uniform(65, 80), 1),
                "memory_percent": round(random.uniform(90, 95), 1),
                "memory_used_mb": random.randint(1840, 1945),
                "memory_total_mb": 2048,
                "disk_percent": round(random.uniform(60, 75), 1),
                "disk_used_gb": round(random.uniform(120, 150), 1),
                "disk_total_gb": 200.0,
                "uptime_seconds": base_uptime,
            },
            "app_metrics": {
                "app_version": "1.2.3",
                "transactions_count": random.randint(80, 150),
                "errors_count": random.randint(5, 10),
                "warnings_count": random.randint(10, 20),
                "avg_response_time_ms": round(random.uniform(600, 1000), 1),
                "active_connections": random.randint(3, 7),
            },
            "network": {
                "latency_ms": round(random.uniform(40, 80), 1),
                "rx_bytes": random.randint(700000, 2000000),
                "tx_bytes": random.randint(400000, 1200000),
                "connection_quality": "fair",
            },
        },
        "high_errors": {
            "is_healthy": False,
            "status": "unhealthy",
            "response_time_ms": random.randint(500, 800),
            "system": {
                "cpu_percent": round(random.uniform(60, 75), 1),
                "memory_percent": round(random.uniform(70, 85), 1),
                "memory_used_mb": random.randint(1400, 1740),
                "memory_total_mb": 2048,
                "disk_percent": round(random.uniform(65, 80), 1),
                "disk_used_gb": round(random.uniform(130, 160), 1),
                "disk_total_gb": 200.0,
                "uptime_seconds": base_uptime,
            },
            "app_metrics": {
                "app_version": "1.2.3",
                "transactions_count": random.randint(50, 120),
                "errors_count": random.randint(15, 30),
                "warnings_count": random.randint(20, 40),
                "avg_response_time_ms": round(random.uniform(800, 1500), 1),
                "active_connections": random.randint(1, 4),
            },
            "network": {
                "latency_ms": round(random.uniform(80, 150), 1),
                "rx_bytes": random.randint(400000, 1500000),
                "tx_bytes": random.randint(200000, 800000),
                "connection_quality": "poor",
            },
        },
        "degraded": {
            "is_healthy": False,
            "status": "degraded",
            "response_time_ms": random.randint(600, 900),
            "system": {
                "cpu_percent": round(random.uniform(85, 95), 1),
                "memory_percent": round(random.uniform(85, 92), 1),
                "memory_used_mb": random.randint(1740, 1884),
                "memory_total_mb": 2048,
                "disk_percent": round(random.uniform(75, 90), 1),
                "disk_used_gb": round(random.uniform(150, 180), 1),
                "disk_total_gb": 200.0,
                "uptime_seconds": base_uptime,
            },
            "app_metrics": {
                "app_version": "1.2.3",
                "transactions_count": random.randint(30, 80),
                "errors_count": random.randint(10, 20),
                "warnings_count": random.randint(15, 30),
                "avg_response_time_ms": round(random.uniform(1000, 2000), 1),
                "active_connections": random.randint(1, 3),
            },
            "network": {
                "latency_ms": round(random.uniform(100, 200), 1),
                "rx_bytes": random.randint(300000, 1000000),
                "tx_bytes": random.randint(150000, 500000),
                "connection_quality": "poor",
            },
        },
    }

    return scenarios.get(scenario, scenarios["healthy"])
