"""Tests for MQTT Push notification provider."""

from unittest.mock import MagicMock, patch

import pytest

from homepot_client.push_notifications.base import (
    PushNotificationPayload,
    PushPriority,
)
from homepot_client.push_notifications.mqtt_push import MQTTPushProvider


@pytest.fixture
def mqtt_config():
    """Provide MQTT configuration for testing."""
    return {
        "broker_host": "mqtt.example.com",
        "broker_port": 1883,
        "username": "test_user",
        "password": "test_password",
        "use_tls": False,
        "client_id": "test_client",
        "qos": 1,
        "retain": False,
        "keepalive": 60,
        "timeout": 30,
    }


@pytest.fixture
def mqtt_config_tls():
    """Provide MQTT configuration with TLS for testing."""
    return {
        "broker_host": "mqtt.example.com",
        "broker_port": 8883,
        "username": "test_user",
        "password": "test_password",
        "use_tls": True,
        "qos": 2,
    }


@pytest.fixture
def sample_payload():
    """Provide a sample notification payload."""
    return PushNotificationPayload(
        title="Temperature Alert",
        body="Temperature exceeded threshold: 85°C",
        data={"sensor_id": "sensor-001", "value": 85, "threshold": 80},
        priority=PushPriority.HIGH,
    )


def mock_mqtt_connect(provider):
    """Mock MQTT connection for faster tests."""

    async def _mock_connect():
        provider._connected = True
        return True

    provider._connect = _mock_connect


