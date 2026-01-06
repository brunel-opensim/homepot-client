"""Device Agent Simulation for HOMEPOT Client.

This module implements mock device agents that simulate real-world device behavior:
- Respond to push notifications
- Download and apply configuration updates
- Run health checks and report status
- Handle various error scenarios realistically

Note: This file uses the standard 'random' module for device simulation purposes only,
not for cryptographic operations. S311 warnings are expected and acceptable here.
"""

# flake8: noqa: S311

import asyncio
import logging
import math
import random  # nosec - Used for device simulation, not cryptographic purposes
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, cast

from sqlalchemy import select

from homepot.app.models.AnalyticsModel import (
    ConfigurationHistory,
    DeviceMetrics,
    DeviceStateHistory,
)
from homepot.audit import AuditEventType, get_audit_logger
from homepot.database import get_database_service
from homepot.error_logger import log_error
from homepot.models import Device, DeviceStatus, Job, JobPriority, JobStatus

logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    """Agent states for simulation."""

    IDLE = "idle"
    DOWNLOADING = "downloading"
    UPDATING = "updating"
    RESTARTING = "restarting"
    HEALTH_CHECK = "health_check"
    ERROR = "error"


class DeviceAgentSimulator:
    """Simulates a device agent that responds to push notifications and runs health checks.

    This simulates realistic device behavior:
    1. Receives push notification from orchestrator
    2. Downloads new configuration from provided URL
    3. Validates and applies configuration
    4. Restarts application
    5. Runs health check
    6. Sends ACK back to HOMEPOT
    """

    def __init__(self, device_id: str, device_type: str = "device"):
        """Initialize a device agent with device configuration.

        Args:
            device_id: Unique identifier for the device
            device_type: Type of device, defaults to "device"
        """
        self.device_id = device_id
        self.device_type = device_type
        self.state = AgentState.IDLE
        self.current_config_version = "1.0.0"
        self.last_health_check: Optional[Dict[str, Any]] = None
        self.error_rate = 0.1  # 10% chance of errors for realistic simulation
        self.response_time_ms = random.randint(100, 500)  # nosec - simulation only
        self.is_running = False

        # Simulate device characteristics
        self.device_info = {
            "model": "Generic-Device-X1",
            "firmware": "2.4.1",
            "os": "Linux ARM",
            "memory_mb": 2048,
            "storage_gb": 16,
            "uptime_hours": random.randint(1, 720),  # nosec - simulation only
        }

        # Simulation counters
        self.transactions_today = random.randint(50, 100)
        self.transaction_volume = random.uniform(1000.0, 5000.0)
        self.uptime_seconds = random.randint(3600, 86400 * 7)
        self.device_int_id: Optional[int] = None  # Cache for database integer ID

        logger.info(f"Device Agent {device_id} ({device_type}) initialized")

    async def _get_device_db_id(self) -> Optional[int]:
        """Resolve database integer ID for this device."""
        if self.device_int_id is not None:
            return self.device_int_id

        try:
            db_service = await get_database_service()
            from sqlalchemy import select

            from homepot.models import Device

            async with db_service.get_session() as session:
                result = await session.execute(
                    select(Device.id).where(Device.device_id == self.device_id)
                )
                self.device_int_id = result.scalar_one_or_none()
                return self.device_int_id
        except Exception:
            return None

    async def start(self) -> None:
        """Start the agent simulator."""
        self.is_running = True
        logger.info(f"Agent {self.device_id} started")

        # Audit Log: Agent Started
        try:
            audit = get_audit_logger()
            db_id = await self._get_device_db_id()
            await audit.log_event(
                event_type=AuditEventType.AGENT_STARTED,
                description=f"Device Agent {self.device_id} started simulation",
                device_id=db_id,
                event_metadata={"device_id": self.device_id},
            )
        except Exception as e:
            logger.warning(f"Failed to audit log agent start: {e}")

        # Start health check loop
        asyncio.create_task(self._health_check_loop())

    async def stop(self) -> None:
        """Stop the agent simulator."""
        self.is_running = False
        logger.info(f"Agent {self.device_id} stopped")

        # Audit Log: Agent Stopped
        try:
            audit = get_audit_logger()
            db_id = await self._get_device_db_id()
            await audit.log_event(
                event_type=AuditEventType.AGENT_STOPPED,
                description=f"Device Agent {self.device_id} stopped simulation",
                device_id=db_id,
                event_metadata={"device_id": self.device_id},
            )
        except Exception as e:
            logger.warning(f"Failed to audit log agent stop: {e}")

    async def handle_push_notification(
        self, notification_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle incoming push notification and simulate agent response.

        This simulates the complete agent workflow:
        1. Receive push notification
        2. Download configuration
        3. Apply configuration
        4. Restart services
        5. Run health check
        6. Send ACK response
        """
        try:
            action = notification_data.get("action", "unknown")
            logger.info(f"Agent {self.device_id} received push notification: {action}")

            # Simulate processing time
            await asyncio.sleep(0.2)

            action = notification_data.get("action", "")
            data = notification_data.get("data", {})
            config_url = data.get("config_url", "")
            config_version = data.get("config_version", "")

            if action == "update_pos_payment_config":
                return await self._handle_config_update(
                    config_url, config_version, data
                )
            elif action == "restart_pos_app":
                return await self._handle_restart()
            elif action == "health_check":
                return await self._handle_health_check()
            else:
                return {
                    "status": "error",
                    "message": f"Unknown action: {action}",
                    "device_id": self.device_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        except Exception as e:
            logger.error(
                f"Agent {self.device_id} error handling push notification: {e}"
            )
            # Log error for AI training
            await log_error(
                category="external_service",
                severity="error",
                error_message=f"Agent {self.device_id} failed to handle push notification",
                exception=e,
                device_id=self.device_id,
                context={"action": action, "notification_data": notification_data},
            )
            return {
                "status": "error",
                "message": "Internal agent error occurred",
                "device_id": self.device_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def _handle_config_update(
        self,
        config_url: str,
        config_version: str,
        config_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Simulate configuration update process."""
        try:
            # Step 1: Download configuration
            self.state = AgentState.DOWNLOADING
            logger.debug(f"Agent {self.device_id} downloading config from {config_url}")
            await asyncio.sleep(random.uniform(0.5, 2.0))  # Simulate download time

            # Simulate download failures (5% chance)
            if random.random() < 0.05:
                raise Exception("Failed to download configuration: Connection timeout")

            # Step 2: Validate configuration
            logger.debug(
                f"Agent {self.device_id} validating config version {config_version}"
            )

            # Audit Log: Config Update
            db_id = await self._get_device_db_id()
            await get_audit_logger().log_event(
                event_type=AuditEventType.CONFIG_UPDATE_APPLIED,
                description=f"Configuration update {config_version} applied",
                device_id=db_id,
                event_metadata={"device_id": self.device_id, "version": config_version},
            )

            await asyncio.sleep(0.2)

            # Simulate validation failures (3% chance)
            if random.random() < 0.03:
                raise Exception(
                    "Configuration validation failed: Invalid payment gateway settings"
                )

            # Step 3: Apply configuration
            self.state = AgentState.UPDATING
            logger.debug(f"Agent {self.device_id} applying configuration")
            await asyncio.sleep(random.uniform(0.3, 1.0))

            # Step 4: Restart POS application
            self.state = AgentState.RESTARTING
            logger.debug(f"Agent {self.device_id} restarting POS application")
            await asyncio.sleep(random.uniform(1.0, 3.0))  # Realistic restart time

            # Audit Log: Device Restart
            db_id = await self._get_device_db_id()
            await get_audit_logger().log_event(
                event_type=AuditEventType.DEVICE_STATUS_CHANGED,
                description=f"POS Application restarted remotely",
                device_id=db_id,
                event_metadata={"device_id": self.device_id, "action": "restart"},
            )

            # Simulate restart failures (2% chance)
            if random.random() < 0.02:
                raise Exception(
                    "POS application failed to restart: Service dependency error"
                )

            # Step 5: Run health check
            self.state = AgentState.HEALTH_CHECK
            health_result = await self._run_health_check()

            # Update current config version
            old_version = self.current_config_version
            self.current_config_version = config_version
            self.state = AgentState.IDLE

            # Log configuration change for AI training
            try:
                db_service = await get_database_service()

                # Determine parameter name and value based on input data
                param_name = "config_version"
                new_val = {"version": config_version, "url": config_url}

                if config_data:
                    # Identify custom fields (excluding standard ones)
                    custom_keys = [
                        k
                        for k in config_data.keys()
                        if k not in ["config_url", "config_version"]
                    ]
                    if custom_keys:
                        param_name = ", ".join(custom_keys)
                        new_val = config_data

                async with db_service.get_session() as session:
                    config_history = ConfigurationHistory(
                        timestamp=datetime.utcnow(),
                        entity_type="device",
                        entity_id=self.device_id,
                        parameter_name=param_name,
                        old_value={"version": old_version},
                        new_value=new_val,
                        changed_by="system",
                        change_reason="Push notification config update",
                        change_type="automated",
                        performance_before={
                            "status": health_result.get("status"),
                            "response_time_ms": health_result.get("response_time_ms"),
                        },
                    )
                    session.add(config_history)
                    await session.flush()  # Get ID

                    # Schedule post-update performance monitoring
                    asyncio.create_task(
                        self._monitor_post_update_performance(
                            cast(int, config_history.id)
                        )
                    )

                    logger.info(
                        f"Logged config change for {self.device_id}: {old_version} → {config_version}"
                    )
            except Exception as log_err:
                logger.error(
                    f"Failed to log configuration history: {log_err}", exc_info=True
                )
                # Return this error in the response for debugging
                return {
                    "status": "success",
                    "message": "Configuration updated (DB Log Failed)",
                    "warning": str(log_err),
                    "device_id": self.device_id,
                    "config_version": config_version,
                    "health_check": health_result,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            # Step 6: Send success ACK
            return {
                "status": "success",
                "message": "Configuration updated successfully",
                "device_id": self.device_id,
                "config_version": config_version,
                "health_check": health_result,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "processing_time_ms": random.randint(2000, 6000),
            }

        except Exception as e:
            self.state = AgentState.ERROR
            await asyncio.sleep(1.0)  # Error recovery time
            self.state = AgentState.IDLE

            # Log error for AI training
            await log_error(
                category="external_service",
                severity="error",
                error_message=f"Agent {self.device_id} failed to apply configuration update",
                exception=e,
                device_id=self.device_id,
                context={
                    "config_url": config_url,
                    "config_version": config_version,
                    "current_version": self.current_config_version,
                },
            )

            return {
                "status": "error",
                "message": "Configuration update failed",
                "device_id": self.device_id,
                "config_version": self.current_config_version,  # Keep old version
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def _monitor_post_update_performance(self, config_history_id: int) -> None:
        """Monitor performance after a configuration update."""
        try:
            # Wait for a simulated "settling period" (e.g., 5 seconds in simulation time)
            await asyncio.sleep(5)

            # Run a new health check
            health_result = await self._run_health_check()

            # Update the configuration history record
            db_service = await get_database_service()
            async with db_service.get_session() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(ConfigurationHistory).where(
                        ConfigurationHistory.id == config_history_id
                    )
                )
                config_history = result.scalar_one_or_none()

                if config_history:
                    config_history.performance_after = {  # type: ignore
                        "status": health_result.get("status"),
                        "response_time_ms": health_result.get("response_time_ms"),
                    }
                    config_history.was_successful = health_result.get("status") == "healthy"  # type: ignore
                    session.add(config_history)
                    logger.info(
                        f"Updated post-change performance for config history {config_history_id}"
                    )

        except Exception as e:
            logger.error(f"Failed to monitor post-update performance: {e}")

    async def _handle_restart(self) -> Dict[str, Any]:
        """Simulate POS application restart."""
        try:
            self.state = AgentState.RESTARTING
            logger.debug(f"Agent {self.device_id} restarting application")
            await asyncio.sleep(random.uniform(2.0, 5.0))

            # Simulate restart failures (5% chance)
            if random.random() < 0.05:
                raise Exception("Application restart failed")

            health_result = await self._run_health_check()
            self.state = AgentState.IDLE

            return {
                "status": "success",
                "message": "Application restarted successfully",
                "device_id": self.device_id,
                "health_check": health_result,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            self.state = AgentState.ERROR
            await asyncio.sleep(2.0)
            self.state = AgentState.IDLE

            # Log error for AI training
            await log_error(
                category="external_service",
                severity="error",
                error_message=f"Agent {self.device_id} failed to restart application",
                exception=e,
                device_id=self.device_id,
                context={"action": "restart_application"},
            )

            return {
                "status": "error",
                "message": "Application restart failed",
                "device_id": self.device_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def _handle_health_check(self) -> Dict[str, Any]:
        """Handle explicit health check request."""
        health_result = await self._run_health_check()

        return {
            "status": "success",
            "message": "Health check completed",
            "device_id": self.device_id,
            "health_check": health_result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _run_health_check(self) -> Dict[str, Any]:
        """Run comprehensive health check."""
        self.state = AgentState.HEALTH_CHECK
        try:
            await asyncio.sleep(random.uniform(0.1, 0.5))

            # Simulate various health scenarios
            scenarios: List[Dict[str, Any]] = [
                {"healthy": True, "weight": 0.85},  # 85% healthy
                {"healthy": False, "error": "Payment gateway timeout", "weight": 0.08},
                {
                    "healthy": False,
                    "error": "Database connection failed",
                    "weight": 0.04,
                },
                {"healthy": False, "error": "Low disk space warning", "weight": 0.03},
            ]

            # Choose scenario based on weights
            rand = random.random()
            cumulative = 0
            selected_scenario = scenarios[0]

            for scenario in scenarios:
                cumulative += scenario["weight"]
                if rand <= cumulative:
                    selected_scenario = scenario
                    break

            is_healthy = selected_scenario["healthy"]

            # Increment counters
            self.transactions_today += random.randint(0, 2)
            self.transaction_volume += random.uniform(0.0, 150.0)
            self.uptime_seconds += 5  # Approximate check interval

            # Generate realistic sine-wave based metrics (1-minute cycle for visibility)
            now = datetime.now(timezone.utc)
            # Cycle position 0..2pi over 60 seconds
            cycle_position = (now.second / 60.0) * 2 * math.pi
            # Factor oscillates 0.0 to 1.0 (smooth wave)
            load_factor = (math.sin(cycle_position) + 1) / 2

            # Calculate metrics based on load factor + reduced noise for smoothness
            cpu_val = (
                20 + (50 * load_factor) + random.uniform(-0.5, 0.5)
            )  # Minimal noise
            mem_val = (
                40 + (30 * load_factor) + random.uniform(-0.2, 0.2)
            )  # Ultra smooth
            net_val = 20 + (80 * load_factor) + random.uniform(0, 2)  # Micro jitter

            # Base error rate is low
            err_val = random.uniform(0.00, 0.02)

            # ANOMALY SIMULATION: Occasionally spike metrics to trigger AI alerts
            # 2% chance per check to spike CPU > 90% (threshold)
            if random.random() < 0.02:
                cpu_val = random.uniform(92.0, 99.0)

            # 2% chance per check to spike Latency > 500ms (threshold)
            if random.random() < 0.02:
                net_val = random.uniform(550.0, 1200.0)

            # 1% chance per check to spike Error Rate > 5% (threshold)
            if random.random() < 0.01:
                err_val = random.uniform(0.06, 0.15)

            # Generate realistic health data
            health_data: Dict[str, Any] = {
                "status": "healthy" if is_healthy else "unhealthy",
                "config_version": self.current_config_version,
                "last_restart": (
                    datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 48))
                ).isoformat(),
                "response_time_ms": self.response_time_ms,
                "device_info": self.device_info,
                "services": {
                    "pos_app": "running" if is_healthy else "error",
                    "payment_gateway": "connected" if is_healthy else "disconnected",
                    "database": "online" if is_healthy else "offline",
                    "network": "connected",
                },
                "metrics": {
                    "cpu_usage_percent": round(max(0, min(100, cpu_val)), 1),
                    "memory_usage_percent": round(max(0, min(100, mem_val)), 1),
                    "disk_usage_percent": random.randint(20, 60),
                    "transactions_today": self.transactions_today,
                    "uptime_seconds": self.uptime_seconds,
                    # New metrics for AI training
                    "network_latency_ms": round(max(0, net_val), 1),
                    "transaction_volume": round(self.transaction_volume, 2),
                    "error_rate": err_val,
                    "active_connections": int(10 + (40 * load_factor)),
                    "queue_depth": int(2 + (18 * load_factor)),
                },
            }

            if not is_healthy:
                health_data["error"] = selected_scenario["error"]
                health_data["services"]["pos_app"] = "error"

                # Log the simulated error to the error_logs table so it shows up in "Live Logs"
                await log_error(
                    category="simulation",
                    severity="error",
                    error_message=f"Agent simulation error: {health_data['error']}",
                    exception=None,  # No real exception, just simulated
                    device_id=self.device_id,
                    context={"health_data": health_data},
                )
            else:
                # Log INFO messages frequently to keep the live log stream active (40% chance)
                if random.random() < 0.40:
                    await log_error(
                        category="system",
                        severity="info",
                        error_message="Routine health check passed successfully",
                        exception=None,
                        device_id=self.device_id,
                        context={"metrics": health_data["metrics"]},
                    )

            # Audit Log: Occasional System Maintenance (5% chance)
            if random.random() < 0.05:
                maintenance_actions = [
                    "Local cache cleared",
                    "Log rotation completed",
                    "Security policies updated",
                    "NTP time synchronization",
                    "Service discovery refresh",
                ]
                action = random.choice(maintenance_actions)
                try:
                    db_id = await self._get_device_db_id()
                    await get_audit_logger().log_event(
                        event_type=(
                            AuditEventType.SYSTEM_STARTUP
                            if "boot" in action
                            else AuditEventType.DEVICE_STATUS_CHANGED
                        ),
                        description=f"Automated maintenance: {action}",
                        device_id=db_id,
                        event_metadata={"device_id": self.device_id},
                    )
                except Exception:
                    pass

            self.last_health_check = health_data

            # Update device status in database
            try:
                db_service = await get_database_service()

                # Use a single session for all database operations
                async with db_service.get_session() as db:
                    # Determine new status based on health
                    new_status = (
                        DeviceStatus.ONLINE if is_healthy else DeviceStatus.ERROR
                    )
                    from sqlalchemy import select, update

                    from homepot.models import Device

                    # Get device and its current status before updating
                    device_result = await db.execute(
                        select(Device).where(Device.device_id == self.device_id)
                    )
                    device = device_result.scalar_one_or_none()

                    if device:
                        previous_status = device.status

                        # Update device status only if changed
                        if previous_status != new_status:
                            stmt = (
                                update(Device)
                                .where(Device.device_id == self.device_id)
                                .values(status=new_status)
                            )
                            await db.execute(stmt)

                            # Log state transition for AI training
                            reason = (
                                "Health check: healthy"
                                if is_healthy
                                else f"Health check: {health_data.get('error', 'unhealthy')}"
                            )
                            state_history = DeviceStateHistory(
                                timestamp=datetime.utcnow(),
                                device_id=int(device.id),  # Use Integer ID
                                previous_state=previous_status,
                                new_state=new_status,
                                changed_by="system",
                                reason=reason,
                                extra_data={
                                    "response_time_ms": self.response_time_ms,
                                    "health_status": (
                                        "healthy" if is_healthy else "unhealthy"
                                    ),
                                },
                            )
                            db.add(state_history)
                            logger.info(
                                f"Device {self.device_id} state changed: {previous_status} → {new_status}"
                            )

                    if device:
                        # Create health check record
                        from homepot.models import HealthCheck

                        health_check = HealthCheck(
                            device_id=int(device.id),  # type: ignore[arg-type]
                            is_healthy=is_healthy,
                            response_time_ms=self.response_time_ms,
                            status_code=200 if is_healthy else 500,
                            endpoint="/health",
                            response_data=health_data,
                        )
                        db.add(health_check)

                        # Save device metrics to database for AI training
                        device_metrics = DeviceMetrics(
                            timestamp=datetime.utcnow(),  # Use timezone-naive for compatibility
                            device_id=int(device.id),  # Use Integer ID
                            cpu_percent=health_data["metrics"]["cpu_usage_percent"],
                            memory_percent=health_data["metrics"][
                                "memory_usage_percent"
                            ],
                            disk_percent=health_data["metrics"]["disk_usage_percent"],
                            transaction_count=health_data["metrics"][
                                "transactions_today"
                            ],
                            network_latency_ms=health_data["metrics"][
                                "network_latency_ms"
                            ],
                            transaction_volume=health_data["metrics"][
                                "transaction_volume"
                            ],
                            error_rate=health_data["metrics"]["error_rate"],
                            active_connections=health_data["metrics"][
                                "active_connections"
                            ],
                            queue_depth=health_data["metrics"]["queue_depth"],
                            extra_metrics={
                                "uptime_seconds": health_data["metrics"][
                                    "uptime_seconds"
                                ],
                                "services": health_data["services"],
                                "device_info": health_data["device_info"],
                            },
                        )
                        db.add(device_metrics)

                        # Update Device Last Seen
                        # device object is already attached to the session
                        device.last_seen = datetime.now(timezone.utc)  # type: ignore[assignment]
                        # Ensure status is consistent
                        device.status = "online" if is_healthy else "offline"  # type: ignore[assignment]
                        db.add(device)

                        await db.commit()
                        logger.info(f"Saved device metrics for {self.device_id}")

            except Exception as e:
                logger.error(f"Failed to save device metrics for {self.device_id}: {e}")
                # Log error for AI training
                await log_error(
                    category="database",
                    severity="warning",
                    error_message=f"Failed to save device metrics for {self.device_id}",
                    exception=e,
                    device_id=self.device_id,
                    context={"action": "save_device_metrics"},
                )

            return health_data
        finally:
            self.state = AgentState.IDLE

    async def _health_check_loop(self) -> None:
        """Periodic health check loop (every 2 seconds)."""
        while self.is_running:
            try:
                await asyncio.sleep(2)  # Check every 2 seconds
                if self.state == AgentState.IDLE:
                    await self._run_health_check()
                    await self._simulate_background_jobs()
            except Exception as e:
                logger.error(f"Health check loop error for {self.device_id}: {e}")
                # Log error for AI training
                await log_error(
                    category="external_service",
                    severity="warning",
                    error_message=f"Health check loop error for {self.device_id}",
                    exception=e,
                    device_id=self.device_id,
                    context={"action": "health_check_loop"},
                )
                await asyncio.sleep(2)  # Short retry delay

    async def _simulate_background_jobs(self) -> None:
        """Simulate execution of background system jobs."""
        # 5% chance per 2s check (~1 per 40s) to create a historical job
        if random.random() < 0.05:
            try:
                db_id = await self._get_device_db_id()
                if not db_id:
                    return

                job_types = [
                    ("Log Rotation", JobStatus.COMPLETED),
                    ("Firmware Check", JobStatus.COMPLETED),
                    ("Cache Pruning", JobStatus.COMPLETED),
                    ("Metric Upload", JobStatus.COMPLETED),
                    ("Security Scan", JobStatus.FAILED),
                ]
                action, status = random.choice(job_types)

                error_msg = None
                if status == JobStatus.FAILED:
                    error_msg = "Timeout waiting for resource"

                logger.debug(f"Simulating job {action} for {self.device_id}")

                db_service = await get_database_service()

                # We need UUID
                import uuid

                from sqlalchemy import select

                from homepot.models import Device

                async with db_service.get_session() as session:
                    # Get site_id
                    dev_res = await session.execute(
                        select(Device).where(Device.id == db_id)
                    )
                    device = dev_res.scalar_one_or_none()
                    if not device or not device.site_id:
                        return

                    job = Job(
                        job_id=str(uuid.uuid4()),
                        action=action,
                        description=f"Automated background task: {action}",
                        status=status,
                        priority=JobPriority.LOW,
                        device_id=db_id,
                        site_id=device.site_id,
                        created_by=1,  # Assume system user ID 1
                        created_at=datetime.utcnow()
                        - timedelta(seconds=random.randint(2, 30)),
                        started_at=datetime.utcnow()
                        - timedelta(seconds=random.randint(1, 10)),
                        completed_at=datetime.utcnow(),
                        error_message=error_msg,
                        result={"trigger": "simulation"},
                    )
                    session.add(job)

            except Exception as e:
                logger.warning(f"Failed to simulate job: {e}")


class AgentManager:
    """Manages all device agent simulators."""

    def __init__(self) -> None:
        """Initialize the agent manager with empty agent registry."""
        self.agents: Dict[str, DeviceAgentSimulator] = {}
        self.is_running = False

    async def start(self) -> None:
        """Start the agent manager and discover existing devices."""
        self.is_running = True
        logger.info("Agent Manager started")

        # Discover and start agents for existing devices
        await self._discover_and_start_agents()

        # Start monitoring for new devices
        asyncio.create_task(self._device_monitor_loop())

    async def stop(self) -> None:
        """Stop all agents."""
        self.is_running = False
        logger.info("Stopping Agent Manager")

        # Stop all agents
        for agent in self.agents.values():
            await agent.stop()

        self.agents.clear()
        logger.info("Agent Manager stopped")

    async def _discover_and_start_agents(self) -> None:
        """Discover existing devices and start agents for them."""
        try:
            db_service = await get_database_service()

            # Get all active POS devices
            from sqlalchemy import select

            from homepot.models import Device, DeviceType

            async with db_service.get_session() as session:
                # Query for both POS_TERMINAL and IOT_SENSOR devices
                result = await session.execute(
                    select(Device).where(
                        Device.is_active.is_(True),
                        Device.device_type.in_(
                            [DeviceType.POS_TERMINAL, DeviceType.IOT_SENSOR]
                        ),
                    )
                )
                devices = result.scalars().all()

                for device in devices:
                    await self._start_agent_for_device(
                        str(device.device_id), str(device.name)
                    )

        except Exception as e:
            logger.error(f"Failed to discover devices: {e}")
            # Log error for AI training
            await log_error(
                category="database",
                severity="error",
                error_message="Failed to discover active POS devices",
                exception=e,
                context={"action": "discover_devices"},
            )

    async def _start_agent_for_device(self, device_id: str, device_name: str) -> None:
        """Start an agent for a specific device."""
        if device_id not in self.agents:
            # Fix: Pass device_type explicitly, don't use name as type
            agent = DeviceAgentSimulator(device_id, device_type="pos_terminal")
            self.agents[device_id] = agent
            await agent.start()
            logger.info(f"Started agent for device {device_id} ({device_name})")

    async def _device_monitor_loop(self) -> None:
        """Monitor for new devices and start agents for them."""
        while self.is_running:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                await self._discover_and_start_agents()
            except Exception as e:
                logger.error(f"Device monitor loop error: {e}")
                # Log error for AI training
                await log_error(
                    category="external_service",
                    severity="warning",
                    error_message="Device monitor loop encountered an error",
                    exception=e,
                    context={"action": "device_monitor_loop"},
                )
                await asyncio.sleep(5)

    async def send_push_notification(
        self, device_id: str, notification_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Send push notification to a specific agent."""
        agent = self.agents.get(device_id)
        if agent:
            return await agent.handle_push_notification(notification_data)
        else:
            logger.warning(f"No agent found for device {device_id}")
            return None

    async def get_agent_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of an agent."""
        agent = self.agents.get(device_id)
        if agent:
            return {
                "device_id": device_id,
                "state": agent.state,
                "config_version": agent.current_config_version,
                "last_health_check": agent.last_health_check,
                "uptime": "running" if agent.is_running else "stopped",
            }
        return None

    async def get_all_agents_status(self) -> List[Dict[str, Any]]:
        """Get status of all agents."""
        statuses = []
        for device_id in self.agents:
            status = await self.get_agent_status(device_id)
            if status:
                statuses.append(status)
        return statuses


# Global agent manager instance
_agent_manager: Optional[AgentManager] = None


async def get_agent_manager() -> AgentManager:
    """Get agent manager singleton."""
    global _agent_manager
    if _agent_manager is None:
        _agent_manager = AgentManager()
        await _agent_manager.start()
    return _agent_manager


async def stop_agent_manager() -> None:
    """Stop agent manager."""
    global _agent_manager
    if _agent_manager is not None:
        await _agent_manager.stop()
        _agent_manager = None
