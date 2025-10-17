"""Tests for Apple Push Notification service (APNs) provider.

This test suite validates the APNs provider implementation including:
- Configuration and initialization
- JWT token generation and refresh
- Device token validation
- Single and bulk notification sending
- Error handling for APNs-specific responses
- HTTP/2 communication
- Payload formatting and size validation
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from homepot_client.push_notifications.apns_apple import (
    APNS_MAX_PAYLOAD_SIZE,
    APNS_PRODUCTION_URL,
    APNS_SANDBOX_URL,
    APNsProvider,
)
from homepot_client.push_notifications.base import (
    PushNotificationPayload,
    PushPriority,
)

# Sample P8 private key for testing (not a real key)
MOCK_P8_KEY = """-----BEGIN PRIVATE KEY-----
MIGTAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBHkwdwIBAQQg6tXhB/JqB8xPDZGp
j5fvVvVvVvVvVvVvVvVvVvVvVvWgCgYIKoZIzj0DAQehRANCAATvVvVvVvVvVvVv
VvVvVvVvVvVvVvVvVvVvVvVvVvVvVvVvVvVvVvVvVvVvVvVvVvVvVvVvVvVvVvVv
VvVvVvVv
-----END PRIVATE KEY-----"""


@pytest.fixture
def temp_p8_key():
    """Create a temporary P8 key file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".p8", delete=False) as temp_file:
        temp_file.write(MOCK_P8_KEY)
        temp_path = temp_file.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink()


@pytest.fixture
def apns_config(temp_p8_key):
    """Provide APNs provider configuration for testing."""
    return {
        "team_id": "ABC123DEFG",
        "key_id": "XYZ987WXYZ",
        "auth_key_path": temp_p8_key,
        "bundle_id": "com.homepot.client",
        "environment": "sandbox",
        "topic": "com.homepot.client",
    }


@pytest.fixture
def valid_device_token():
    """Provide valid APNs device token (64 hex characters)."""
    return "a" * 64


@pytest.fixture
def sample_payload():
    """Provide sample notification payload."""
    return PushNotificationPayload(
        title="Payment Pending",
        body="Transaction #12345 awaiting approval",
        data={"transaction_id": "12345", "pos_id": "POS-001"},
        priority=PushPriority.HIGH,
    )


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================


def test_apns_provider_initialization_success(apns_config):
    """Test successful APNs provider initialization."""
    provider = APNsProvider(apns_config)

    assert provider.team_id == "ABC123DEFG"
    assert provider.key_id == "XYZ987WXYZ"
    assert provider.bundle_id == "com.homepot.client"
    assert provider.environment == "sandbox"
    assert provider.topic == "com.homepot.client"
    assert provider.base_url == APNS_SANDBOX_URL


def test_apns_provider_production_environment(apns_config):
    """Test production environment configuration."""
    apns_config["environment"] = "production"
    provider = APNsProvider(apns_config)

    assert provider.environment == "production"
    assert provider.base_url == APNS_PRODUCTION_URL


def test_apns_provider_missing_config():
    """Test initialization with missing required configuration."""
    with pytest.raises(ValueError, match="Missing required APNs config"):
        APNsProvider({})


def test_apns_provider_invalid_environment(apns_config):
    """Test initialization with invalid environment."""
    apns_config["environment"] = "invalid"

    with pytest.raises(ValueError, match="Invalid environment"):
        APNsProvider(apns_config)


@pytest.mark.asyncio
async def test_apns_provider_initialize(apns_config):
    """Test async initialization of APNs provider."""
    provider = APNsProvider(apns_config)

    with patch("jwt.encode", return_value="mock_jwt_token"):
        success = await provider.initialize()

    assert success is True
    assert provider._initialized is True
    assert provider._jwt_token == "mock_jwt_token"  # noqa: S105
    assert provider._client is not None
    assert isinstance(provider._client, httpx.AsyncClient)

    # Cleanup
    await provider.cleanup()


@pytest.mark.asyncio
async def test_apns_provider_initialize_missing_key_file(apns_config):
    """Test initialization fails with missing key file."""
    apns_config["auth_key_path"] = "/nonexistent/path.p8"
    provider = APNsProvider(apns_config)

    success = await provider.initialize()
    assert success is False


