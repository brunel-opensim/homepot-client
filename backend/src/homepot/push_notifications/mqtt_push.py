"""MQTT Push Notification provider for IoT and OT devices.

This module implements MQTT-based push notifications for industrial and IoT devices:
- IoT sensors (temperature, motion, humidity, etc.)
- Industrial controllers (PLCs, SCADA systems)
- Edge gateways
- Custom embedded devices

MQTT provides:
- Lightweight messaging (perfect for resource-constrained devices)
- Quality of Service (QoS) levels (0, 1, 2)
- Retained messages for persistent state
- Last Will and Testament (LWT) for device disconnection
- Topic-based pub/sub architecture
- TLS/SSL support for secure communication
- Authentication and authorization

Configuration required:
- broker_host: MQTT broker hostname or IP
- broker_port: MQTT broker port (default: 1883, TLS: 8883)
- username: MQTT authentication username (optional)
- password: MQTT authentication password (optional)
- use_tls: Enable TLS/SSL encryption (recommended: True)
- client_id: Unique client identifier (optional, auto-generated)
- qos: Quality of Service level (0, 1, or 2, default: 1)
- retain: Retain messages on broker (default: False)

Example usage:
    config = {
        "broker_host": "mqtt.example.com",
        "broker_port": 8883,
        "username": "homepot",
        "password": "secure_password",
        "use_tls": True,
        "qos": 1,
        "retain": False
    }

    mqtt_provider = MQTTPushProvider(config)
    await mqtt_provider.initialize()

    # Device token is the MQTT topic
    device_token = "devices/sensor-001/notifications"

    result = await mqtt_provider.send_notification(
        device_token=device_token,
        payload=PushNotificationPayload(
            title="Temperature Alert",
            body="Temperature exceeded threshold: 85°C",
            data={"sensor_id": "sensor-001", "value": 85, "threshold": 80}
        )
    )
"""

import asyncio
import json
import logging
import ssl
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import paho.mqtt.client as mqtt
    from paho.mqtt.client import Client

    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    mqtt = None  # type: ignore
    Client = None  # type: ignore

from .base import (
    PushNotificationPayload,
    PushNotificationProvider,
    PushNotificationResult,
)

logger = logging.getLogger(__name__)


