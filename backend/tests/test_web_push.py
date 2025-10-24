"""Tests for Web Push notification provider."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from homepot_client.push_notifications.web_push import WebPushProvider
from homepot_client.push_notifications.base import (
    PushNotificationPayload,
    PushPriority,
)


@pytest.fixture
def web_push_config():
    """Provide Web Push configuration for testing."""
    return {
        "vapid_private_key": """-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg/enUgwULCGxZvVrv
9c3fXx+01poP45NJPN6WcfhT0qehRANCAASTmibcZrXiJa8rN1o/48ispQNpr8Al
KhSyjDxfVaszuOIzST7CYcmS70YYddT0EDOgMekEsyu8CRoabhcdws85
-----END PRIVATE KEY-----""",
        "vapid_public_key": "BJOaJtxmteIlrys3Wj_jyKylA2mvwCUqFLKMPF9VqzO44jNJPsJhyZLvRhh11PQQM6Ax6QSzK7wJGhpuFx3Czzk",
        "vapid_subject": "mailto:test@example.com",
        "ttl_seconds": 300,
    }


@pytest.fixture
def sample_subscription():
    """Provide a sample browser push subscription."""
    return {
        "endpoint": "https://fcm.googleapis.com/fcm/send/cLGI1J2qISw:APA91b...",
        "keys": {
            "p256dh": "BNcRd...base64url...",
            "auth": "tBHI...base64url...",
        },
    }


@pytest.fixture
async def web_push_provider(web_push_config):
    """Create and initialize a Web Push provider for testing."""
    provider = WebPushProvider(web_push_config)
    await provider.initialize()
    return provider


class TestWebPushProvider:
    """Test suite for Web Push notification provider."""

    def test_initialization_with_valid_config(self, web_push_config):
        """Test provider initialization with valid configuration."""
        provider = WebPushProvider(web_push_config)
        assert provider.platform_name == "web_push"
        assert provider.vapid_subject == "mailto:test@example.com"
        assert provider.ttl_seconds == 300

    def test_initialization_without_vapid_keys(self):
        """Test that initialization fails without VAPID keys."""
        with pytest.raises(ValueError, match="vapid_private_key"):
            WebPushProvider({"vapid_subject": "mailto:test@example.com"})

    def test_initialization_without_vapid_subject(self, web_push_config):
        """Test that initialization fails without VAPID subject."""
        config = web_push_config.copy()
        del config["vapid_subject"]

        with pytest.raises(ValueError, match="vapid_subject"):
            WebPushProvider(config)

    def test_initialization_with_invalid_vapid_subject(self, web_push_config):
        """Test that initialization fails with invalid VAPID subject format."""
        config = web_push_config.copy()
        config["vapid_subject"] = "invalid-subject"

        with pytest.raises(ValueError, match="must start with"):
            WebPushProvider(config)

    @pytest.mark.asyncio
    async def test_provider_initialization(self, web_push_provider):
        """Test successful provider initialization."""
        assert web_push_provider._initialized is True

    def test_validate_subscription_valid(
        self, web_push_provider, sample_subscription
    ):
        """Test subscription validation with valid subscription."""
        is_valid = web_push_provider._validate_subscription(sample_subscription)
        assert is_valid is True

    def test_validate_subscription_missing_endpoint(
        self, web_push_provider
    ):
        """Test subscription validation fails without endpoint."""
        invalid_subscription = {
            "keys": {
                "p256dh": "BNcRd...base64url...",
                "auth": "tBHI...base64url...",
            }
        }
        is_valid = web_push_provider._validate_subscription(invalid_subscription)
        assert is_valid is False

    def test_validate_subscription_invalid_endpoint(
        self, web_push_provider
    ):
        """Test subscription validation fails with invalid endpoint URL."""
        invalid_subscription = {"endpoint": "not-a-valid-url"}
        is_valid = web_push_provider._validate_subscription(invalid_subscription)
        assert is_valid is False

    def test_validate_device_token_valid(
        self, web_push_provider, sample_subscription
    ):
        """Test device token validation with valid subscription JSON."""
        device_token = json.dumps(sample_subscription)
        is_valid = web_push_provider.validate_device_token(device_token)
        assert is_valid is True

    def test_validate_device_token_invalid_json(self, web_push_provider):
        """Test device token validation fails with invalid JSON."""
        is_valid = web_push_provider.validate_device_token("not-valid-json")
        assert is_valid is False

    def test_build_push_data(self, web_push_provider):
        """Test building push notification data payload."""
        payload = PushNotificationPayload(
            title="Test Notification",
            body="This is a test message",
            data={"url": "/notifications"},
            priority=PushPriority.HIGH,
            platform_data={
                "icon": "/icon.png",
                "badge": "/badge.png",
            },
        )

        push_data = web_push_provider._build_push_data(payload)
        data = json.loads(push_data)

        assert "notification" in data
        assert data["notification"]["title"] == "Test Notification"
        assert data["notification"]["body"] == "This is a test message"
        assert data["notification"]["icon"] == "/icon.png"
        assert data["notification"]["badge"] == "/badge.png"
        assert data["notification"]["requireInteraction"] is True  # HIGH priority
        assert data["notification"]["data"]["url"] == "/notifications"

    @pytest.mark.asyncio
    @patch("homepot_client.push_notifications.web_push.WEBPUSH_AVAILABLE", True)
    @patch("homepot_client.push_notifications.web_push.webpush")
    async def test_send_notification_success(
        self, mock_webpush, web_push_provider, sample_subscription
    ):
        """Test successful notification sending."""
        # Mock webpush response
        mock_webpush.return_value = MagicMock(status_code=201)

        device_token = json.dumps(sample_subscription)
        payload = PushNotificationPayload(
            title="Test",
            body="Message",
            priority=PushPriority.NORMAL,
        )

        result = await web_push_provider.send_notification(device_token, payload)

        assert result.success is True
        assert result.platform == "web_push"
        assert "sent successfully" in result.message.lower()

    @pytest.mark.asyncio
    async def test_send_notification_invalid_subscription(
        self, web_push_provider
    ):
        """Test sending notification with invalid subscription."""
        invalid_token = json.dumps({"invalid": "subscription"})
        payload = PushNotificationPayload(title="Test", body="Message")

        result = await web_push_provider.send_notification(invalid_token, payload)

        assert result.success is False
        assert result.error_code == "INVALID_SUBSCRIPTION"

    @pytest.mark.asyncio
    @patch("homepot_client.push_notifications.web_push.WEBPUSH_AVAILABLE", False)
    async def test_send_notification_without_pywebpush(
        self, web_push_provider, sample_subscription
    ):
        """Test sending notification when pywebpush is not available."""
        device_token = json.dumps(sample_subscription)
        payload = PushNotificationPayload(title="Test", body="Message")

        result = await web_push_provider.send_notification(device_token, payload)

        assert result.success is False
        assert result.error_code == "LIBRARY_NOT_AVAILABLE"
        assert "pywebpush" in result.message

    @pytest.mark.asyncio
    async def test_send_bulk_notifications(
        self, web_push_provider, sample_subscription
    ):
        """Test sending bulk notifications."""
        device_token = json.dumps(sample_subscription)
        notifications = [
            (device_token, PushNotificationPayload(title=f"Test {i}", body="Message"))
            for i in range(3)
        ]

        with patch.object(
            web_push_provider,
            "send_notification",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = MagicMock(success=True)

            results = await web_push_provider.send_bulk_notifications(notifications)

            assert len(results) == 3
            assert mock_send.call_count == 3

    @pytest.mark.asyncio
    async def test_send_topic_notification_not_supported(
        self, web_push_provider
    ):
        """Test that topic notifications return not supported error."""
        payload = PushNotificationPayload(title="Test", body="Message")

        result = await web_push_provider.send_topic_notification("test-topic", payload)

        assert result.success is False
        assert result.error_code == "TOPICS_NOT_SUPPORTED"

    @pytest.mark.asyncio
    async def test_get_platform_info(self, web_push_provider):
        """Test getting platform information."""
        info = await web_push_provider.get_platform_info()

        assert info["platform"] == "web_push"
        assert info["vapid_subject"] == "mailto:test@example.com"
        assert info["has_vapid_keys"] is True
        assert info["default_ttl"] == 300
        assert "statistics" in info
        assert "supported_services" in info

    def test_get_vapid_public_key(self, web_push_provider):
        """Test getting VAPID public key."""
        public_key = web_push_provider.get_vapid_public_key()
        assert public_key == web_push_provider.vapid_public_key

    @pytest.mark.asyncio
    @patch("homepot_client.push_notifications.web_push.webpush")
    async def test_statistics_tracking(
        self, mock_webpush, web_push_provider, sample_subscription
    ):
        """Test that statistics are tracked correctly."""
        # Mock successful webpush response
        mock_webpush.return_value = MagicMock(status_code=201)
        
        device_token = json.dumps(sample_subscription)
        payload = PushNotificationPayload(title="Test", body="Message")

        initial_sent = web_push_provider.stats["total_sent"]
        initial_success = web_push_provider.stats["total_success"]

        # Send notification
        result = await web_push_provider.send_notification(device_token, payload)

        assert result.success is True
        assert web_push_provider.stats["total_sent"] == initial_sent + 1
        assert web_push_provider.stats["total_success"] == initial_success + 1
        assert web_push_provider.stats["last_sent"] is not None


class TestWebPushIntegration:
    """Integration tests for Web Push provider."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_notification_flow(
        self, web_push_config, sample_subscription
    ):
        """Test complete notification sending flow."""
        # Initialize provider
        provider = WebPushProvider(web_push_config)
        success = await provider.initialize()
        assert success is True

        # Validate subscription
        device_token = json.dumps(sample_subscription)
        is_valid = provider.validate_device_token(device_token)
        assert is_valid is True

        # Create payload
        payload = PushNotificationPayload(
            title="Integration Test",
            body="Testing Web Push notifications",
            data={"test": True},
            priority=PushPriority.HIGH,
            platform_data={
                "icon": "/test-icon.png",
                "requireInteraction": True,
            },
        )

        # Send notification (will fail without real subscription, but tests the flow)
        result = await provider.send_notification(device_token, payload)

        # Check result structure
        assert hasattr(result, "success")
        assert hasattr(result, "message")
        assert hasattr(result, "platform")
        assert result.platform == "web_push"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_health_check(self, web_push_config):
        """Test provider health check."""
        provider = WebPushProvider(web_push_config)
        await provider.initialize()

        health = await provider.health_check()

        assert health["status"] in ["healthy", "unhealthy"]
        assert health["platform"] == "web_push"
        assert health["initialized"] is True
        assert "platform_info" in health
