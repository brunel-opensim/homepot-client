"""Apple Push Notification service (APNs) provider.

This module implements push notifications for Apple platforms including:
- iOS (iPhone, iPad)
- macOS (Mac computers)
- watchOS (Apple Watch)
- tvOS (Apple TV)

APNs uses JWT-based authentication with P8 private keys and communicates
via HTTP/2 protocol. This provider supports:
- Token-based authentication (recommended by Apple)
- Single device notifications
- Bulk notifications via HTTP/2 multiplexing
- Topic-based notifications
- Silent background notifications
- Alert notifications with sound and badge

Authentication Flow:
1. Load P8 private key from Apple Developer account
2. Generate JWT token signed with the private key
3. Include JWT in Authorization header for each request
4. JWT tokens expire after 1 hour, automatically refreshed

Configuration Requirements:
{
    "team_id": "ABC123DEFG",           # 10-character Apple Team ID
    "key_id": "XYZ987WXYZ",            # 10-character Key ID
    "auth_key_path": "/path/to/AuthKey_XYZ987WXYZ.p8",
    "bundle_id": "com.homepot.client", # App bundle identifier
    "environment": "production",        # or "sandbox" for testing
    "topic": "com.homepot.client"      # Usually same as bundle_id
}

APNs Endpoints:
- Production: https://api.push.apple.com
- Sandbox: https://api.sandbox.push.apple.com
"""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import jwt

from .base import (
    AuthenticationError,
    InvalidTokenError,
    NetworkError,
    PayloadTooLargeError,
    PushNotificationError,
    PushNotificationPayload,
    PushNotificationProvider,
    PushNotificationResult,
    PushPriority,
)

logger = logging.getLogger(__name__)

# APNs Configuration
APNS_PRODUCTION_URL = "https://api.push.apple.com"
APNS_SANDBOX_URL = "https://api.sandbox.push.apple.com"
APNS_MAX_PAYLOAD_SIZE = 4096  # 4KB limit for APNs
JWT_EXPIRATION_SECONDS = 3600  # 1 hour
JWT_REFRESH_THRESHOLD = 300  # Refresh 5 minutes before expiration