# ============================================================================
# JWT TOKEN TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_jwt_token_generation(apns_config):
    """Test JWT token generation."""
    provider = APNsProvider(apns_config)

    with patch("jwt.encode", return_value="mock_jwt_token") as mock_encode:
        await provider.initialize()

        # Verify jwt.encode was called with correct parameters
        mock_encode.assert_called_once()
        call_args = mock_encode.call_args

        # Check algorithm
        assert call_args.kwargs["algorithm"] == "ES256"

        # Check headers
        headers = call_args.kwargs["headers"]
        assert headers["alg"] == "ES256"
        assert headers["kid"] == "XYZ987WXYZ"

        # Check payload
        payload = call_args.args[0]
        assert payload["iss"] == "ABC123DEFG"
        assert "iat" in payload

    await provider.cleanup()


@pytest.mark.asyncio
async def test_jwt_token_refresh(apns_config):
    """Test JWT token automatic refresh."""
    provider = APNsProvider(apns_config)

    with patch("jwt.encode", return_value="mock_jwt_token"):
        await provider.initialize()

        # Simulate expired token
        provider._jwt_expires_at = datetime.utcnow() - timedelta(seconds=10)

        # Check token is expired
        assert provider._is_jwt_expired() is True

        # Refresh should generate new token
        with patch("jwt.encode", return_value="new_jwt_token"):
            provider._ensure_valid_jwt()
            assert provider._jwt_token == "new_jwt_token"  # noqa: S105

    await provider.cleanup()


# ============================================================================
# DEVICE TOKEN VALIDATION TESTS
# ============================================================================


def test_validate_device_token_valid(apns_config, valid_device_token):
    """Test validation of valid device token."""
    provider = APNsProvider(apns_config)
    assert provider.validate_device_token(valid_device_token) is True


def test_validate_device_token_invalid_length(apns_config):
    """Test validation rejects tokens with wrong length."""
    provider = APNsProvider(apns_config)

    # Too short
    assert provider.validate_device_token("a" * 63) is False

    # Too long
    assert provider.validate_device_token("a" * 65) is False


def test_validate_device_token_invalid_hex(apns_config):
    """Test validation rejects non-hexadecimal tokens."""
    provider = APNsProvider(apns_config)

    # Contains non-hex characters
    invalid_token = "g" * 64
    assert provider.validate_device_token(invalid_token) is False


def test_validate_device_token_empty(apns_config):
    """Test validation rejects empty token."""
    provider = APNsProvider(apns_config)
    assert provider.validate_device_token("") is False


# ============================================================================
# PAYLOAD BUILDING TESTS
# ============================================================================


def test_build_apns_payload_basic(apns_config, sample_payload):
    """Test building basic APNs payload."""
    provider = APNsProvider(apns_config)
    apns_payload = provider._build_apns_payload(sample_payload)

    assert "aps" in apns_payload
    assert apns_payload["aps"]["alert"]["title"] == "Payment Pending"
    assert apns_payload["aps"]["alert"]["body"] == (
        "Transaction #12345 awaiting approval"
    )
    assert apns_payload["aps"]["sound"] == "default"
    assert apns_payload["transaction_id"] == "12345"
    assert apns_payload["pos_id"] == "POS-001"


def test_build_apns_payload_with_badge(apns_config):
    """Test APNs payload with badge count."""
    provider = APNsProvider(apns_config)

    payload = PushNotificationPayload(
        title="New Message",
        body="You have a new message",
        platform_data={"badge": 5},
    )

    apns_payload = provider._build_apns_payload(payload)
    assert apns_payload["aps"]["badge"] == 5


def test_build_apns_payload_content_available(apns_config):
    """Test APNs payload with content-available flag."""
    provider = APNsProvider(apns_config)

    payload = PushNotificationPayload(
        title="Background Sync",
        body="Syncing data",
        platform_data={"content_available": True},
    )

    apns_payload = provider._build_apns_payload(payload)
    assert apns_payload["aps"]["content-available"] == 1


def test_build_apns_payload_custom_sound(apns_config):
    """Test APNs payload with custom sound."""
    provider = APNsProvider(apns_config)

    payload = PushNotificationPayload(
        title="Alert",
        body="Important notification",
        platform_data={"sound": "custom_sound.caf"},
    )

    apns_payload = provider._build_apns_payload(payload)
    assert apns_payload["aps"]["sound"] == "custom_sound.caf"


def test_map_priority(apns_config):
    """Test priority mapping to APNs values."""
    provider = APNsProvider(apns_config)

    assert provider._map_priority(PushPriority.LOW) == "5"
    assert provider._map_priority(PushPriority.NORMAL) == "5"
    assert provider._map_priority(PushPriority.HIGH) == "10"
    assert provider._map_priority(PushPriority.CRITICAL) == "10"


