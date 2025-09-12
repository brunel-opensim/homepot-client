"""Simulation provider for testing push notifications without real services.

This provider simulates push notification delivery and is primarily used for:
- Testing and development
- Integration tests
- Fallback when no real providers are available
- Demo environments

The simulation provider mimics the behavior of real push notification services
but delivers notifications to the existing agent simulation system.
"""

import asyncio
import logging
import random
from typing import Any, Dict, List

from .base import (
    PushNotificationPayload,
    PushNotificationProvider,
    PushNotificationResult,
)

logger = logging.getLogger(__name__)


class SimulationProvider(PushNotificationProvider):
    """Simulation push notification provider for testing and development.

    This provider integrates with the existing HOMEPOT agent simulation
    system to provide realistic push notification behavior without requiring
    external services.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the simulation provider.

        Args:
            config: Configuration dictionary with simulation settings
        """
        super().__init__(config)
        self.platform_name = "simulation"

        # Simulation settings
        self.success_rate = config.get("success_rate", 0.95)  # 95% success
        self.delivery_delay_ms = config.get("delivery_delay_ms", (100, 500))
        self.error_scenarios = config.get("enable_error_scenarios", True)

        self.logger.info(
            f"Initialized simulation provider with {self.success_rate * 100}% success"
        )

    async def initialize(self) -> bool:
        """Initialize the simulation provider."""
        try:
            # Simulate initialization delay
            await asyncio.sleep(0.1)

            self._initialized = True
            self.logger.info("Simulation provider initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize simulation provider: {e}")
            return False

    async def send_notification(
        self, device_token: str, payload: PushNotificationPayload
    ) -> PushNotificationResult:
        """Send a push notification to a single device via agent simulation.

        Args:
            device_token: Device identifier (maps to agent device_id)
            payload: Notification payload

        Returns:
            Result of the simulated push notification
        """
        if not self._initialized:
            raise RuntimeError("Provider not initialized")

        # Simulate network delay
        delay_min, delay_max = self.delivery_delay_ms
        delay = random.uniform(delay_min, delay_max) / 1000.0  # nosec B311
        await asyncio.sleep(delay)

        # Simulate various error scenarios
        if self.error_scenarios and random.random() > self.success_rate:  # nosec B311
            return self._simulate_error(device_token, payload)

        # Try to deliver to agent simulation
        try:
            # Get the agent manager to deliver notification
            from homepot_client.agents import get_agent_manager

            agent_manager = await get_agent_manager()

            # Convert our payload to agent notification format
            agent_notification = self._convert_to_agent_format(payload)

            # Send to agent
            response = await agent_manager.send_push_notification(
                device_token, agent_notification
            )

            if response and response.get("status") == "success":
                return PushNotificationResult(
                    success=True,
                    message="Notification delivered to agent simulation",
                    platform=self.platform_name,
                    device_token=device_token,
                    message_id=f"sim-{random.randint(100000, 999999)}",  # nosec B311
                )
            else:
                error_msg = (
                    response.get("message", "Agent not found")
                    if response
                    else "No agent response"
                )
                return PushNotificationResult(
                    success=False,
                    message=f"Agent delivery failed: {error_msg}",
                    platform=self.platform_name,
                    device_token=device_token,
                    error_code="AGENT_ERROR",
                )

        except Exception as e:
            self.logger.error(f"Simulation delivery failed for {device_token}: {e}")
            return PushNotificationResult(
                success=False,
                message=f"Simulation error: {str(e)}",
                platform=self.platform_name,
                device_token=device_token,
                error_code="SIMULATION_ERROR",
            )

    async def send_bulk_notifications(
        self, notifications: List[tuple[str, PushNotificationPayload]]
    ) -> List[PushNotificationResult]:
        """Send push notifications to multiple devices.

        Args:
            notifications: List of (device_token, payload) tuples

        Returns:
            List of results for each notification
        """
        results = []

        # Process notifications concurrently for better performance
        tasks = [
            self.send_notification(device_token, payload)
            for device_token, payload in notifications
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to failed results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                device_token = notifications[i][0]
                processed_results.append(
                    PushNotificationResult(
                        success=False,
                        message=f"Bulk notification error: {str(result)}",
                        platform=self.platform_name,
                        device_token=device_token,
                        error_code="BULK_ERROR",
                    )
                )
            else:
                processed_results.append(result)

        return processed_results

    async def send_topic_notification(
        self, topic: str, payload: PushNotificationPayload
    ) -> PushNotificationResult:
        """Send a push notification to a topic (simulated).

        Args:
            topic: Topic name (e.g., 'site-123' or 'pos-terminals')
            payload: Notification payload

        Returns:
            Result of the topic notification
        """
        # Simulate topic delivery by finding all devices for the topic
        try:
            from sqlalchemy import select

            from homepot_client.database import get_database_service
            from homepot_client.models import Device, DeviceType

            db_service = await get_database_service()

            # Map topic to device query
            devices = []
            async with db_service.get_session() as session:
                if topic.startswith("site-"):
                    # Topic is a site - get all devices for that site
                    site_id = topic.replace("site-", "")
                    result = await session.execute(
                        select(Device).where(
                            Device.site_id == int(site_id), Device.is_active.is_(True)
                        )
                    )
                    devices = result.scalars().all()
                elif topic == "pos-terminals":
                    # Get all POS terminals
                    result = await session.execute(
                        select(Device).where(
                            Device.device_type == DeviceType.POS_TERMINAL,
                            Device.is_active.is_(True),
                        )
                    )
                    devices = result.scalars().all()

            if not devices:
                return PushNotificationResult(
                    success=False,
                    message=f"No devices found for topic: {topic}",
                    platform=self.platform_name,
                    error_code="NO_DEVICES",
                )

            # Send to all devices in the topic
            notifications = [(device.device_id, payload) for device in devices]
            results = await self.send_bulk_notifications(notifications)

            # Summarize results
            successful = sum(1 for r in results if r.success)
            total = len(results)

            return PushNotificationResult(
                success=successful > 0,
                message=f"Topic notification sent to {successful}/{total} devices",
                platform=self.platform_name,
                message_id=f"topic-sim-{random.randint(100000, 999999)}",  # nosec B311
            )

        except Exception as e:
            return PushNotificationResult(
                success=False,
                message=f"Topic notification failed: {str(e)}",
                platform=self.platform_name,
                error_code="TOPIC_ERROR",
            )

    def validate_device_token(self, token: str) -> bool:
        """Validate a device token (simulation accepts any non-empty string).

        Args:
            token: Device token to validate

        Returns:
            True if token is valid format
        """
        return isinstance(token, str) and len(token.strip()) > 0

    async def get_platform_info(self) -> Dict[str, Any]:
        """Get simulation platform information.

        Returns:
            Platform status and configuration
        """
        try:
            from homepot_client.agents import get_agent_manager

            agent_manager = await get_agent_manager()
            agents_status = await agent_manager.get_all_agents_status()

            return {
                "platform": "simulation",
                "service_status": "operational",
                "active_agents": len(agents_status),
                "success_rate": self.success_rate,
                "delivery_delay_ms": self.delivery_delay_ms,
                "error_scenarios_enabled": self.error_scenarios,
            }

        except Exception as e:
            return {
                "platform": "simulation",
                "service_status": "error",
                "error": str(e),
            }

    def _convert_to_agent_format(
        self, payload: PushNotificationPayload
    ) -> Dict[str, Any]:
        """Convert our payload format to agent notification format.

        Args:
            payload: Standard push notification payload

        Returns:
            Dictionary in agent notification format
        """
        # Map our payload to agent notification format
        notification = {
            "action": "health_check",  # Default action that's always supported
            "data": {
                "title": payload.title,
                "body": payload.body,
                "priority": payload.priority.value,
                **payload.data,  # Include all custom data
            },
        }

        # Add platform-specific data if present
        if payload.platform_data:
            notification["data"].update(payload.platform_data)

        # Handle specific action types based on data content
        if "config_url" in payload.data:
            notification["action"] = "update_pos_payment_config"
            notification["data"]["config_url"] = payload.data["config_url"]
            notification["data"]["config_version"] = payload.data.get(
                "config_version", "1.0.0"
            )
        elif "restart" in payload.data and payload.data["restart"]:
            notification["action"] = "restart_pos_app"
        elif "action" in payload.data:
            # Allow direct action specification in payload data
            valid_actions = [
                "update_pos_payment_config",
                "restart_pos_app",
                "health_check",
            ]
            if payload.data["action"] in valid_actions:
                notification["action"] = payload.data["action"]

        return notification

    def _simulate_error(
        self, device_token: str, payload: PushNotificationPayload
    ) -> PushNotificationResult:
        """Simulate various error scenarios.

        Args:
            device_token: Device token
            payload: Notification payload

        Returns:
            Failed result with simulated error
        """
        # Different error scenarios with weights
        errors = [
            ("DEVICE_OFFLINE", "Device is currently offline", 0.4),
            ("INVALID_TOKEN", "Invalid device token", 0.2),
            ("NETWORK_ERROR", "Network connectivity issues", 0.2),
            ("SERVICE_UNAVAILABLE", "Push service temporarily unavailable", 0.1),
            ("QUOTA_EXCEEDED", "Daily quota exceeded", 0.05),
            ("PAYLOAD_TOO_LARGE", "Notification payload too large", 0.05),
        ]

        # Select error based on weights
        rand = random.random()  # nosec B311
        cumulative = 0
        selected_error = errors[0]

        for error_code, message, weight in errors:
            cumulative += weight
            if rand <= cumulative:
                selected_error = (error_code, message, weight)
                break

        error_code, message, _ = selected_error

        return PushNotificationResult(
            success=False,
            message=message,
            platform=self.platform_name,
            device_token=device_token,
            error_code=error_code,
        )
