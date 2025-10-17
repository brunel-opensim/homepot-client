"""Tests for Firebase Cloud Messaging (FCM) Linux provider.

This test suite validates the FCM Linux push notification provider,
including authentication, notification sending, error handling, and
batch operations.
"""

# ruff: noqa: S105 - Test file contains mock tokens, not real secrets

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from homepot_client.push_notifications.base import (
    PushNotificationPayload,
    PushPriority,
)
from homepot_client.push_notifications.fcm_linux import FCMLinuxProvider


@pytest.fixture
def temp_service_account(tmp_path):
    """Create a temporary service account JSON file."""
    service_account_data = {
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "key123",
        "private_key": (
            "-----BEGIN PRIVATE KEY-----\n"
            "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC\n"
            "-----END PRIVATE KEY-----\n"
        ),
        "client_email": "test@test-project.iam.gserviceaccount.com",
        "client_id": "123456789",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    }

    service_account_file = tmp_path / "service-account.json"
    service_account_file.write_text(json.dumps(service_account_data))
    return str(service_account_file)


@pytest.fixture
def fcm_config(temp_service_account):
    """Provide test FCM configuration."""
    return {
        "service_account_path": temp_service_account,
        "project_id": "test-project-id",
        "batch_size": 500,
        "timeout_seconds": 30,
    }


@pytest.fixture
def sample_device_token():
    """Provide a sample FCM device token."""
    # FCM tokens are typically 152-163 characters
    return "f" + "a" * 151  # 152 character token


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