# ============================================================================
# SEND NOTIFICATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_send_notification_success(
    apns_config, valid_device_token, sample_payload
):
    """Test successful notification send."""
    provider = APNsProvider(apns_config)

    with patch("jwt.encode", return_value="mock_jwt_token"):
        await provider.initialize()

        # Mock successful HTTP response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"apns-id": "test-apns-id-12345"}

        with patch.object(
            provider._client, "post", return_value=mock_response
        ) as mock_post:
            result = await provider.send_notification(
                valid_device_token, sample_payload
            )

            # Verify request was made
            mock_post.assert_called_once()
            call_args = mock_post.call_args

            # Check URL
            expected_url = f"{APNS_SANDBOX_URL}/3/device/{valid_device_token}"
            assert call_args.args[0] == expected_url

            # Check headers
            headers = call_args.kwargs["headers"]
            assert headers["authorization"] == "bearer mock_jwt_token"
            assert headers["apns-topic"] == "com.homepot.client"
            assert headers["apns-priority"] == "10"  # HIGH priority

            # Check result
            assert result.success is True
            assert result.message_id == "test-apns-id-12345"
            assert result.platform == "apns"

    await provider.cleanup()


@pytest.mark.asyncio
async def test_send_notification_invalid_token(apns_config, sample_payload):
    """Test sending notification with invalid device token."""
    provider = APNsProvider(apns_config)

    with patch("jwt.encode", return_value="mock_jwt_token"):
        await provider.initialize()

        invalid_token = "invalid"  # noqa: S105
        result = await provider.send_notification(invalid_token, sample_payload)

        assert result.success is False
        assert result.error_code == "INVALID_TOKEN"

    await provider.cleanup()


@pytest.mark.asyncio
async def test_send_notification_payload_too_large(apns_config, valid_device_token):
    """Test sending notification with payload exceeding size limit."""
    provider = APNsProvider(apns_config)

    with patch("jwt.encode", return_value="mock_jwt_token"):
        await provider.initialize()

        # Create oversized payload
        large_data = {"data": "x" * APNS_MAX_PAYLOAD_SIZE}
        large_payload = PushNotificationPayload(
            title="Test", body="Test", data=large_data
        )

        result = await provider.send_notification(valid_device_token, large_payload)

        assert result.success is False
        assert result.error_code == "PAYLOAD_TOO_LARGE"

    await provider.cleanup()


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_code,expected_error_code",
    [
        (400, "BAD_REQUEST"),
        (403, "AUTH_FAILED"),
        (404, "NOT_FOUND"),
        (410, "UNREGISTERED"),
        (413, "PAYLOAD_TOO_LARGE"),
        (429, "TOO_MANY_REQUESTS"),
        (500, "SERVER_ERROR"),
        (503, "SERVER_ERROR"),
    ],
)
async def test_handle_error_responses(
    apns_config, valid_device_token, sample_payload, status_code, expected_error_code
):
    """Test handling of various APNs error responses."""
    provider = APNsProvider(apns_config)

    with patch("jwt.encode", return_value="mock_jwt_token"):
        await provider.initialize()

        # Mock error response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = status_code
        mock_response.json.return_value = {"reason": "TestError"}

        with patch.object(provider._client, "post", return_value=mock_response):
            result = await provider.send_notification(
                valid_device_token, sample_payload
            )

            assert result.success is False
            assert result.error_code == expected_error_code

    await provider.cleanup()


@pytest.mark.asyncio
async def test_handle_unregistered_device(
    apns_config, valid_device_token, sample_payload
):
    """Test handling 410 status (device unregistered)."""
    provider = APNsProvider(apns_config)

    with patch("jwt.encode", return_value="mock_jwt_token"):
        await provider.initialize()

        # Mock 410 response (device uninstalled app)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 410
        mock_response.json.return_value = {"reason": "Unregistered"}

        with patch.object(provider._client, "post", return_value=mock_response):
            result = await provider.send_notification(
                valid_device_token, sample_payload
            )

            # Should indicate device token is inactive
            assert result.success is False
            assert result.error_code == "UNREGISTERED"
            assert "inactive" in result.message.lower()

    await provider.cleanup()


@pytest.mark.asyncio
async def test_handle_network_timeout(apns_config, valid_device_token, sample_payload):
    """Test handling network timeout."""
    provider = APNsProvider(apns_config)

    with patch("jwt.encode", return_value="mock_jwt_token"):
        await provider.initialize()

        # Mock timeout exception
        with patch.object(
            provider._client, "post", side_effect=httpx.TimeoutException("Timeout")
        ):
            result = await provider.send_notification(
                valid_device_token, sample_payload
            )

            assert result.success is False
            assert "timeout" in result.message.lower()

    await provider.cleanup()


