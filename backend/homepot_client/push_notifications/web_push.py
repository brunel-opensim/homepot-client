r"""Web Push Notification provider for web browsers.

This module implements Web Push notifications for modern web browsers including:
- Chrome/Edge (via Firebase Cloud Messaging endpoints)
- Firefox (via Mozilla Push Service)
- Safari (via Safari Push Notifications)
- Opera and other web browsers

Web Push provides:
- VAPID (Voluntary Application Server Identification) authentication
- Push API standard compliance
- Cross-browser compatibility
- Encrypted payload delivery
- Service Worker integration
- Notification permission management

Configuration required:
- vapid_private_key: VAPID private key (PEM format)
- vapid_public_key: VAPID public key (base64 URL-safe)
- vapid_subject: Contact email or URL (e.g., mailto:admin@example.com)
- ttl_seconds: Time-to-live for notifications (default: 300)

Example usage:
    config = {
        "vapid_private_key": "-----BEGIN EC PRIVATE KEY-----\\n...",
        "vapid_public_key": "BNcR...base64url...",
        "vapid_subject": "mailto:admin@example.com",
        "ttl_seconds": 300
    }

    web_push_provider = WebPushProvider(config)
    await web_push_provider.initialize()

    # Subscribe endpoint from browser
    subscription = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/...",
        "keys": {
            "p256dh": "BNcR...base64url...",
            "auth": "tBHI...base64url..."
        }
    }

    result = await web_push_provider.send_notification(
        device_token=json.dumps(subscription),
        payload=PushNotificationPayload(
            title="New Message",
            body="You have a new notification",
            data={"url": "/notifications"}
        )
    )
"""

import asyncio
import base64
import json
import logging
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import urlparse

try:
    from pywebpush import WebPushException, webpush

    WEBPUSH_AVAILABLE = True
except ImportError:
    WEBPUSH_AVAILABLE = False
    webpush = None
    WebPushException = Exception

from .base import (
    PushNotificationPayload,
    PushNotificationProvider,
    PushNotificationResult,
    PushPriority,
)

logger = logging.getLogger(__name__)