class MQTTPushProvider(PushNotificationProvider):
    """MQTT-based push notification provider for IoT/OT devices.

    This provider sends notifications to IoT devices and industrial controllers
    via MQTT protocol. Perfect for resource-constrained devices, sensors,
    PLCs, and embedded systems.

    Features:
    - QoS levels 0, 1, and 2
    - Retained messages
    - Last Will and Testament
    - TLS/SSL encryption
    - Username/password authentication
    - Topic-based routing
    - Connection pooling
    """

    # Class constants
    DEFAULT_PORT = 1883
    DEFAULT_TLS_PORT = 8883
    DEFAULT_QOS = 1
    DEFAULT_KEEPALIVE = 60
    DEFAULT_TIMEOUT = 30
    MAX_PAYLOAD_SIZE = 256 * 1024  # 256KB (MQTT default)

    def __init__(self, config: Dict[str, Any]):
        """Initialize the MQTT Push provider.

        Args:
            config: Configuration dictionary containing:
                - broker_host: MQTT broker hostname or IP (required)
                - broker_port: MQTT broker port (optional, default: 1883/8883)
                - username: Authentication username (optional)
                - password: Authentication password (optional)
                - use_tls: Enable TLS/SSL (optional, default: False)
                - client_id: Client identifier (optional, auto-generated)
                - qos: Quality of Service (optional, default: 1)
                - retain: Retain messages (optional, default: False)
                - keepalive: Keep-alive interval (optional, default: 60)
                - timeout: Connection timeout (optional, default: 30)
        """
        super().__init__(config)
        self.platform_name = "mqtt_push"

        # Required configuration - validated below
        broker_host = config.get("broker_host")

        # Validate required configuration
        if not broker_host:
            raise ValueError("MQTT Push requires 'broker_host'")

        # Assign validated values
        self.broker_host: str = broker_host

        # Optional configuration
        self.use_tls = config.get("use_tls", False)
        self.broker_port = config.get(
            "broker_port",
            self.DEFAULT_TLS_PORT if self.use_tls else self.DEFAULT_PORT,
        )
        self.username = config.get("username")
        self.password = config.get("password")
        self.client_id = config.get("client_id", f"homepot-{uuid.uuid4().hex[:8]}")
        self.qos = config.get("qos", self.DEFAULT_QOS)
        self.retain = config.get("retain", False)
        self.keepalive = config.get("keepalive", self.DEFAULT_KEEPALIVE)
        self.timeout = config.get("timeout", self.DEFAULT_TIMEOUT)

        # Validate QoS level
        if self.qos not in [0, 1, 2]:
            raise ValueError(f"Invalid QoS level: {self.qos}. Must be 0, 1, or 2")

        # Check if paho-mqtt is available
        if not MQTT_AVAILABLE:
            logger.warning(
                "paho-mqtt library not installed. MQTT functionality limited. "
                "Install with: pip install paho-mqtt"
            )

        # MQTT client (initialized in initialize())
        self.client: Optional[Any] = None  # Type is paho.mqtt.client.Client
        self._connected = False
        self._connection_lock = asyncio.Lock()

        # Statistics tracking
        self.stats: Dict[str, Any] = {
            "total_sent": 0,
            "total_success": 0,
            "total_failed": 0,
            "last_sent": None,
            "connection_count": 0,
        }

        self.logger.info(
            f"Initialized {self.platform_name} provider "
            f"(broker: {self.broker_host}:{self.broker_port}, "
            f"client_id: {self.client_id})"
        )

    async def initialize(self) -> bool:
        """Initialize the MQTT Push provider.

        Returns:
            True if initialization successful, False otherwise

        Raises:
            RuntimeError: If paho-mqtt library is not installed
        """
        try:
            if not MQTT_AVAILABLE:
                raise RuntimeError(
                    "paho-mqtt library not installed. "
                    "Install with: pip install paho-mqtt"
                )

            # Create MQTT client
            self.client = mqtt.Client(client_id=self.client_id, protocol=mqtt.MQTTv5)

            # Set authentication if provided
            if self.username and self.password:
                self.client.username_pw_set(self.username, self.password)

            # Configure TLS if enabled
            if self.use_tls:
                self.client.tls_set(
                    cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLSv1_2
                )

            # Set callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_publish = self._on_publish

            # Test connection
            await self._connect()

            self._initialized = True
            self.logger.info(f"Successfully initialized {self.platform_name} provider")
            return True

        except RuntimeError:
            # Re-raise library availability errors
            raise
        except Exception as e:
            self.logger.error(f"Failed to initialize {self.platform_name}: {e}")
            self._initialized = False
            return False

    async def _connect(self) -> bool:
        """Establish connection to MQTT broker.

        Returns:
            True if connection successful, False otherwise
        """
        async with self._connection_lock:
            if self._connected:
                return True

            if not self.client:
                raise RuntimeError(
                    "MQTT client not initialized. Call initialize() first."
                )

            try:
                # Connect to broker
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self.client.connect(  # type: ignore
                        self.broker_host,
                        self.broker_port,
                        self.keepalive,
                    ),
                )

                # Start network loop in background
                self.client.loop_start()

                # Wait for connection (with timeout)
                timeout = self.timeout
                while not self._connected and timeout > 0:
                    await asyncio.sleep(0.1)
                    timeout -= 0.1

                if not self._connected:
                    raise TimeoutError("Connection timeout")

                self.stats["connection_count"] += 1
                return True

            except Exception as e:
                self.logger.error(f"Failed to connect to MQTT broker: {e}")
                return False

    def _on_connect(
        self, client: Any, userdata: Any, flags: Any, rc: int, properties: Any = None
    ) -> None:
        """Handle connection establishment callback."""
        if rc == 0:
            self._connected = True
            self.logger.info(f"Connected to MQTT broker: {self.broker_host}")
        else:
            self._connected = False
            self.logger.error(f"MQTT connection failed with code: {rc}")

    def _on_disconnect(
        self, client: Any, userdata: Any, rc: int, properties: Any = None
    ) -> None:
        """Handle connection loss callback."""
        self._connected = False
        if rc != 0:
            self.logger.warning(f"Unexpected disconnection from MQTT broker: {rc}")

    def _on_publish(self, client: Any, userdata: Any, mid: int) -> None:
        """Handle message publication callback."""
        self.logger.debug(f"Message published with mid: {mid}")

    async def send_notification(
        self, device_token: str, payload: PushNotificationPayload
    ) -> PushNotificationResult:
        """Send push notification via MQTT.

        Args:
            device_token: MQTT topic (e.g., "devices/sensor-001/notifications")
            payload: Notification payload

        Returns:
            Result of the notification attempt
        """
        try:
            # Validate token (topic)
            if not self.validate_device_token(device_token):
                return PushNotificationResult(
                    success=False,
                    message="Invalid MQTT topic format",
                    platform=self.platform_name,
                    device_token=(
                        device_token[:50] + "..." if device_token else "invalid"
                    ),
                    error_code="INVALID_TOPIC",
                )

            # Build MQTT message
            mqtt_message = self._build_mqtt_message(payload)

            # Ensure connection
            if not self._connected:
                await self._connect()

            if not self._connected:
                return PushNotificationResult(
                    success=False,
                    message="Not connected to MQTT broker",
                    platform=self.platform_name,
                    device_token=device_token[:50] + "...",
                    error_code="NOT_CONNECTED",
                )

            if not self.client:
                return PushNotificationResult(
                    success=False,
                    message="MQTT client not initialized",
                    platform=self.platform_name,
                    device_token=device_token[:50] + "...",
                    error_code="CLIENT_NOT_INITIALIZED",
                )

            # Publish message
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.client.publish(  # type: ignore
                    topic=device_token,
                    payload=json.dumps(mqtt_message),
                    qos=self.qos,
                    retain=self.retain,
                ),
            )

            # Check result
            if result.rc == mqtt.MQTT_ERR_SUCCESS:  # type: ignore
                self.stats["total_sent"] += 1
                self.stats["total_success"] += 1
                self.stats["last_sent"] = datetime.utcnow().isoformat()

                return PushNotificationResult(
                    success=True,
                    message="MQTT notification sent successfully",
                    platform=self.platform_name,
                    device_token=device_token[:50] + "...",
                    message_id=mqtt_message.get("message_id"),
                )
            else:
                self.stats["total_sent"] += 1
                self.stats["total_failed"] += 1

                return PushNotificationResult(
                    success=False,
                    message=f"MQTT publish failed: {result.rc}",
                    platform=self.platform_name,
                    device_token=device_token[:50] + "...",
                    error_code=f"MQTT_ERROR_{result.rc}",
                )

        except Exception as e:
            self.stats["total_failed"] += 1
            self.logger.error(f"Failed to send MQTT notification: {e}")

            return PushNotificationResult(
                success=False,
                message=f"Exception: {str(e)}",
                platform=self.platform_name,
                device_token=device_token[:50] + "..." if device_token else "unknown",
                error_code="EXCEPTION",
            )

    def _build_mqtt_message(self, payload: PushNotificationPayload) -> Dict[str, Any]:
        """Build MQTT message from notification payload.

        Args:
            payload: Notification payload

        Returns:
            MQTT message dictionary
        """
        message: Dict[str, Any] = {
            "title": payload.title,
            "body": payload.body,
            "timestamp": datetime.utcnow().isoformat(),
            "platform": self.platform_name,
            "message_id": str(uuid.uuid4()),
        }

        # Add optional fields
        if payload.data:
            message["data"] = payload.data

        if payload.priority:
            message["priority"] = payload.priority.value

        # Check platform_data for badge and sound (platform-specific)
        if payload.platform_data:
            if "badge" in payload.platform_data:
                message["badge"] = payload.platform_data["badge"]
            if "sound" in payload.platform_data:
                message["sound"] = payload.platform_data["sound"]

        if payload.ttl_seconds:
            message["ttl"] = payload.ttl_seconds

        return message

    async def send_bulk_notifications(
        self, notifications: List[tuple[str, PushNotificationPayload]]
    ) -> List[PushNotificationResult]:
        """Send push notifications to multiple IoT devices.

        Args:
            notifications: List of (device_token/topic, payload) tuples

        Returns:
            List of results for each notification attempt
        """
        # Send notifications concurrently
        tasks = [
            self.send_notification(device_token, payload)
            for device_token, payload in notifications
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        processed_results: List[PushNotificationResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                device_token = notifications[i][0]
                processed_results.append(
                    PushNotificationResult(
                        success=False,
                        message=f"Exception: {str(result)}",
                        platform=self.platform_name,
                        device_token=device_token[:50] + "...",
                        error_code="EXCEPTION",
                    )
                )
            else:
                processed_results.append(result)  # type: ignore[arg-type]

        return processed_results

    async def send_topic_notification(
        self, topic: str, payload: PushNotificationPayload
    ) -> PushNotificationResult:
        """Send notification to an MQTT topic.

        This is the native MQTT way of broadcasting to multiple subscribers.

        Args:
            topic: MQTT topic (e.g., "devices/sensors/all")
            payload: Notification payload

        Returns:
            Result of the notification attempt
        """
        # In MQTT, topic notifications are the same as device notifications
        # The topic itself IS the device_token
        return await self.send_notification(topic, payload)

    def validate_device_token(self, token: str) -> bool:
        """Validate MQTT topic format.

        Args:
            token: MQTT topic to validate

        Returns:
            True if topic is valid
        """
        if not token or not isinstance(token, str):
            return False

        # Basic MQTT topic validation
        # Topics should not start or end with /
        # Topics should not contain # or + (wildcards) for publishing
        if token.startswith("/") or token.endswith("/"):
            return False

        if "#" in token or "+" in token:
            return False

        # Topic should have reasonable length
        if len(token) > 256:
            return False

        return True

    async def get_platform_info(self) -> Dict[str, Any]:
        """Get MQTT platform information.

        Returns:
            Dictionary with platform details
        """
        return {
            "platform": self.platform_name,
            "broker_host": self.broker_host,
            "broker_port": self.broker_port,
            "broker": f"{self.broker_host}:{self.broker_port}",
            "client_id": self.client_id,
            "mqtt_available": MQTT_AVAILABLE,
            "connected": self._connected,
            "tls_enabled": self.use_tls,
            "qos": self.qos,
            "qos_level": self.qos,
            "retain_enabled": self.retain,
            "max_payload_size": self.MAX_PAYLOAD_SIZE,
            "statistics": self.stats,
        }

    async def cleanup(self) -> None:
        """Clean up MQTT resources."""
        if self.client and self._connected:
            try:
                self.client.loop_stop()
                self.client.disconnect()
                self._connected = False
                self.logger.info("MQTT connection closed")
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")

    def __del__(self) -> None:
        """Destructor to ensure cleanup."""
        if hasattr(self, "client") and self.client:
            try:
                if self._connected:
                    self.client.loop_stop()
                    self.client.disconnect()
            except Exception:  # nosec B110
                pass  # Ignore errors during cleanup