# ============================================================================
# BULK NOTIFICATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_send_bulk_notifications_success(apns_config, sample_payload):
    """Test sending bulk notifications."""
    provider = APNsProvider(apns_config)

    with patch("jwt.encode", return_value="mock_jwt_token"):
        await provider.initialize()

        # Create multiple device tokens
        device_tokens = [f"{i:064x}" for i in range(5)]

        notifications = [(token, sample_payload) for token in device_tokens]

        # Mock successful responses
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"apns-id": "test-id"}

        with patch.object(provider._client, "post", return_value=mock_response):
            results = await provider.send_bulk_notifications(notifications)

            assert len(results) == 5
            assert all(result.success for result in results)

    await provider.cleanup()


@pytest.mark.asyncio
async def test_send_bulk_notifications_mixed_results(apns_config, sample_payload):
    """Test bulk notifications with mixed success/failure."""
    provider = APNsProvider(apns_config)

    with patch("jwt.encode", return_value="mock_jwt_token"):
        await provider.initialize()

        device_tokens = [f"{i:064x}" for i in range(3)]
        notifications = [(token, sample_payload) for token in device_tokens]

        # Mock responses: success, failure, success
        responses = [
            MagicMock(
                spec=httpx.Response,
                status_code=200,
                headers={"apns-id": "success-1"},
            ),
            MagicMock(
                spec=httpx.Response,
                status_code=410,
                json=lambda: {"reason": "Unregistered"},
            ),
            MagicMock(
                spec=httpx.Response,
                status_code=200,
                headers={"apns-id": "success-2"},
            ),
        ]

        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            response = responses[call_count]
            call_count += 1
            return response

        with patch.object(provider._client, "post", side_effect=mock_post):
            results = await provider.send_bulk_notifications(notifications)

            assert len(results) == 3
            assert results[0].success is True
            assert results[1].success is False
            assert results[1].error_code == "UNREGISTERED"
            assert results[2].success is True

    await provider.cleanup()


# ============================================================================
# TOPIC NOTIFICATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_send_topic_notification_not_supported(apns_config, sample_payload):
    """Test that topic notifications return not supported error."""
    provider = APNsProvider(apns_config)

    with patch("jwt.encode", return_value="mock_jwt_token"):
        await provider.initialize()

        result = await provider.send_topic_notification("test_topic", sample_payload)

        assert result.success is False
        assert result.error_code == "TOPIC_NOT_SUPPORTED"
        assert "not support" in result.message.lower()

    await provider.cleanup()


# ============================================================================
# PLATFORM INFO TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_get_platform_info(apns_config):
    """Test getting platform information."""
    provider = APNsProvider(apns_config)

    with patch("jwt.encode", return_value="mock_jwt_token"):
        await provider.initialize()

        info = await provider.get_platform_info()

        assert info["platform"] == "apns"
        assert info["environment"] == "sandbox"
        assert info["base_url"] == APNS_SANDBOX_URL
        assert info["topic"] == "com.homepot.client"
        assert info["bundle_id"] == "com.homepot.client"
        assert info["team_id"] == "ABC123DEFG"
        assert info["key_id"] == "XYZ987WXYZ"
        assert info["http2_enabled"] is True
        assert info["max_payload_size"] == APNS_MAX_PAYLOAD_SIZE
        assert info["jwt_valid"] is True

    await provider.cleanup()


@pytest.mark.asyncio
async def test_health_check(apns_config):
    """Test provider health check."""
    provider = APNsProvider(apns_config)

    with patch("jwt.encode", return_value="mock_jwt_token"):
        await provider.initialize()

        health = await provider.health_check()

        assert health["status"] == "healthy"
        assert health["platform"] == "apnsprovider"
        assert health["initialized"] is True

    await provider.cleanup()


# ============================================================================
# CLEANUP TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_cleanup(apns_config):
    """Test provider cleanup."""
    provider = APNsProvider(apns_config)

    with patch("jwt.encode", return_value="mock_jwt_token"):
        await provider.initialize()

        assert provider._client is not None
        assert provider._jwt_token is not None

        await provider.cleanup()

        assert provider._client is None
        assert provider._jwt_token is None
        assert provider._jwt_expires_at is None
        assert provider._initialized is False