class WebPushProvider(PushNotificationProvider):
    """Web Push notification provider for web browsers.

    This provider implements the Web Push Protocol (RFC 8030) with VAPID
    authentication for sending push notifications to web browsers.
    """

    # Supported push service endpoints
    SUPPORTED_ENDPOINTS = [
        "fcm.googleapis.com",  # Chrome, Edge, Opera
        "updates.push.services.mozilla.com",  # Firefox
        "web.push.apple.com",  # Safari
        "notify.windows.com",  # Edge (legacy)
    ]

    # Web Push limits
    MAX_PAYLOAD_SIZE = 4096  # 4KB recommended
    DEFAULT_TTL = 300  # 5 minutes
    MAX_TTL = 2419200  # 28 days

    def __init__(self, config: Dict[str, Any]):
        """Initialize the Web Push provider.

        Args:
            config: Configuration dictionary containing:
                - vapid_private_key: VAPID private key (PEM format)
                - vapid_public_key: VAPID public key (base64 URL-safe)
                - vapid_subject: Contact information (mailto: or https:)
                - ttl_seconds: Time-to-live (optional, default: 300)
                - timeout_seconds: Request timeout (optional, default: 30)
        """
        super().__init__(config)
        self.platform_name = "web_push"

        # Required configuration - validated below
        vapid_private_key = config.get("vapid_private_key")
        vapid_public_key = config.get("vapid_public_key")
        vapid_subject = config.get("vapid_subject")

        # Validate configuration
        if not vapid_private_key or not vapid_public_key:
            raise ValueError(
                "Web Push requires 'vapid_private_key' and 'vapid_public_key'"
            )

        if not vapid_subject:
            raise ValueError(
                "Web Push requires 'vapid_subject' (mailto: or https: URL)"
            )

        if not vapid_subject.startswith(("mailto:", "https://")):
            raise ValueError("vapid_subject must start with 'mailto:' or 'https://'")

        # Assign validated values (now mypy knows they're not None)
        self.vapid_private_key: str = vapid_private_key
        self.vapid_public_key: str = vapid_public_key
        self.vapid_subject: str = vapid_subject

        # Optional configuration
        self.ttl_seconds = config.get("ttl_seconds", self.DEFAULT_TTL)
        self.timeout = config.get("timeout_seconds", 30)

        # Check if pywebpush is available
        if not WEBPUSH_AVAILABLE:
            logger.warning(
                "pywebpush library not installed. Web Push functionality limited. "
                "Install with: pip install pywebpush"
            )

        # Statistics tracking
        self.stats: Dict[str, Any] = {
            "total_sent": 0,
            "total_success": 0,
            "total_failed": 0,
            "last_sent": None,
        }

        self.logger.info(f"Initialized {self.platform_name} provider")

    async def initialize(self) -> bool:
        """Initialize the Web Push provider.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Validate VAPID keys format
            self._validate_vapid_keys()

            self._initialized = True
            self.logger.info(f"{self.platform_name} provider initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize {self.platform_name}: {e}")
            self._initialized = False
            return False

    def _validate_vapid_keys(self) -> None:
        """Validate VAPID key formats.

        Raises:
            ValueError: If key format is invalid
        """
        # Validate private key (PEM format)
        if not self.vapid_private_key.startswith("-----BEGIN"):
            raise ValueError("VAPID private key must be in PEM format")

        # Validate public key (base64 URL-safe)
        try:
            # Should be 65 bytes when decoded (uncompressed EC public key)
            decoded = base64.urlsafe_b64decode(
                self.vapid_public_key + "=" * (4 - len(self.vapid_public_key) % 4)
            )
            if len(decoded) != 65:
                raise ValueError("VAPID public key should be 65 bytes (uncompressed)")
        except Exception as e:
            raise ValueError(f"Invalid VAPID public key format: {e}")

    async def send_notification(
        self, device_token: str, payload: PushNotificationPayload
    ) -> PushNotificationResult:
        """Send a push notification to a single web browser.

        Args:
            device_token: JSON-encoded subscription object containing:
                - endpoint: Push service endpoint URL
                - keys: Dict with 'p256dh' and 'auth' keys
            payload: Notification payload

        Returns:
            Result of the push notification attempt
        """
        try:
            # Parse subscription from device token
            subscription = self._parse_subscription(device_token)

            # Validate subscription
            if not self._validate_subscription(subscription):
                return PushNotificationResult(
                    success=False,
                    message="Invalid subscription format",
                    platform=self.platform_name,
                    device_token=device_token[:50] + "...",
                    error_code="INVALID_SUBSCRIPTION",
                )

            # Build Web Push payload
            push_data = self._build_push_data(payload)

            # Send via pywebpush if available
            if WEBPUSH_AVAILABLE:
                result = await self._send_via_pywebpush(
                    subscription, push_data, payload
                )
            else:
                result = await self._send_via_manual_request(
                    subscription, push_data, payload
                )

            # Update statistics
            self.stats["total_sent"] += 1
            if result.success:
                self.stats["total_success"] += 1
            else:
                self.stats["total_failed"] += 1
            self.stats["last_sent"] = datetime.utcnow().isoformat()

            return result

        except Exception as e:
            self.logger.error(f"Failed to send Web Push notification: {e}")
            self.stats["total_failed"] += 1
            return PushNotificationResult(
                success=False,
                message=f"Send failed: {str(e)}",
                platform=self.platform_name,
                device_token=device_token[:50] + "...",
                error_code="SEND_FAILED",
            )

    async def _send_via_pywebpush(
        self,
        subscription: Dict[str, Any],
        push_data: str,
        payload: PushNotificationPayload,
    ) -> PushNotificationResult:
        """Send notification using pywebpush library.

        Args:
            subscription: Push subscription object
            push_data: JSON-encoded notification data
            payload: Original notification payload

        Returns:
            Push notification result
        """
        try:
            # Prepare VAPID claims
            vapid_claims = {"sub": self.vapid_subject}

            # Send push notification
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: webpush(
                    subscription_info=subscription,
                    data=push_data,
                    vapid_private_key=self.vapid_private_key,
                    vapid_claims=vapid_claims,
                    ttl=payload.ttl_seconds or self.ttl_seconds,
                ),
            )

            return PushNotificationResult(
                success=True,
                message="Push notification sent successfully",
                platform=self.platform_name,
                device_token=subscription["endpoint"][:50] + "...",
                message_id=None,  # Web Push doesn't return message ID
            )

        except WebPushException as e:
            self.logger.error(f"WebPushException: {e}")

            # Handle specific error cases
            if e.response and e.response.status_code == 410:
                # Subscription expired/invalid
                return PushNotificationResult(
                    success=False,
                    message="Subscription expired or invalid (410 Gone)",
                    platform=self.platform_name,
                    device_token=subscription["endpoint"][:50] + "...",
                    error_code="SUBSCRIPTION_EXPIRED",
                )
            elif e.response and e.response.status_code == 404:
                return PushNotificationResult(
                    success=False,
                    message="Subscription not found (404)",
                    platform=self.platform_name,
                    device_token=subscription["endpoint"][:50] + "...",
                    error_code="SUBSCRIPTION_NOT_FOUND",
                )
            else:
                return PushNotificationResult(
                    success=False,
                    message=f"WebPush failed: {str(e)}",
                    platform=self.platform_name,
                    device_token=subscription["endpoint"][:50] + "...",
                    error_code="WEBPUSH_ERROR",
                )

    async def _send_via_manual_request(
        self,
        subscription: Dict[str, Any],
        push_data: str,
        payload: PushNotificationPayload,
    ) -> PushNotificationResult:
        """Send notification via manual HTTP request (fallback).

        Args:
            subscription: Push subscription object
            push_data: JSON-encoded notification data
            payload: Original notification payload

        Returns:
            Push notification result
        """
        # This is a fallback implementation without pywebpush
        # Would require manual VAPID header generation and encryption
        return PushNotificationResult(
            success=False,
            message=(
                "pywebpush library not available. "
                "Please install: pip install pywebpush"
            ),
            platform=self.platform_name,
            device_token=subscription["endpoint"][:50] + "...",
            error_code="LIBRARY_NOT_AVAILABLE",
        )

    async def send_bulk_notifications(
        self, notifications: List[tuple[str, PushNotificationPayload]]
    ) -> List[PushNotificationResult]:
        """Send push notifications to multiple web browsers.

        Args:
            notifications: List of (device_token, payload) tuples

        Returns:
            List of results for each notification attempt
        """
        tasks = [
            self.send_notification(device_token, payload)
            for device_token, payload in notifications
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to failed results
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
                # result is PushNotificationResult here
                processed_results.append(result)  # type: ignore[arg-type]

        return processed_results

    async def send_topic_notification(
        self, topic: str, payload: PushNotificationPayload
    ) -> PushNotificationResult:
        """Send a push notification to a topic.

        Note: Web Push doesn't natively support topics. This would need to be
        implemented at the application level by maintaining topic subscriptions.

        Args:
            topic: Topic name
            payload: Notification payload

        Returns:
            Result indicating topics are not supported
        """
        return PushNotificationResult(
            success=False,
            message="Topic notifications not supported for Web Push. "
            "Implement topic management at application level.",
            platform=self.platform_name,
            error_code="TOPICS_NOT_SUPPORTED",
        )

    def validate_device_token(self, token: str) -> bool:
        """Validate a Web Push subscription format.

        Args:
            token: JSON-encoded subscription object

        Returns:
            True if subscription format is valid, False otherwise
        """
        try:
            subscription = self._parse_subscription(token)
            return self._validate_subscription(subscription)
        except Exception:
            return False

    def _parse_subscription(self, token: str) -> Dict[str, Any]:
        """Parse subscription from device token.

        Args:
            token: JSON-encoded subscription

        Returns:
            Subscription dictionary

        Raises:
            ValueError: If token is invalid
        """
        try:
            subscription: Dict[str, Any] = json.loads(token)
            return subscription
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid subscription JSON: {e}")

    def _validate_subscription(self, subscription: Dict[str, Any]) -> bool:
        """Validate subscription object format.

        Args:
            subscription: Subscription dictionary

        Returns:
            True if valid, False otherwise
        """
        # Check required fields
        if "endpoint" not in subscription:
            return False

        # Validate endpoint URL
        try:
            parsed = urlparse(subscription["endpoint"])
            if not parsed.scheme or not parsed.netloc:
                return False

            # Check if endpoint is from a known push service
            is_known_service = any(
                service in parsed.netloc for service in self.SUPPORTED_ENDPOINTS
            )
            if not is_known_service:
                self.logger.warning(f"Unknown push service endpoint: {parsed.netloc}")

        except Exception:
            return False

        # Check encryption keys (required for payload encryption)
        if "keys" in subscription:
            keys = subscription["keys"]
            if "p256dh" not in keys or "auth" not in keys:
                return False

        return True

    def _build_push_data(self, payload: PushNotificationPayload) -> str:
        """Build Web Push notification data payload.

        Args:
            payload: Notification payload

        Returns:
            JSON-encoded notification data
        """
        # Build notification object following Web Notification API format
        notification_data = {
            "notification": {
                "title": payload.title,
                "body": payload.body,
                "icon": payload.platform_data.get("icon"),
                "badge": payload.platform_data.get("badge"),
                "image": payload.platform_data.get("image"),
                "tag": payload.collapse_key,
                "requireInteraction": payload.priority
                in [
                    PushPriority.HIGH,
                    PushPriority.CRITICAL,
                ],
                "silent": payload.platform_data.get("silent", False),
                "vibrate": payload.platform_data.get("vibrate"),
                "timestamp": int(payload.created_at.timestamp() * 1000),
                "data": payload.data,
            }
        }

        # Add action buttons if specified
        if "actions" in payload.platform_data:
            notification_data["notification"]["actions"] = payload.platform_data[
                "actions"
            ]

        return json.dumps(notification_data)

    async def get_platform_info(self) -> Dict[str, Any]:
        """Get Web Push platform information.

        Returns:
            Dictionary containing platform information
        """
        return {
            "platform": self.platform_name,
            "vapid_subject": self.vapid_subject,
            "has_vapid_keys": bool(self.vapid_private_key and self.vapid_public_key),
            "pywebpush_available": WEBPUSH_AVAILABLE,
            "default_ttl": self.ttl_seconds,
            "max_payload_size": self.MAX_PAYLOAD_SIZE,
            "supported_services": self.SUPPORTED_ENDPOINTS,
            "statistics": self.stats,
        }

    def get_vapid_public_key(self) -> str:
        """Get the VAPID public key for client-side subscription.

        Returns:
            Base64 URL-safe encoded VAPID public key
        """
        return self.vapid_public_key
