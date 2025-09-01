"""POS Agent Simulation for HOMEPOT Client.

This module implements mock POS agents that simulate real-world device behavior:
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
import random  # nosec - Used for POS device simulation, not cryptographic purposes
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum

from homepot_client.database import get_database_service
from homepot_client.models import DeviceStatus

logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    """Agent states for simulation."""

    IDLE = "idle"
    DOWNLOADING = "downloading"
    UPDATING = "updating"
    RESTARTING = "restarting"
    HEALTH_CHECK = "health_check"
    ERROR = "error"


class POSAgentSimulator:
    """Simulates a POS agent that responds to push notifications and runs health checks.

    This simulates realistic POS terminal behavior:
    1. Receives push notification from orchestrator
    2. Downloads new configuration from provided URL
    3. Validates and applies configuration
    4. Restarts POS application
    5. Runs health check
    6. Sends ACK back to HOMEPOT
    """

    def __init__(self, device_id: str, device_type: str = "pos_terminal"):
        """Initialize a POS agent with device configuration.

        Args:
            device_id: Unique identifier for the POS device
            device_type: Type of device, defaults to "pos_terminal"
        """
        self.device_id = device_id
        self.device_type = device_type
        self.state = AgentState.IDLE
        self.current_config_version = "1.0.0"
        self.last_health_check = None
        self.error_rate = 0.1  # 10% chance of errors for realistic simulation
        self.response_time_ms = random.randint(100, 500)  # nosec - simulation only
        self.is_running = False

        # Simulate device characteristics
        self.device_info = {
            "model": "POS-Terminal-X1",
            "firmware": "2.4.1",
            "os": "Linux ARM",
            "memory_mb": 2048,
            "storage_gb": 16,
            "uptime_hours": random.randint(1, 720),  # nosec - simulation only
        }

        logger.info(f"POS Agent {device_id} ({device_type}) initialized")

    async def start(self):
        """Start the agent simulator."""
        self.is_running = True
        logger.info(f"Agent {self.device_id} started")

        # Start health check loop
        asyncio.create_task(self._health_check_loop())

    async def stop(self):
        """Stop the agent simulator."""
        self.is_running = False
        logger.info(f"Agent {self.device_id} stopped")

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
            config_url = notification_data.get("data", {}).get("config_url", "")
            config_version = notification_data.get("data", {}).get("config_version", "")

            if action == "update_pos_payment_config":
                return await self._handle_config_update(config_url, config_version)
            elif action == "restart_pos_app":
                return await self._handle_restart()
            elif action == "health_check":
                return await self._handle_health_check()
            else:
                return {
                    "status": "error",
                    "message": f"Unknown action: {action}",
                    "device_id": self.device_id,
                    "timestamp": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            logger.error(
                f"Agent {self.device_id} error handling push notification: {e}"
            )
            return {
                "status": "error",
                "message": str(e),
                "device_id": self.device_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _handle_config_update(
        self, config_url: str, config_version: str
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

            # Simulate restart failures (2% chance)
            if random.random() < 0.02:
                raise Exception(
                    "POS application failed to restart: Service dependency error"
                )

            # Step 5: Run health check
            self.state = AgentState.HEALTH_CHECK
            health_result = await self._run_health_check()

            # Update current config version
            self.current_config_version = config_version
            self.state = AgentState.IDLE

            # Step 6: Send success ACK
            return {
                "status": "success",
                "message": "Configuration updated successfully",
                "device_id": self.device_id,
                "config_version": config_version,
                "health_check": health_result,
                "timestamp": datetime.utcnow().isoformat(),
                "processing_time_ms": random.randint(2000, 6000),
            }

        except Exception as e:
            self.state = AgentState.ERROR
            await asyncio.sleep(1.0)  # Error recovery time
            self.state = AgentState.IDLE

            return {
                "status": "error",
                "message": str(e),
                "device_id": self.device_id,
                "config_version": self.current_config_version,  # Keep old version
                "timestamp": datetime.utcnow().isoformat(),
            }

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
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            self.state = AgentState.ERROR
            await asyncio.sleep(2.0)
            self.state = AgentState.IDLE

            return {
                "status": "error",
                "message": str(e),
                "device_id": self.device_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _handle_health_check(self) -> Dict[str, Any]:
        """Handle explicit health check request."""
        health_result = await self._run_health_check()

        return {
            "status": "success",
            "message": "Health check completed",
            "device_id": self.device_id,
            "health_check": health_result,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _run_health_check(self) -> Dict[str, Any]:
        """Run comprehensive health check."""
        self.state = AgentState.HEALTH_CHECK
        await asyncio.sleep(random.uniform(0.1, 0.5))

        # Simulate various health scenarios
        scenarios = [
            {"healthy": True, "weight": 0.85},  # 85% healthy
            {"healthy": False, "error": "Payment gateway timeout", "weight": 0.08},
            {"healthy": False, "error": "Database connection failed", "weight": 0.04},
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

        # Generate realistic health data
        health_data = {
            "status": "healthy" if is_healthy else "unhealthy",
            "config_version": self.current_config_version,
            "last_restart": (
                datetime.utcnow() - timedelta(hours=random.randint(1, 48))
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
                "cpu_usage_percent": random.randint(10, 80),
                "memory_usage_percent": random.randint(30, 70),
                "disk_usage_percent": random.randint(20, 60),
                "transactions_today": random.randint(50, 300),
                "uptime_seconds": random.randint(3600, 86400 * 7),
            },
        }

        if not is_healthy:
            health_data["error"] = selected_scenario["error"]
            health_data["services"]["pos_app"] = "error"

        self.last_health_check = health_data

        # Update device status in database
        try:
            db_service = await get_database_service()
            new_status = DeviceStatus.ONLINE if is_healthy else DeviceStatus.ERROR
            await db_service.update_device_status(self.device_id, new_status)

            # Create health check record
            await db_service.create_health_check(
                device_name=self.device_id,  # Use device_name for lookup
                is_healthy=is_healthy,
                response_time_ms=self.response_time_ms,
                status_code=200 if is_healthy else 500,
                endpoint="/health",
                response_data=health_data,
            )

        except Exception as e:
            logger.error(f"Failed to update device status for {self.device_id}: {e}")

        return health_data

    async def _health_check_loop(self):
        """Periodic health check loop (every 30 seconds)."""
        while self.is_running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                if self.state == AgentState.IDLE:
                    await self._run_health_check()
            except Exception as e:
                logger.error(f"Health check loop error for {self.device_id}: {e}")
                await asyncio.sleep(5)  # Short retry delay


class AgentManager:
    """Manages all POS agent simulators."""

    def __init__(self):
        """Initialize the agent manager with empty agent registry."""
        self.agents: Dict[str, POSAgentSimulator] = {}
        self.is_running = False

    async def start(self):
        """Start the agent manager and discover existing devices."""
        self.is_running = True
        logger.info("Agent Manager started")

        # Discover and start agents for existing devices
        await self._discover_and_start_agents()

        # Start monitoring for new devices
        asyncio.create_task(self._device_monitor_loop())

    async def stop(self):
        """Stop all agents."""
        self.is_running = False
        logger.info("Stopping Agent Manager")

        # Stop all agents
        for agent in self.agents.values():
            await agent.stop()

        self.agents.clear()
        logger.info("Agent Manager stopped")

    async def _discover_and_start_agents(self):
        """Discover existing devices and start agents for them."""
        try:
            db_service = await get_database_service()

            # Get all active POS devices
            from sqlalchemy import select
            from homepot_client.models import Device, DeviceType

            async with db_service.get_session() as session:
                result = await session.execute(
                    select(Device).where(
                        Device.is_active.is_(True),
                        Device.device_type == DeviceType.POS_TERMINAL,
                    )
                )
                devices = result.scalars().all()

                for device in devices:
                    await self._start_agent_for_device(device.device_id, device.name)

        except Exception as e:
            logger.error(f"Failed to discover devices: {e}")

    async def _start_agent_for_device(self, device_id: str, device_name: str):
        """Start an agent for a specific device."""
        if device_id not in self.agents:
            agent = POSAgentSimulator(device_id, device_name)
            self.agents[device_id] = agent
            await agent.start()
            logger.info(f"Started agent for device {device_id}")

    async def _device_monitor_loop(self):
        """Monitor for new devices and start agents for them."""
        while self.is_running:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                await self._discover_and_start_agents()
            except Exception as e:
                logger.error(f"Device monitor loop error: {e}")
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


async def stop_agent_manager():
    """Stop agent manager."""
    global _agent_manager
    if _agent_manager is not None:
        await _agent_manager.stop()
        _agent_manager = None