class TestMQTTPushProvider:
    """Test suite for MQTT Push notification provider."""

    def test_initialization_with_valid_config(self, mqtt_config):
        """Test provider initialization with valid configuration."""
        provider = MQTTPushProvider(mqtt_config)
        assert provider.platform_name == "mqtt_push"
        assert provider.broker_host == "mqtt.example.com"
        assert provider.broker_port == 1883
        assert provider.username == "test_user"
        assert provider.password == "test_password"
        assert provider.use_tls is False
        assert provider.qos == 1
        assert provider.retain is False

    def test_initialization_without_broker_host(self):
        """Test that initialization fails without broker_host."""
        with pytest.raises(ValueError, match="broker_host"):
            MQTTPushProvider({})

    def test_initialization_with_invalid_qos(self, mqtt_config):
        """Test that initialization fails with invalid QoS level."""
        config = mqtt_config.copy()
        config["qos"] = 3  # Invalid QoS (must be 0, 1, or 2)

        with pytest.raises(ValueError, match="Invalid QoS level"):
            MQTTPushProvider(config)

    def test_initialization_with_tls(self, mqtt_config_tls):
        """Test provider initialization with TLS enabled."""
        provider = MQTTPushProvider(mqtt_config_tls)
        assert provider.use_tls is True
        assert provider.broker_port == 8883
        assert provider.qos == 2

    def test_default_values(self):
        """Test that default values are set correctly."""
        provider = MQTTPushProvider({"broker_host": "mqtt.example.com"})
        assert provider.broker_port == 1883  # Default non-TLS port
        assert provider.qos == 1  # Default QoS
        assert provider.retain is False
        assert provider.use_tls is False
        assert provider.client_id.startswith("homepot-")

    def test_default_port_with_tls(self):
        """Test that default port is 8883 when TLS is enabled."""
        provider = MQTTPushProvider(
            {"broker_host": "mqtt.example.com", "use_tls": True}
        )
        assert provider.broker_port == 8883  # Default TLS port

    @pytest.mark.asyncio
    @patch("homepot_client.push_notifications.mqtt_push.MQTT_AVAILABLE", True)
    @patch("homepot_client.push_notifications.mqtt_push.mqtt")
    async def test_provider_initialization(self, mock_mqtt, mqtt_config):
        """Test successful provider initialization."""
        # Mock MQTT client
        mock_client = MagicMock()
        mock_mqtt.Client.return_value = mock_client

        provider = MQTTPushProvider(mqtt_config)

        # Mock the _connect method to avoid actual broker connection
        async def mock_connect():
            provider._connected = True
            return True

        provider._connect = mock_connect

        mock_mqtt_connect(provider)
        await provider.initialize()

        # Verify client was created
        mock_mqtt.Client.assert_called_once()

        # Verify authentication was set
        mock_client.username_pw_set.assert_called_once_with(
            "test_user", "test_password"
        )

        # Verify callbacks were registered
        assert mock_client.on_connect is not None
        assert mock_client.on_disconnect is not None
        assert mock_client.on_publish is not None

    @pytest.mark.asyncio
    @patch("homepot_client.push_notifications.mqtt_push.MQTT_AVAILABLE", True)
    @patch("homepot_client.push_notifications.mqtt_push.mqtt")
    async def test_provider_initialization_with_tls(self, mock_mqtt, mqtt_config_tls):
        """Test provider initialization with TLS/SSL."""
        mock_client = MagicMock()
        mock_mqtt.Client.return_value = mock_client
        mock_mqtt.ssl = MagicMock()
        mock_mqtt.ssl.CERT_REQUIRED = 1

        provider = MQTTPushProvider(mqtt_config_tls)

        # Mock the _connect method to avoid actual broker connection
        async def mock_connect():
            provider._connected = True
            return True

        provider._connect = mock_connect

        mock_mqtt_connect(provider)
        await provider.initialize()

        # Verify TLS was configured
        mock_client.tls_set.assert_called_once()

    @pytest.mark.asyncio
    @patch("homepot_client.push_notifications.mqtt_push.MQTT_AVAILABLE", False)
    async def test_initialization_without_mqtt_library(self, mqtt_config):
        """Test initialization when paho-mqtt is not installed."""
        provider = MQTTPushProvider(mqtt_config)

        # Should raise error during initialize(), not __init__()
        # Don't mock connection since we're testing library availability
        with pytest.raises(RuntimeError, match="paho-mqtt library"):
            await provider.initialize()

    def test_validate_device_token_valid(self, mqtt_config):
        """Test validation of valid MQTT topics."""
        provider = MQTTPushProvider(mqtt_config)

        # Valid topics
        assert (
            provider.validate_device_token("devices/sensor-001/notifications") is True
        )
        assert provider.validate_device_token("home/living-room/temperature") is True
        assert provider.validate_device_token("factory/plc-01/alerts") is True

    def test_validate_device_token_invalid(self, mqtt_config):
        """Test validation of invalid MQTT topics."""
        provider = MQTTPushProvider(mqtt_config)

        # Invalid topics
        assert provider.validate_device_token("") is False
        assert provider.validate_device_token(None) is False  # type: ignore
        assert (
            provider.validate_device_token("/devices/sensor") is False
        )  # Starts with /
        assert provider.validate_device_token("devices/sensor/") is False  # Ends with /
        assert provider.validate_device_token("devices/#") is False  # Wildcard
        assert provider.validate_device_token("devices/+/alerts") is False  # Wildcard
        assert provider.validate_device_token("a" * 300) is False  # Too long

    @pytest.mark.asyncio
    @patch("homepot_client.push_notifications.mqtt_push.MQTT_AVAILABLE", True)
    @patch("homepot_client.push_notifications.mqtt_push.mqtt")
    async def test_send_notification_success(
        self, mock_mqtt, mqtt_config, sample_payload
    ):
        """Test successful notification sending."""
        # Mock MQTT client
        mock_client = MagicMock()
        mock_publish_result = MagicMock()
        mock_publish_result.rc = 0  # MQTT_ERR_SUCCESS
        mock_client.publish.return_value = mock_publish_result
        mock_mqtt.Client.return_value = mock_client
        mock_mqtt.MQTT_ERR_SUCCESS = 0

        provider = MQTTPushProvider(mqtt_config)
        mock_mqtt_connect(provider)
        mock_mqtt_connect(provider)
        await provider.initialize()

        # Simulate connection
        provider._connected = True

        # Send notification
        result = await provider.send_notification(
            device_token="devices/sensor-001/notifications",
            payload=sample_payload,
        )

        assert result.success is True
        assert result.platform == "mqtt_push"
        assert "successfully" in result.message.lower()
        assert provider.stats["total_sent"] == 1
        assert provider.stats["total_success"] == 1
        assert provider.stats["total_failed"] == 0

    @pytest.mark.asyncio
    @patch("homepot_client.push_notifications.mqtt_push.MQTT_AVAILABLE", True)
    @patch("homepot_client.push_notifications.mqtt_push.mqtt")
    async def test_send_notification_invalid_token(
        self, mock_mqtt, mqtt_config, sample_payload
    ):
        """Test notification sending with invalid token."""
        mock_client = MagicMock()
        mock_mqtt.Client.return_value = mock_client

        provider = MQTTPushProvider(mqtt_config)
        mock_mqtt_connect(provider)
        mock_mqtt_connect(provider)
        await provider.initialize()

        result = await provider.send_notification(
            device_token="/invalid/topic/",
            payload=sample_payload,
        )

        assert result.success is False
        assert "INVALID_TOPIC" in result.error_code

    @pytest.mark.asyncio
    @patch("homepot_client.push_notifications.mqtt_push.MQTT_AVAILABLE", True)
    @patch("homepot_client.push_notifications.mqtt_push.mqtt")
    async def test_send_notification_not_connected(
        self, mock_mqtt, mqtt_config, sample_payload
    ):
        """Test notification sending when not connected."""
        mock_client = MagicMock()
        mock_client.connect.side_effect = Exception("Connection failed")
        mock_mqtt.Client.return_value = mock_client

        provider = MQTTPushProvider(mqtt_config)
        # Don't mock connection - we want it to fail
        try:
            await provider.initialize()
        except Exception:
            pass  # Expected to fail

        # Ensure not connected
        provider._connected = False

        result = await provider.send_notification(
            device_token="devices/sensor-001/notifications",
            payload=sample_payload,
        )

        assert result.success is False
        assert result.error_code in ["NOT_CONNECTED", "EXCEPTION"]

    @pytest.mark.asyncio
    @patch("homepot_client.push_notifications.mqtt_push.MQTT_AVAILABLE", True)
    @patch("homepot_client.push_notifications.mqtt_push.mqtt")
    async def test_send_bulk_notifications(
        self, mock_mqtt, mqtt_config, sample_payload
    ):
        """Test sending bulk notifications."""
        mock_client = MagicMock()
        mock_publish_result = MagicMock()
        mock_publish_result.rc = 0
        mock_client.publish.return_value = mock_publish_result
        mock_mqtt.Client.return_value = mock_client
        mock_mqtt.MQTT_ERR_SUCCESS = 0

        provider = MQTTPushProvider(mqtt_config)
        mock_mqtt_connect(provider)
        await provider.initialize()
        provider._connected = True

        # Send to multiple devices
        notifications = [
            ("devices/sensor-001/notifications", sample_payload),
            ("devices/sensor-002/notifications", sample_payload),
            ("factory/plc-01/alerts", sample_payload),
        ]

        results = await provider.send_bulk_notifications(notifications)

        assert len(results) == 3
        assert all(r.success for r in results)
        assert provider.stats["total_sent"] == 3
        assert provider.stats["total_success"] == 3

    @pytest.mark.asyncio
    @patch("homepot_client.push_notifications.mqtt_push.MQTT_AVAILABLE", True)
    @patch("homepot_client.push_notifications.mqtt_push.mqtt")
    async def test_send_topic_notification(
        self, mock_mqtt, mqtt_config, sample_payload
    ):
        """Test topic-based notification (same as regular send in MQTT)."""
        mock_client = MagicMock()
        mock_publish_result = MagicMock()
        mock_publish_result.rc = 0
        mock_client.publish.return_value = mock_publish_result
        mock_mqtt.Client.return_value = mock_client
        mock_mqtt.MQTT_ERR_SUCCESS = 0

        provider = MQTTPushProvider(mqtt_config)
        mock_mqtt_connect(provider)
        await provider.initialize()
        provider._connected = True

        result = await provider.send_topic_notification(
            topic="factory/alerts/temperature",
            payload=sample_payload,
        )

        assert result.success is True

    @pytest.mark.asyncio
    @patch("homepot_client.push_notifications.mqtt_push.MQTT_AVAILABLE", True)
    @patch("homepot_client.push_notifications.mqtt_push.mqtt")
    async def test_build_mqtt_message(self, mock_mqtt, mqtt_config, sample_payload):
        """Test MQTT message building from payload."""
        mock_client = MagicMock()
        mock_mqtt.Client.return_value = mock_client

        provider = MQTTPushProvider(mqtt_config)

        # Mock the _connect method to avoid timeout
        async def mock_connect():
            provider._connected = True
            return True

        provider._connect = mock_connect

        mock_mqtt_connect(provider)
        await provider.initialize()

        message = provider._build_mqtt_message(sample_payload)

        assert message["title"] == "Temperature Alert"
        assert message["body"] == "Temperature exceeded threshold: 85°C"
        assert message["data"] == {
            "sensor_id": "sensor-001",
            "value": 85,
            "threshold": 80,
        }
        assert message["priority"] == "high"  # PushPriority.HIGH.value is lowercase
        assert message["platform"] == "mqtt_push"
        assert "timestamp" in message

    @pytest.mark.asyncio
    @patch("homepot_client.push_notifications.mqtt_push.MQTT_AVAILABLE", True)
    @patch("homepot_client.push_notifications.mqtt_push.mqtt")
    async def test_build_mqtt_message_with_platform_data(self, mock_mqtt, mqtt_config):
        """Test MQTT message with platform-specific data."""
        mock_client = MagicMock()
        mock_mqtt.Client.return_value = mock_client

        provider = MQTTPushProvider(mqtt_config)
        mock_mqtt_connect(provider)
        await provider.initialize()

        payload = PushNotificationPayload(
            title="Test",
            body="Test message",
            platform_data={"badge": 5, "sound": "alert.wav"},
        )

        message = provider._build_mqtt_message(payload)

        assert message["badge"] == 5
        assert message["sound"] == "alert.wav"

    @pytest.mark.asyncio
    @patch("homepot_client.push_notifications.mqtt_push.MQTT_AVAILABLE", True)
    @patch("homepot_client.push_notifications.mqtt_push.mqtt")
    async def test_get_platform_info(self, mock_mqtt, mqtt_config):
        """Test getting platform information."""
        mock_client = MagicMock()
        mock_mqtt.Client.return_value = mock_client

        provider = MQTTPushProvider(mqtt_config)

        # Mock the _connect method to avoid timeout
        async def mock_connect():
            provider._connected = True
            return True

        provider._connect = mock_connect

        mock_mqtt_connect(provider)
        await provider.initialize()
        provider._connected = True

        info = await provider.get_platform_info()

        assert info["platform"] == "mqtt_push"
        assert info["broker_host"] == "mqtt.example.com"
        assert info["broker_port"] == 1883
        assert info["connected"] is True
        assert info["qos"] == 1
        assert "statistics" in info

    @pytest.mark.asyncio
    @patch("homepot_client.push_notifications.mqtt_push.MQTT_AVAILABLE", True)
    @patch("homepot_client.push_notifications.mqtt_push.mqtt")
    async def test_statistics_tracking(self, mock_mqtt, mqtt_config, sample_payload):
        """Test that statistics are tracked correctly."""
        mock_client = MagicMock()
        mock_publish_success = MagicMock()
        mock_publish_success.rc = 0
        mock_publish_fail = MagicMock()
        mock_publish_fail.rc = 1
        mock_client.publish.side_effect = [mock_publish_success, mock_publish_fail]
        mock_mqtt.Client.return_value = mock_client
        mock_mqtt.MQTT_ERR_SUCCESS = 0

        provider = MQTTPushProvider(mqtt_config)
        mock_mqtt_connect(provider)
        await provider.initialize()
        provider._connected = True

        # Send successful notification
        await provider.send_notification(
            "devices/sensor-001/notifications", sample_payload
        )

        # Send failed notification
        await provider.send_notification(
            "devices/sensor-002/notifications", sample_payload
        )

        assert provider.stats["total_sent"] == 2
        assert provider.stats["total_success"] == 1
        assert provider.stats["total_failed"] == 1
        assert provider.stats["last_sent"] is not None

    @pytest.mark.asyncio
    @patch("homepot_client.push_notifications.mqtt_push.MQTT_AVAILABLE", True)
    @patch("homepot_client.push_notifications.mqtt_push.mqtt")
    async def test_cleanup(self, mock_mqtt, mqtt_config):
        """Test cleanup disconnects properly."""
        mock_client = MagicMock()
        mock_mqtt.Client.return_value = mock_client

        provider = MQTTPushProvider(mqtt_config)
        mock_mqtt_connect(provider)
        await provider.initialize()
        provider._connected = True

        await provider.cleanup()

        mock_client.loop_stop.assert_called_once()
        mock_client.disconnect.assert_called_once()
        assert provider._connected is False

    def test_callback_on_connect_success(self, mqtt_config):
        """Test _on_connect callback with successful connection."""
        provider = MQTTPushProvider(mqtt_config)

        # Simulate successful connection (rc=0)
        provider._on_connect(None, None, None, 0)

        assert provider._connected is True

    def test_callback_on_connect_failure(self, mqtt_config):
        """Test _on_connect callback with failed connection."""
        provider = MQTTPushProvider(mqtt_config)

        # Simulate failed connection (rc!=0)
        provider._on_connect(None, None, None, 5)

        assert provider._connected is False

    def test_callback_on_disconnect(self, mqtt_config):
        """Test _on_disconnect callback."""
        provider = MQTTPushProvider(mqtt_config)
        provider._connected = True

        # Simulate unexpected disconnection
        provider._on_disconnect(None, None, 1)

        assert provider._connected is False

    def test_callback_on_publish(self, mqtt_config):
        """Test _on_publish callback."""
        provider = MQTTPushProvider(mqtt_config)

        # Should not raise any exceptions
        provider._on_publish(None, None, 12345)


