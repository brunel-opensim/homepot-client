"""Tests for Windows Notification Service (WNS) provider.

This test suite validates the WNS Windows push notification provider,
including authentication, notification sending, error handling, and
batch operations.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homepot_client.push_notifications.base import (
    PushNotificationPayload,
    PushPriority,
)
from homepot_client.push_notifications.wns_windows import (
    WNSNotificationType,
    WNSWindowsProvider,
)


@pytest.fixture
def wns_config():
    """Provide test WNS configuration."""
    return {
        "package_sid": (
            "ms-app://s-1-15-2-1234567890-1234567890-1234567890-"
            "1234567890-1234567890-1234567890-1234567890"
        ),
        "client_secret": "test-client-secret-key",
        "notification_type": WNSNotificationType.TOAST,
        "batch_size": 100,
        "timeout_seconds": 30,
    }


@pytest.fixture
def sample_channel_uri():
    """Provide a sample WNS channel URI."""
    return "https://db5.notify.windows.com/?token=AwYAAACUmm%2fYzaXDvVN5A%2f..."


@pytest.fixture
def sample_payload():
    """Provide a sample notification payload."""
    return PushNotificationPayload(
        title="Configuration Update",
        body="New payment gateway settings available",
        data={
            "config_url": "https://example.com/config.json",
            "config_version": "v1.2.3",
        },
        priority=PushPriority.HIGH,
        ttl_seconds=300,
        collapse_key="config-update",
    )


class TestWNSWindowsProvider:
    """Test suite for WNS Windows provider."""

    @pytest.mark.asyncio
    async def test_initialization_success(self, wns_config):
        """Test successful WNS provider initialization."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            # Mock successful authentication
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value={
                    "access_token": "test-token",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                }
            )

            # Properly mock the context manager
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_session.post = MagicMock(return_value=mock_context)

            provider = WNSWindowsProvider(wns_config)
            result = await provider.initialize()

            assert result is True
            assert provider._initialized is True
            assert provider._access_token == "test-token"

            await provider.cleanup()

    @pytest.mark.asyncio
    async def test_initialization_missing_config(self):
        """Test initialization fails with missing configuration."""
        provider = WNSWindowsProvider({"package_sid": "test"})  # Missing client_secret

        result = await provider.initialize()

        assert result is False
        assert provider._initialized is False

    @pytest.mark.asyncio
    async def test_validate_device_token_valid(self, wns_config, sample_channel_uri):
        """Test validation of valid WNS channel URI."""
        provider = WNSWindowsProvider(wns_config)

        assert provider.validate_device_token(sample_channel_uri) is True

    @pytest.mark.asyncio
    async def test_validate_device_token_invalid(self, wns_config):
        """Test validation of invalid channel URIs."""
        provider = WNSWindowsProvider(wns_config)

        # Test various invalid formats
        assert provider.validate_device_token("") is False
        assert provider.validate_device_token("not-a-url") is False
        assert provider.validate_device_token("http://wrong-protocol.com") is False
        assert provider.validate_device_token("https://wrong-domain.com") is False

    @pytest.mark.asyncio
    async def test_send_notification_success(
        self, wns_config, sample_channel_uri, sample_payload
    ):
        """Test successful notification sending."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            # Mock authentication
            auth_response = AsyncMock()
            auth_response.status = 200
            auth_response.json = AsyncMock(
                return_value={
                    "access_token": "test-token",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                }
            )
            auth_context = AsyncMock()
            auth_context.__aenter__ = AsyncMock(return_value=auth_response)
            auth_context.__aexit__ = AsyncMock(return_value=None)

            # Mock notification send
            send_response = AsyncMock()
            send_response.status = 200
            send_response.headers = {
                "X-WNS-Status": "received",
                "X-WNS-DeviceConnectionStatus": "connected",
                "X-WNS-Msg-ID": "msg-123",
            }
            send_context = AsyncMock()
            send_context.__aenter__ = AsyncMock(return_value=send_response)
            send_context.__aexit__ = AsyncMock(return_value=None)

            mock_session.post = MagicMock(side_effect=[auth_context, send_context])

            provider = WNSWindowsProvider(wns_config)
            await provider.initialize()

            result = await provider.send_notification(
                sample_channel_uri, sample_payload
            )

            assert result.success is True
            assert result.platform == "wns_windows"
            assert result.message_id == "msg-123"

            await provider.cleanup()

    @pytest.mark.asyncio
    async def test_send_notification_invalid_token(self, wns_config, sample_payload):
        """Test sending notification with invalid channel URI."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            # Mock authentication
            auth_response = AsyncMock()
            auth_response.status = 200
            auth_response.json = AsyncMock(
                return_value={
                    "access_token": "test-token",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                }
            )
            auth_context = AsyncMock()
            auth_context.__aenter__ = AsyncMock(return_value=auth_response)
            auth_context.__aexit__ = AsyncMock(return_value=None)
            mock_session.post = MagicMock(return_value=auth_context)

            provider = WNSWindowsProvider(wns_config)
            await provider.initialize()

            result = await provider.send_notification("invalid-uri", sample_payload)

            assert result.success is False
            assert result.error_code == "INVALID_CHANNEL_URI"

            await provider.cleanup()

    @pytest.mark.asyncio
    async def test_send_notification_channel_expired(
        self, wns_config, sample_channel_uri, sample_payload
    ):
        """Test handling of expired channel URI (404 response)."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            # Mock authentication
            auth_response = AsyncMock()
            auth_response.status = 200
            auth_response.json = AsyncMock(
                return_value={
                    "access_token": "test-token",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                }
            )
            auth_context = AsyncMock()
            auth_context.__aenter__ = AsyncMock(return_value=auth_response)
            auth_context.__aexit__ = AsyncMock(return_value=None)

            # Mock 404 response
            send_response = AsyncMock()
            send_response.status = 404
            send_response.headers = {
                "X-WNS-Error-Description": "Channel expired",
            }
            send_context = AsyncMock()
            send_context.__aenter__ = AsyncMock(return_value=send_response)
            send_context.__aexit__ = AsyncMock(return_value=None)

            mock_session.post = MagicMock(side_effect=[auth_context, send_context])

            provider = WNSWindowsProvider(wns_config)
            await provider.initialize()

            result = await provider.send_notification(
                sample_channel_uri, sample_payload
            )

            assert result.success is False
            assert result.error_code == "CHANNEL_EXPIRED"

            await provider.cleanup()

    @pytest.mark.asyncio
    async def test_send_bulk_notifications(
        self, wns_config, sample_channel_uri, sample_payload
    ):
        """Test sending bulk notifications."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            # Mock authentication
            auth_response = AsyncMock()
            auth_response.status = 200
            auth_response.json = AsyncMock(
                return_value={
                    "access_token": "test-token",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                }
            )
            auth_context = AsyncMock()
            auth_context.__aenter__ = AsyncMock(return_value=auth_response)
            auth_context.__aexit__ = AsyncMock(return_value=None)

            # Mock successful sends
            send_response = AsyncMock()
            send_response.status = 200
            send_response.headers = {
                "X-WNS-Status": "received",
                "X-WNS-Msg-ID": "msg-123",
            }
            send_context = AsyncMock()
            send_context.__aenter__ = AsyncMock(return_value=send_response)
            send_context.__aexit__ = AsyncMock(return_value=None)

            mock_session.post = MagicMock(
                side_effect=[auth_context] + [send_context] * 5
            )

            provider = WNSWindowsProvider(wns_config)
            await provider.initialize()

            # Create bulk notifications
            notifications = [
                (f"{sample_channel_uri}-{i}", sample_payload) for i in range(5)
            ]

            results = await provider.send_bulk_notifications(notifications)

            assert len(results) == 5
            assert all(r.success for r in results)

            await provider.cleanup()

    @pytest.mark.asyncio
    async def test_build_toast_notification(self, wns_config, sample_payload):
        """Test building toast notification XML."""
        provider = WNSWindowsProvider(wns_config)

        content, content_type = provider._build_toast_notification(sample_payload)

        assert content_type == "text/xml"
        assert "<?xml version" in content
        assert "<toast>" in content
        assert sample_payload.title in content
        assert sample_payload.body in content

    @pytest.mark.asyncio
    async def test_build_raw_notification(self, wns_config, sample_payload):
        """Test building raw notification JSON."""
        config = wns_config.copy()
        config["notification_type"] = WNSNotificationType.RAW

        provider = WNSWindowsProvider(config)

        content, content_type = provider._build_raw_notification(sample_payload)

        assert content_type == "application/octet-stream"
        assert sample_payload.title in content
        assert sample_payload.body in content
        assert "config_url" in content

    @pytest.mark.asyncio
    async def test_xml_escaping(self, wns_config):
        """Test XML special character escaping."""
        provider = WNSWindowsProvider(wns_config)

        # Test escaping
        assert provider._escape_xml("Test & Co") == "Test &amp; Co"
        assert provider._escape_xml("A < B") == "A &lt; B"
        assert provider._escape_xml("A > B") == "A &gt; B"
        assert provider._escape_xml('Say "hello"') == "Say &quot;hello&quot;"

    @pytest.mark.asyncio
    async def test_get_platform_info(self, wns_config):
        """Test getting platform information."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            # Mock authentication
            auth_response = AsyncMock()
            auth_response.status = 200
            auth_response.json = AsyncMock(
                return_value={
                    "access_token": "test-token",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                }
            )
            auth_context = AsyncMock()
            auth_context.__aenter__ = AsyncMock(return_value=auth_response)
            auth_context.__aexit__ = AsyncMock(return_value=None)
            mock_session.post = MagicMock(return_value=auth_context)

            provider = WNSWindowsProvider(wns_config)
            await provider.initialize()

            info = await provider.get_platform_info()

            assert info["platform"] == "wns_windows"
            assert info["service_status"] == "operational"
            assert info["notification_type"] == WNSNotificationType.TOAST
            assert info["batch_size"] == 100
            assert info["token_valid"] is True

            await provider.cleanup()

    @pytest.mark.asyncio
    async def test_token_refresh(self, wns_config):
        """Test access token refresh logic."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            # Mock authentication responses
            auth_response = AsyncMock()
            auth_response.status = 200
            auth_response.json = AsyncMock(
                return_value={
                    "access_token": "new-token",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                }
            )
            auth_context = AsyncMock()
            auth_context.__aenter__ = AsyncMock(return_value=auth_response)
            auth_context.__aexit__ = AsyncMock(return_value=None)
            mock_session.post = MagicMock(return_value=auth_context)

            provider = WNSWindowsProvider(wns_config)
            await provider.initialize()

            # Force token to be invalid
            provider._token_expiry = 0

            # This should trigger a refresh
            await provider._ensure_valid_token()

            assert provider._access_token == "new-token"
            assert provider._is_token_valid() is True

            await provider.cleanup()

    @pytest.mark.asyncio
    async def test_payload_size_validation(self, wns_config, sample_channel_uri):
        """Test payload size validation."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            # Mock authentication
            auth_response = AsyncMock()
            auth_response.status = 200
            auth_response.json = AsyncMock(
                return_value={
                    "access_token": "test-token",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                }
            )
            auth_context = AsyncMock()
            auth_context.__aenter__ = AsyncMock(return_value=auth_response)
            auth_context.__aexit__ = AsyncMock(return_value=None)
            mock_session.post = MagicMock(return_value=auth_context)

            provider = WNSWindowsProvider(wns_config)
            await provider.initialize()

            # Create oversized payload
            large_payload = PushNotificationPayload(
                title="Test",
                body="x" * 10000,  # Very large body
                data={"key": "value" * 1000},
            )

            result = await provider.send_notification(sample_channel_uri, large_payload)

            assert result.success is False
            assert result.error_code == "PAYLOAD_TOO_LARGE"

            await provider.cleanup()