class TestFCMLinuxProvider:
    """Test suite for FCM Linux provider."""

    @pytest.mark.asyncio
    async def test_initialization_success(self, fcm_config):
        """Test successful FCM provider initialization."""
        with (
            patch("aiohttp.ClientSession") as mock_session_class,
            patch(
                "google.oauth2.service_account.Credentials.from_service_account_file"
            ) as mock_creds,
        ):

            # Mock credentials
            mock_credentials = Mock()
            mock_credentials.token = "test-access-token"
            mock_credentials.expiry = None
            mock_creds.return_value = mock_credentials

            # Mock session
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            provider = FCMLinuxProvider(fcm_config)

            # Mock the refresh method
            with patch.object(
                provider, "_refresh_access_token", new_callable=AsyncMock
            ):
                result = await provider.initialize()

                assert result is True
                assert provider._initialized is True

            await provider.cleanup()

    @pytest.mark.asyncio
    async def test_initialization_missing_config(self):
        """Test initialization fails with missing configuration."""
        provider = FCMLinuxProvider(
            {"project_id": "test"}
        )  # Missing service_account_path

        result = await provider.initialize()

        assert result is False
        assert provider._initialized is False

    @pytest.mark.asyncio
    async def test_initialization_missing_file(self):
        """Test initialization fails with non-existent service account file."""
        config = {
            "service_account_path": "/nonexistent/file.json",
            "project_id": "test-project",
        }

        provider = FCMLinuxProvider(config)
        result = await provider.initialize()

        assert result is False
        assert provider._initialized is False

    @pytest.mark.asyncio
    async def test_validate_device_token_valid(self, fcm_config, sample_device_token):
        """Test validation of valid FCM device token."""
        provider = FCMLinuxProvider(fcm_config)

        assert provider.validate_device_token(sample_device_token) is True

    @pytest.mark.asyncio
    async def test_validate_device_token_invalid(self, fcm_config):
        """Test validation of invalid device tokens."""
        provider = FCMLinuxProvider(fcm_config)

        # Test various invalid formats
        assert provider.validate_device_token("") is False
        assert provider.validate_device_token("too-short") is False
        assert provider.validate_device_token("a" * 200) is False  # Too long
        assert provider.validate_device_token("invalid chars!!!") is False
        assert provider.validate_device_token(123) is False  # Not a string

    @pytest.mark.asyncio
    async def test_send_notification_success(
        self, fcm_config, sample_device_token, sample_payload
    ):
        """Test successful notification sending."""
        with (
            patch("aiohttp.ClientSession") as mock_session_class,
            patch(
                "google.oauth2.service_account.Credentials.from_service_account_file"
            ) as mock_creds,
        ):

            # Mock credentials
            mock_credentials = Mock()
            mock_credentials.token = "test-access-token"
            mock_creds.return_value = mock_credentials

            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            # Mock successful FCM response
            send_response = AsyncMock()
            send_response.status = 200
            send_response.json = AsyncMock(
                return_value={"name": "projects/test/messages/msg-123"}
            )
            send_context = AsyncMock()
            send_context.__aenter__ = AsyncMock(return_value=send_response)
            send_context.__aexit__ = AsyncMock(return_value=None)

            mock_session.post = MagicMock(return_value=send_context)

            provider = FCMLinuxProvider(fcm_config)

            # Mock initialization
            with patch.object(
                provider, "_refresh_access_token", new_callable=AsyncMock
            ):
                await provider.initialize()

                # Set token manually for test
                provider._access_token = "test-token"

                result = await provider.send_notification(
                    sample_device_token, sample_payload
                )

                assert result.success is True
                assert result.platform == "fcm_linux"
                assert result.message_id == "msg-123"

            await provider.cleanup()

    @pytest.mark.asyncio
    async def test_send_notification_invalid_token(self, fcm_config, sample_payload):
        """Test sending notification with invalid device token."""
        with (
            patch("aiohttp.ClientSession") as mock_session_class,
            patch(
                "google.oauth2.service_account.Credentials.from_service_account_file"
            ) as mock_creds,
        ):

            # Mock credentials
            mock_credentials = Mock()
            mock_credentials.token = "test-access-token"
            mock_creds.return_value = mock_credentials

            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            provider = FCMLinuxProvider(fcm_config)

            with patch.object(
                provider, "_refresh_access_token", new_callable=AsyncMock
            ):
                await provider.initialize()
                provider._access_token = "test-token"

                result = await provider.send_notification(
                    "invalid-token", sample_payload
                )

                assert result.success is False
                assert result.error_code == "INVALID_TOKEN"

            await provider.cleanup()

    @pytest.mark.asyncio
    async def test_send_notification_fcm_error(
        self, fcm_config, sample_device_token, sample_payload
    ):
        """Test handling of FCM API errors."""
        with (
            patch("aiohttp.ClientSession") as mock_session_class,
            patch(
                "google.oauth2.service_account.Credentials.from_service_account_file"
            ) as mock_creds,
        ):

            # Mock credentials
            mock_credentials = Mock()
            mock_credentials.token = "test-access-token"
            mock_creds.return_value = mock_credentials

            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            # Mock 404 error response
            send_response = AsyncMock()
            send_response.status = 404
            send_response.json = AsyncMock(
                return_value={
                    "error": {
                        "status": "NOT_FOUND",
                        "message": "Requested entity was not found",
                    }
                }
            )
            send_context = AsyncMock()
            send_context.__aenter__ = AsyncMock(return_value=send_response)
            send_context.__aexit__ = AsyncMock(return_value=None)

            mock_session.post = MagicMock(return_value=send_context)

            provider = FCMLinuxProvider(fcm_config)

            with patch.object(
                provider, "_refresh_access_token", new_callable=AsyncMock
            ):
                await provider.initialize()
                provider._access_token = "test-token"

                result = await provider.send_notification(
                    sample_device_token, sample_payload
                )

                assert result.success is False
                # Error code should be mapped from FCM error

            await provider.cleanup()

    @pytest.mark.asyncio
    async def test_send_bulk_notifications(
        self, fcm_config, sample_device_token, sample_payload
    ):
        """Test sending bulk notifications."""
        with (
            patch("aiohttp.ClientSession") as mock_session_class,
            patch(
                "google.oauth2.service_account.Credentials.from_service_account_file"
            ) as mock_creds,
        ):

            # Mock credentials
            mock_credentials = Mock()
            mock_credentials.token = "test-access-token"
            mock_creds.return_value = mock_credentials

            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            # Mock successful sends
            send_response = AsyncMock()
            send_response.status = 200
            send_response.json = AsyncMock(
                return_value={"name": "projects/test/messages/msg-123"}
            )
            send_context = AsyncMock()
            send_context.__aenter__ = AsyncMock(return_value=send_response)
            send_context.__aexit__ = AsyncMock(return_value=None)

            mock_session.post = MagicMock(return_value=send_context)

            provider = FCMLinuxProvider(fcm_config)

            with patch.object(
                provider, "_refresh_access_token", new_callable=AsyncMock
            ):
                await provider.initialize()
                provider._access_token = "test-token"

                # Create bulk notifications
                notifications = [
                    (f"{sample_device_token}-{i}", sample_payload) for i in range(5)
                ]

                results = await provider.send_bulk_notifications(notifications)

                assert len(results) == 5
                assert all(r.success for r in results)

            await provider.cleanup()

    @pytest.mark.asyncio
    async def test_send_topic_notification(self, fcm_config, sample_payload):
        """Test sending notification to a topic."""
        with (
            patch("aiohttp.ClientSession") as mock_session_class,
            patch(
                "google.oauth2.service_account.Credentials.from_service_account_file"
            ) as mock_creds,
        ):

            # Mock credentials
            mock_credentials = Mock()
            mock_credentials.token = "test-access-token"
            mock_creds.return_value = mock_credentials

            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            # Mock successful topic send
            send_response = AsyncMock()
            send_response.status = 200
            send_response.json = AsyncMock(
                return_value={"name": "projects/test/messages/msg-topic-123"}
            )
            send_context = AsyncMock()
            send_context.__aenter__ = AsyncMock(return_value=send_response)
            send_context.__aexit__ = AsyncMock(return_value=None)

            mock_session.post = MagicMock(return_value=send_context)

            provider = FCMLinuxProvider(fcm_config)

            with patch.object(
                provider, "_refresh_access_token", new_callable=AsyncMock
            ):
                await provider.initialize()
                provider._access_token = "test-token"

                result = await provider.send_topic_notification(
                    "pos-terminals", sample_payload
                )

                assert result.success is True
                assert result.platform == "fcm_linux"

            await provider.cleanup()

    @pytest.mark.asyncio
    async def test_build_fcm_message(
        self, fcm_config, sample_device_token, sample_payload
    ):
        """Test building FCM message structure."""
        provider = FCMLinuxProvider(fcm_config)

        message = provider._build_fcm_message(sample_device_token, sample_payload)

        assert "message" in message
        assert message["message"]["token"] == sample_device_token
        assert "data" in message["message"]
        assert message["message"]["data"]["title"] == sample_payload.title
        assert message["message"]["data"]["body"] == sample_payload.body
        assert "android" in message["message"]
        assert message["message"]["android"]["priority"] == "high"

    @pytest.mark.asyncio
    async def test_priority_mapping(self, fcm_config):
        """Test priority mapping from our enum to FCM priority."""
        provider = FCMLinuxProvider(fcm_config)

        assert provider._map_priority_to_fcm(PushPriority.LOW) == "normal"
        assert provider._map_priority_to_fcm(PushPriority.NORMAL) == "normal"
        assert provider._map_priority_to_fcm(PushPriority.HIGH) == "high"
        assert provider._map_priority_to_fcm(PushPriority.CRITICAL) == "high"

    @pytest.mark.asyncio
    async def test_get_platform_info(self, fcm_config):
        """Test getting platform information."""
        with (
            patch("aiohttp.ClientSession") as mock_session_class,
            patch(
                "google.oauth2.service_account.Credentials.from_service_account_file"
            ) as mock_creds,
        ):

            # Mock credentials
            mock_credentials = Mock()
            mock_credentials.token = "test-access-token"
            mock_creds.return_value = mock_credentials

            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            provider = FCMLinuxProvider(fcm_config)

            with patch.object(
                provider, "_refresh_access_token", new_callable=AsyncMock
            ):
                await provider.initialize()
                provider._access_token = "test-token"

                info = await provider.get_platform_info()

                assert info["platform"] == "fcm_linux"
                assert info["project_id"] == "test-project-id"
                assert info["service_status"] == "operational"
                assert info["batch_size"] == 500
                assert info["has_credentials"] is True

            await provider.cleanup()

    @pytest.mark.asyncio
    async def test_token_refresh(self, fcm_config):
        """Test access token refresh logic."""
        with (
            patch("aiohttp.ClientSession") as mock_session_class,
            patch(
                "google.oauth2.service_account.Credentials.from_service_account_file"
            ) as mock_creds,
        ):

            # Mock credentials with refresh capability
            mock_credentials = Mock()
            mock_credentials.token = None  # No initial token
            mock_credentials.expiry = None

            # Track refresh calls
            refresh_count = 0

            def mock_refresh(request):
                nonlocal refresh_count
                refresh_count += 1
                mock_credentials.token = f"token-refresh-{refresh_count}"

            mock_credentials.refresh = mock_refresh
            mock_creds.return_value = mock_credentials

            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            provider = FCMLinuxProvider(fcm_config)
            await provider.initialize()

            # First refresh happens during initialization
            assert provider._access_token == "token-refresh-1"
            assert refresh_count == 1

            # Force another refresh
            await provider._refresh_access_token()

            # Token should be refreshed again
            assert provider._access_token == "token-refresh-2"
            assert refresh_count == 2

            await provider.cleanup()

    @pytest.mark.asyncio
    async def test_payload_size_validation(self, fcm_config, sample_device_token):
        """Test payload size validation."""
        with (
            patch("aiohttp.ClientSession") as mock_session_class,
            patch(
                "google.oauth2.service_account.Credentials.from_service_account_file"
            ) as mock_creds,
        ):

            # Mock credentials
            mock_credentials = Mock()
            mock_credentials.token = "test-access-token"
            mock_creds.return_value = mock_credentials

            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            provider = FCMLinuxProvider(fcm_config)

            with patch.object(
                provider, "_refresh_access_token", new_callable=AsyncMock
            ):
                await provider.initialize()
                provider._access_token = "test-token"

                # Create oversized payload
                large_payload = PushNotificationPayload(
                    title="Test",
                    body="x" * 5000,  # Very large body
                    data={"key": "value" * 1000},
                )

                result = await provider.send_notification(
                    sample_device_token, large_payload
                )

                assert result.success is False
                assert result.error_code == "PAYLOAD_TOO_LARGE"

            await provider.cleanup()

    @pytest.mark.asyncio
    async def test_parse_fcm_error(self, fcm_config):
        """Test FCM error parsing."""
        provider = FCMLinuxProvider(fcm_config)

        # Test INVALID_ARGUMENT with token error
        error_code, error_msg = provider._parse_fcm_error(
            400,
            {
                "error": {
                    "status": "INVALID_ARGUMENT",
                    "message": "Invalid token provided",
                }
            },
        )
        assert error_code == "INVALID_TOKEN"

        # Test UNAUTHENTICATED
        error_code, error_msg = provider._parse_fcm_error(
            401,
            {
                "error": {
                    "status": "UNAUTHENTICATED",
                    "message": "Authentication failed",
                }
            },
        )
        assert error_code == "AUTHENTICATION_ERROR"

        # Test QUOTA_EXCEEDED
        error_code, error_msg = provider._parse_fcm_error(
            429, {"error": {"status": "QUOTA_EXCEEDED", "message": "Quota exceeded"}}
        )
        assert error_code == "QUOTA_EXCEEDED"

    @pytest.mark.asyncio
    async def test_health_check(self, fcm_config):
        """Test provider health check."""
        with (
            patch("aiohttp.ClientSession") as mock_session_class,
            patch(
                "google.oauth2.service_account.Credentials.from_service_account_file"
            ) as mock_creds,
        ):

            # Mock credentials
            mock_credentials = Mock()
            mock_credentials.token = "test-access-token"
            mock_creds.return_value = mock_credentials

            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            provider = FCMLinuxProvider(fcm_config)

            with patch.object(
                provider, "_refresh_access_token", new_callable=AsyncMock
            ):
                await provider.initialize()
                provider._access_token = "test-token"

                health = await provider.health_check()

                assert health["status"] == "healthy"
                assert health["platform"] == "fcm_linux"
                assert health["initialized"] is True

            await provider.cleanup()

    @pytest.mark.asyncio
    async def test_collapse_key_handling(self, fcm_config, sample_device_token):
        """Test collapse key is properly included in FCM message."""
        provider = FCMLinuxProvider(fcm_config)

        payload = PushNotificationPayload(
            title="Test",
            body="Test message",
            collapse_key="test-collapse-key",
        )

        message = provider._build_fcm_message(sample_device_token, payload)

        assert "android" in message["message"]
        assert message["message"]["android"]["collapse_key"] == "test-collapse-key"

    @pytest.mark.asyncio
    async def test_ttl_handling(self, fcm_config, sample_device_token):
        """Test TTL (time to live) is properly set in FCM message."""
        provider = FCMLinuxProvider(fcm_config)

        payload = PushNotificationPayload(
            title="Test",
            body="Test message",
            ttl_seconds=600,  # 10 minutes
        )

        message = provider._build_fcm_message(sample_device_token, payload)

        assert "android" in message["message"]
        assert message["message"]["android"]["ttl"] == "600s"