class TestMQTTPushIntegration:
    """Integration tests for MQTT Push provider."""

    @pytest.mark.asyncio
    @patch("homepot_client.push_notifications.mqtt_push.MQTT_AVAILABLE", True)
    @patch("homepot_client.push_notifications.mqtt_push.mqtt")
    async def test_full_workflow(self, mock_mqtt, mqtt_config, sample_payload):
        """Test complete workflow from initialization to cleanup."""
        mock_client = MagicMock()
        mock_publish_result = MagicMock()
        mock_publish_result.rc = 0
        mock_client.publish.return_value = mock_publish_result
        mock_mqtt.Client.return_value = mock_client
        mock_mqtt.MQTT_ERR_SUCCESS = 0

        # Initialize provider
        provider = MQTTPushProvider(mqtt_config)
        mock_mqtt_connect(provider)
        await provider.initialize()

        # Simulate connection
        provider._connected = True

        # Validate token
        assert (
            provider.validate_device_token("devices/sensor-001/notifications") is True
        )

        # Send notification
        result = await provider.send_notification(
            device_token="devices/sensor-001/notifications",
            payload=sample_payload,
        )
        assert result.success is True

        # Get platform info
        info = await provider.get_platform_info()
        assert info["connected"] is True

        # Cleanup
        await provider.cleanup()
        assert provider._connected is False

    @pytest.mark.asyncio
    @patch("homepot_client.push_notifications.mqtt_push.MQTT_AVAILABLE", True)
    @patch("homepot_client.push_notifications.mqtt_push.mqtt")
    async def test_multiple_qos_levels(self, mock_mqtt, sample_payload):
        """Test provider with different QoS levels."""
        mock_client = MagicMock()
        mock_publish_result = MagicMock()
        mock_publish_result.rc = 0
        mock_client.publish.return_value = mock_publish_result
        mock_mqtt.Client.return_value = mock_client
        mock_mqtt.MQTT_ERR_SUCCESS = 0

        for qos in [0, 1, 2]:
            config = {"broker_host": "mqtt.example.com", "qos": qos}
            provider = MQTTPushProvider(config)
            assert provider.qos == qos

            mock_mqtt_connect(provider)
            await provider.initialize()
            provider._connected = True

            result = await provider.send_notification(
                "devices/test/notifications", sample_payload
            )
            assert result.success is True