class APNsProvider(PushNotificationProvider):
    """Apple Push Notification service provider.

    This provider implements push notifications for all Apple platforms using
    token-based authentication with P8 private keys and HTTP/2 protocol.

    The provider handles:
    - JWT token generation and automatic refresh
    - HTTP/2 persistent connections
    - Device token validation (64 hexadecimal characters)
    - Payload size validation (4KB limit)
    - APNs-specific error handling
    - Priority mapping (normal=5, high=10)
    - Silent and alert notifications
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize APNs provider.

        Args:
            config: Configuration dictionary containing:
                - team_id: Apple Team ID (10 characters)
                - key_id: APNs Key ID (10 characters)
                - auth_key_path: Path to .p8 private key file
                - bundle_id: App bundle identifier
                - environment: "production" or "sandbox"
                - topic: Notification topic (usually bundle_id)

        Raises:
            ValueError: If required configuration is missing
        """
        super().__init__(config)

        # Validate required configuration
        required_fields = [
            "team_id",
            "key_id",
            "auth_key_path",
            "bundle_id",
            "environment",
        ]
        missing = [field for field in required_fields if field not in config]
        if missing:
            raise ValueError(f"Missing required APNs config: {missing}")

        # Extract configuration
        self.team_id = config["team_id"]
        self.key_id = config["key_id"]
        self.auth_key_path = config["auth_key_path"]
        self.bundle_id = config["bundle_id"]
        self.environment = config["environment"]
        self.topic = config.get("topic", self.bundle_id)

        # Validate environment
        if self.environment not in ["production", "sandbox"]:
            raise ValueError(
                f"Invalid environment: {self.environment}. "
                "Must be 'production' or 'sandbox'"
            )

        # Set base URL based on environment
        self.base_url = (
            APNS_PRODUCTION_URL
            if self.environment == "production"
            else APNS_SANDBOX_URL
        )

        # JWT token management
        self._jwt_token: Optional[str] = None
        self._jwt_expires_at: Optional[datetime] = None
        self._private_key: Optional[str] = None

        # HTTP/2 client
        self._client: Optional[httpx.AsyncClient] = None

        self.logger.info(
            f"Initialized APNs provider for {self.environment} "
            f"environment (topic: {self.topic})"
        )

    async def initialize(self) -> bool:
        """Initialize the APNs provider.

        This method:
        1. Loads the P8 private key from file
        2. Generates the first JWT token
        3. Creates HTTP/2 client with persistent connection

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Load P8 private key
            self._load_private_key()

            # Generate initial JWT token
            self._generate_jwt_token()

            # Create HTTP/2 client
            self._client = httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(30.0),
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            )

            self._initialized = True
            self.logger.info("APNs provider initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize APNs provider: {e}")
            return False

    def _load_private_key(self) -> None:
        """Load P8 private key from file.

        Raises:
            FileNotFoundError: If key file doesn't exist
            ValueError: If key file is invalid
        """
        key_path = Path(self.auth_key_path)

        if not key_path.exists():
            raise FileNotFoundError(f"APNs key file not found: {self.auth_key_path}")

        try:
            self._private_key = key_path.read_text().strip()

            # Basic validation
            if not self._private_key.startswith("-----BEGIN PRIVATE KEY-----"):
                raise ValueError("Invalid P8 key format")

            self.logger.info(f"Loaded APNs private key from {self.auth_key_path}")

        except Exception as e:
            raise ValueError(f"Failed to load APNs private key: {e}")

    def _generate_jwt_token(self) -> None:
        """Generate JWT token for APNs authentication.

        APNs JWT structure:
        - Header: alg=ES256, kid=<key_id>
        - Payload: iss=<team_id>, iat=<timestamp>
        - Signature: Signed with P8 private key

        The token is valid for 1 hour and includes the issue timestamp.
        """
        if not self._private_key:
            raise AuthenticationError(
                "Private key not loaded", platform="apns", error_code="NO_PRIVATE_KEY"
            )

        try:
            # JWT header
            headers = {"alg": "ES256", "kid": self.key_id}

            # JWT payload
            issued_at = int(time.time())
            payload = {"iss": self.team_id, "iat": issued_at}

            # Generate token
            self._jwt_token = jwt.encode(
                payload, self._private_key, algorithm="ES256", headers=headers
            ).decode("utf-8")

            # Set expiration time
            self._jwt_expires_at = datetime.utcnow() + timedelta(
                seconds=JWT_EXPIRATION_SECONDS
            )

            self.logger.debug(
                f"Generated APNs JWT token (expires at {self._jwt_expires_at})"
            )

        except Exception as e:
            raise AuthenticationError(
                f"Failed to generate JWT token: {e}",
                platform="apns",
                error_code="JWT_GENERATION_FAILED",
            )

    def _is_jwt_expired(self) -> bool:
        """Check if JWT token needs refresh.

        Returns:
            True if token is expired or will expire soon
        """
        if not self._jwt_token or not self._jwt_expires_at:
            return True

        # Refresh if token expires within threshold
        time_until_expiry = (self._jwt_expires_at - datetime.utcnow()).total_seconds()
        return time_until_expiry < JWT_REFRESH_THRESHOLD

    def _ensure_valid_jwt(self) -> None:
        """Ensure JWT token is valid, refresh if needed."""
        if self._is_jwt_expired():
            self.logger.info("JWT token expired or expiring soon, refreshing...")
            self._generate_jwt_token()

    async def send_notification(
        self, device_token: str, payload: PushNotificationPayload
    ) -> PushNotificationResult:
        """Send a push notification to a single Apple device.

        Args:
            device_token: APNs device token (64 hexadecimal characters)
            payload: Notification payload

        Returns:
            Result of the notification attempt

        Raises:
            InvalidTokenError: If device token format is invalid
            PayloadTooLargeError: If payload exceeds 4KB
            AuthenticationError: If JWT authentication fails
            NetworkError: If network request fails
        """
        if not self._initialized:
            raise RuntimeError("APNs provider not initialized")

        # Validate device token
        if not self.validate_device_token(device_token):
            return PushNotificationResult(
                success=False,
                message=f"Invalid device token format: {device_token}",
                platform="apns",
                device_token=device_token,
                error_code="INVALID_TOKEN",
            )

        try:
            # Ensure JWT is valid
            self._ensure_valid_jwt()

            # Build APNs payload
            apns_payload = self._build_apns_payload(payload)

            # Validate payload size
            payload_size = len(json.dumps(apns_payload).encode("utf-8"))
            if payload_size > APNS_MAX_PAYLOAD_SIZE:
                raise PayloadTooLargeError(
                    f"Payload size ({payload_size} bytes) exceeds "
                    f"APNs limit ({APNS_MAX_PAYLOAD_SIZE} bytes)",
                    platform="apns",
                    error_code="PAYLOAD_TOO_LARGE",
                )

            # Send notification
            result = await self._send_request(device_token, apns_payload, payload)

            return result

        except (InvalidTokenError, PayloadTooLargeError, AuthenticationError) as e:
            return PushNotificationResult(
                success=False,
                message=str(e),
                platform="apns",
                device_token=device_token,
                error_code=e.error_code,
            )
        except Exception as e:
            self.logger.error(f"Failed to send APNs notification: {e}")
            return PushNotificationResult(
                success=False,
                message=f"Unexpected error: {e}",
                platform="apns",
                device_token=device_token,
                error_code="UNKNOWN_ERROR",
            )

    async def _send_request(
        self,
        device_token: str,
        apns_payload: Dict[str, Any],
        original_payload: PushNotificationPayload,
    ) -> PushNotificationResult:
        """Send HTTP/2 request to APNs.

        Args:
            device_token: Device token
            apns_payload: APNs-formatted payload
            original_payload: Original notification payload

        Returns:
            Result of the request
        """
        if not self._client:
            raise RuntimeError("HTTP client not initialized")

        # Build request URL
        url = f"{self.base_url}/3/device/{device_token}"

        # Build headers
        headers = {
            "authorization": f"bearer {self._jwt_token}",
            "apns-topic": self.topic,
            "apns-priority": self._map_priority(original_payload.priority),
        }

        # Add expiration if set
        if original_payload.expires_at:
            expiration_timestamp = int(original_payload.expires_at.timestamp())
            headers["apns-expiration"] = str(expiration_timestamp)

        # Add collapse ID if set
        if original_payload.collapse_key:
            headers["apns-collapse-id"] = original_payload.collapse_key

        try:
            # Send HTTP/2 POST request
            response = await self._client.post(url, json=apns_payload, headers=headers)

            # Handle response
            return self._handle_response(response, device_token)

        except httpx.TimeoutException as e:
            raise NetworkError(
                f"Request timeout: {e}", platform="apns", error_code="TIMEOUT"
            )
        except httpx.NetworkError as e:
            raise NetworkError(
                f"Network error: {e}", platform="apns", error_code="NETWORK_ERROR"
            )
        except Exception as e:
            raise PushNotificationError(
                f"Request failed: {e}", platform="apns", error_code="REQUEST_FAILED"
            )

    def _handle_response(
        self, response: httpx.Response, device_token: str
    ) -> PushNotificationResult:
        """Handle APNs response.

        APNs Status Codes:
        - 200: Success
        - 400: Bad request (malformed payload)
        - 403: Invalid authentication token
        - 404: Invalid device token or topic
        - 410: Device token no longer active (uninstalled)
        - 413: Payload too large
        - 429: Too many requests
        - 500/503: Server error

        Args:
            response: HTTP response
            device_token: Device token

        Returns:
            Result with appropriate status and error code
        """
        status = response.status_code

        # Success
        if status == 200:
            # Extract apns-id from headers if available
            apns_id = response.headers.get("apns-id")
            return PushNotificationResult(
                success=True,
                message="Notification sent successfully",
                platform="apns",
                device_token=device_token,
                message_id=apns_id,
            )

        # Parse error response
        try:
            error_data = response.json()
            reason = error_data.get("reason", "Unknown error")
        except Exception:
            reason = "Unknown error"

        # Handle specific errors
        if status == 400:
            return PushNotificationResult(
                success=False,
                message=f"Bad request: {reason}",
                platform="apns",
                device_token=device_token,
                error_code="BAD_REQUEST",
            )
        elif status == 403:
            return PushNotificationResult(
                success=False,
                message=f"Authentication failed: {reason}",
                platform="apns",
                device_token=device_token,
                error_code="AUTH_FAILED",
            )
        elif status == 404:
            return PushNotificationResult(
                success=False,
                message=f"Invalid token or topic: {reason}",
                platform="apns",
                device_token=device_token,
                error_code="NOT_FOUND",
            )
        elif status == 410:
            # Device token no longer valid - app uninstalled
            return PushNotificationResult(
                success=False,
                message=f"Device token inactive: {reason}",
                platform="apns",
                device_token=device_token,
                error_code="UNREGISTERED",
            )
        elif status == 413:
            return PushNotificationResult(
                success=False,
                message=f"Payload too large: {reason}",
                platform="apns",
                device_token=device_token,
                error_code="PAYLOAD_TOO_LARGE",
            )
        elif status == 429:
            return PushNotificationResult(
                success=False,
                message=f"Too many requests: {reason}",
                platform="apns",
                device_token=device_token,
                error_code="TOO_MANY_REQUESTS",
                retry_after=60,  # Retry after 1 minute
            )
        elif status in [500, 503]:
            return PushNotificationResult(
                success=False,
                message=f"Server error: {reason}",
                platform="apns",
                device_token=device_token,
                error_code="SERVER_ERROR",
                retry_after=30,  # Retry after 30 seconds
            )
        else:
            return PushNotificationResult(
                success=False,
                message=f"Unexpected status {status}: {reason}",
                platform="apns",
                device_token=device_token,
                error_code=f"HTTP_{status}",
            )

    def _build_apns_payload(self, payload: PushNotificationPayload) -> Dict[str, Any]:
        """Build APNs-specific payload structure.

        APNs Payload Format:
        {
            "aps": {
                "alert": {
                    "title": "Title",
                    "body": "Body"
                },
                "badge": 1,
                "sound": "default",
                "content-available": 1
            },
            "custom-key": "custom-value"
        }

        Args:
            payload: Generic notification payload

        Returns:
            APNs-formatted payload dictionary
        """
        # Build aps dictionary
        aps: Dict[str, Any] = {}

        # Add alert
        aps["alert"] = {"title": payload.title, "body": payload.body}

        # Add badge if specified in platform_data
        if "badge" in payload.platform_data:
            aps["badge"] = payload.platform_data["badge"]

        # Add sound
        sound = payload.platform_data.get("sound", "default")
        if sound:
            aps["sound"] = sound

        # Add content-available for background notifications
        if payload.platform_data.get("content_available", False):
            aps["content-available"] = 1

        # Add mutable-content for notification service extensions
        if payload.platform_data.get("mutable_content", False):
            aps["mutable-content"] = 1

        # Add category for actionable notifications
        if "category" in payload.platform_data:
            aps["category"] = payload.platform_data["category"]

        # Build complete payload
        apns_payload = {"aps": aps}

        # Add custom data
        if payload.data:
            apns_payload.update(payload.data)

        return apns_payload

    def _map_priority(self, priority: PushPriority) -> str:
        """Map generic priority to APNs priority.

        APNs Priorities:
        - 10: High priority (immediate delivery, wakes device)
        - 5: Normal priority (conserves power)

        Args:
            priority: Generic priority level

        Returns:
            APNs priority as string ("5" or "10")
        """
        if priority in [PushPriority.HIGH, PushPriority.CRITICAL]:
            return "10"
        return "5"

    async def send_bulk_notifications(
        self, notifications: List[tuple[str, PushNotificationPayload]]
    ) -> List[PushNotificationResult]:
        """Send push notifications to multiple devices.

        APNs doesn't have a native batch API, but HTTP/2 multiplexing
        allows sending multiple requests concurrently over the same connection.

        Args:
            notifications: List of (device_token, payload) tuples

        Returns:
            List of results for each notification
        """
        if not self._initialized:
            raise RuntimeError("APNs provider not initialized")

        # Send all notifications concurrently using HTTP/2
        import asyncio

        tasks = [
            self.send_notification(device_token, payload)
            for device_token, payload in notifications
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        processed_results: List[PushNotificationResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                device_token = notifications[i][0]
                processed_results.append(
                    PushNotificationResult(
                        success=False,
                        message=f"Exception: {result}",
                        platform="apns",
                        device_token=device_token,
                        error_code="EXCEPTION",
                    )
                )
            else:
                processed_results.append(result)  # type: ignore[arg-type]

        return processed_results

    async def send_topic_notification(
        self, topic: str, payload: PushNotificationPayload
    ) -> PushNotificationResult:
        """Send a push notification to a topic.

        Note: APNs doesn't support topic-based messaging in the same way
        as FCM. APNs topics are used for identifying the app, not for
        user subscription groups.

        For broadcast notifications, you need to maintain a list of device
        tokens and use send_bulk_notifications instead.

        Args:
            topic: Topic name (not used in APNs)
            payload: Notification payload

        Returns:
            Error result indicating topic messaging is not supported
        """
        return PushNotificationResult(
            success=False,
            message="APNs does not support topic-based messaging. "
            "Use send_bulk_notifications with device token list instead.",
            platform="apns",
            error_code="TOPIC_NOT_SUPPORTED",
        )

    def validate_device_token(self, token: str) -> bool:
        """Validate APNs device token format.

        APNs device tokens are exactly 64 hexadecimal characters.

        Args:
            token: Device token to validate

        Returns:
            True if token format is valid, False otherwise
        """
        if not token:
            return False

        # Must be exactly 64 characters
        if len(token) != 64:
            return False

        # Must be valid hexadecimal
        try:
            int(token, 16)
            return True
        except ValueError:
            return False

    async def get_platform_info(self) -> Dict[str, Any]:
        """Get APNs platform information.

        Returns:
            Dictionary containing platform-specific information
        """
        return {
            "platform": "apns",
            "environment": self.environment,
            "base_url": self.base_url,
            "topic": self.topic,
            "bundle_id": self.bundle_id,
            "team_id": self.team_id,
            "key_id": self.key_id,
            "http2_enabled": True,
            "max_payload_size": APNS_MAX_PAYLOAD_SIZE,
            "jwt_valid": not self._is_jwt_expired() if self._jwt_token else False,
            "jwt_expires_at": (
                self._jwt_expires_at.isoformat() if self._jwt_expires_at else None
            ),
        }

    async def cleanup(self) -> None:
        """Clean up resources when shutting down the provider."""
        await super().cleanup()

        if self._client:
            await self._client.aclose()
            self._client = None

        self._jwt_token = None
        self._jwt_expires_at = None
        self._private_key = None

        self.logger.info("APNs provider cleaned up")
