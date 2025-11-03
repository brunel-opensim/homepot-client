"""Windows Notification Service (WNS) provider for Windows devices.

This module implements WNS push notifications specifically for Windows-based
devices including:
- Windows IoT devices
- Windows-based POS terminals
- Windows desktop applications
- Windows embedded systems

WNS provides:
- OAuth 2.0 authentication via Azure AD
- Toast, tile, badge, and raw notification types
- Batch messaging support
- Channel URI management
- Error handling and retry logic
- Delivery status tracking

Configuration required:
- package_sid: Windows Package Security Identifier (SID)
- client_secret: Azure AD client secret for authentication
- notification_type: Type of notification (toast, tile, badge, raw)
- batch_size: Maximum messages per batch (default: 100)
- timeout_seconds: Request timeout (default: 30)

Example usage:
    config = {
        "package_sid": "ms-app://s-1-15-2-...",
        "client_secret": "your-azure-client-secret",
        "notification_type": "toast",
        "batch_size": 100,
        "timeout_seconds": 30
    }

    wns_provider = WNSWindowsProvider(config)
    await wns_provider.initialize()

    result = await wns_provider.send_notification(
        device_token="https://db5.notify.windows.com/?token=...",
        payload=PushNotificationPayload(
            title="Configuration Update",
            body="New payment gateway settings available",
            data={"config_url": "https://example.com/config.json"}
        )
    )
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import aiohttp

from .base import (
    AuthenticationError,
    NetworkError,
    PayloadTooLargeError,
    PushNotificationPayload,
    PushNotificationProvider,
    PushNotificationResult,
)

logger = logging.getLogger(__name__)


class WNSNotificationType:
    """WNS notification types."""

    TOAST = "toast"  # Pop-up notification
    TILE = "tile"  # Live tile update
    BADGE = "badge"  # Badge notification
    RAW = "raw"  # Raw data notification


class WNSWindowsProvider(PushNotificationProvider):
    """Windows Notification Service provider for Windows devices.

    This provider implements the WNS API for sending push notifications
    to Windows-based devices and applications.
    """

    # WNS endpoints
    WNS_AUTH_ENDPOINT = "https://login.live.com/accesstoken.srf"

    # WNS limits
    MAX_PAYLOAD_SIZE_TOAST = 5000  # 5KB for toast notifications
    MAX_PAYLOAD_SIZE_TILE = 5000  # 5KB for tile notifications
    MAX_PAYLOAD_SIZE_RAW = 5000  # 5KB for raw notifications
    MAX_BATCH_SIZE = 100
    MAX_TTL_SECONDS = 604800  # 7 days

    # WNS headers
    WNS_TYPE_HEADER = "X-WNS-Type"
    WNS_TTL_HEADER = "X-WNS-TTL"
    WNS_TAG_HEADER = "X-WNS-Tag"
    WNS_CACHE_POLICY_HEADER = "X-WNS-Cache-Policy"
    WNS_REQUEST_STATUS_HEADER = "X-WNS-Status"
    WNS_DEVICE_CONNECTION_STATUS = "X-WNS-DeviceConnectionStatus"
    WNS_ERROR_DESCRIPTION = "X-WNS-Error-Description"
    WNS_MSG_ID = "X-WNS-Msg-ID"

    def __init__(self, config: Dict[str, Any]):
        """Initialize the WNS Windows provider.

        Args:
            config: Configuration dictionary containing:
                - package_sid: Windows Package SID
                - client_secret: Azure AD client secret
                - notification_type: Type of notification (optional, default: toast)
                - batch_size: Maximum messages per batch (optional)
                - timeout_seconds: Request timeout (optional)
        """
        super().__init__(config)
        self.platform_name = "wns_windows"

        # Required configuration
        self.package_sid = config.get("package_sid")
        self.client_secret = config.get("client_secret")

        # Optional configuration
        self.notification_type = config.get(
            "notification_type", WNSNotificationType.TOAST
        )
        self.batch_size = min(config.get("batch_size", 100), self.MAX_BATCH_SIZE)
        self.timeout_seconds = config.get("timeout_seconds", 30)
        self.cache_policy = config.get("cache_policy", "cache")  # or "no-cache"

        # Authentication
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[float] = None
        self._token_type: str = "Bearer"

        # HTTP session
        self._session: Optional[aiohttp.ClientSession] = None

        self.logger.info(
            f"Initialized WNS Windows provider for package: {self.package_sid}"
        )

    async def initialize(self) -> bool:
        """Initialize the WNS provider with authentication.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Validate configuration
            if not self.package_sid:
                raise ValueError("package_sid is required")
            if not self.client_secret:
                raise ValueError("client_secret is required")

            # Validate notification type
            valid_types = [
                WNSNotificationType.TOAST,
                WNSNotificationType.TILE,
                WNSNotificationType.BADGE,
                WNSNotificationType.RAW,
            ]
            if self.notification_type not in valid_types:
                raise ValueError(
                    f"Invalid notification_type: {self.notification_type}. "
                    f"Must be one of: {valid_types}"
                )

            # Create HTTP session
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
            )

            # Get initial access token
            await self._refresh_access_token()

            self._initialized = True
            self.logger.info("WNS Windows provider initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize WNS Windows provider: {e}")
            return False

    async def send_notification(
        self, device_token: str, payload: PushNotificationPayload
    ) -> PushNotificationResult:
        """Send a push notification to a single Windows device via WNS.

        Args:
            device_token: WNS channel URI
            payload: Notification payload

        Returns:
            Result of the push notification attempt
        """
        if not self._initialized:
            raise RuntimeError("Provider not initialized")

        try:
            # Validate channel URI
            if not self.validate_device_token(device_token):
                return PushNotificationResult(
                    success=False,
                    message="Invalid WNS channel URI format",
                    platform=self.platform_name,
                    device_token=device_token,
                    error_code="INVALID_CHANNEL_URI",
                )

            # Build WNS notification
            notification_content, content_type = self._build_wns_notification(payload)

            # Validate payload size
            message_size = len(notification_content.encode("utf-8"))
            max_size = self._get_max_payload_size()
            if message_size > max_size:
                raise PayloadTooLargeError(
                    f"Payload too large: {message_size} bytes (max: {max_size})",
                    self.platform_name,
                    "PAYLOAD_TOO_LARGE",
                )

            # Send to WNS
            response = await self._send_wns_request(
                device_token, notification_content, content_type, payload
            )

            if response["success"]:
                return PushNotificationResult(
                    success=True,
                    message="Notification sent successfully via WNS",
                    platform=self.platform_name,
                    device_token=device_token,
                    message_id=response.get("message_id"),
                )
            else:
                return PushNotificationResult(
                    success=False,
                    message=response["error_message"],
                    platform=self.platform_name,
                    device_token=device_token,
                    error_code=response["error_code"],
                    retry_after=response.get("retry_after"),
                )

        except PayloadTooLargeError as e:
            self.logger.error(f"WNS payload too large for {device_token}: {e}")
            return PushNotificationResult(
                success=False,
                message=str(e),
                platform=self.platform_name,
                device_token=device_token,
                error_code="PAYLOAD_TOO_LARGE",
            )
        except Exception as e:
            self.logger.error(f"WNS notification failed for {device_token}: {e}")
            return PushNotificationResult(
                success=False,
                message=f"WNS error: {str(e)}",
                platform=self.platform_name,
                device_token=device_token,
                error_code="WNS_ERROR",
            )

    async def send_bulk_notifications(
        self, notifications: List[tuple[str, PushNotificationPayload]]
    ) -> List[PushNotificationResult]:
        """Send push notifications to multiple Windows devices efficiently.

        Args:
            notifications: List of (channel_uri, payload) tuples

        Returns:
            List of results for each notification
        """
        if not notifications:
            return []

        results = []

        # Process in batches with concurrency limit
        for i in range(0, len(notifications), self.batch_size):
            batch = notifications[i : i + self.batch_size]
            batch_results = await self._send_batch(batch)
            results.extend(batch_results)

        return results

    async def send_topic_notification(
        self, topic: str, payload: PushNotificationPayload
    ) -> PushNotificationResult:
        """Send a push notification to a topic (not natively supported by WNS).

        WNS doesn't have built-in topic support, so this method will query
        the database for devices matching the topic and send individually.

        Args:
            topic: Topic name (e.g., 'pos-terminals', 'site-123')
            payload: Notification payload

        Returns:
            Result of the topic notification
        """
        if not self._initialized:
            raise RuntimeError("Provider not initialized")

        try:
            # Get devices for topic from database
            from sqlalchemy import select

            from homepot.database import get_database_service
            from homepot.models import Device, DeviceType

            db_service = await get_database_service()

            devices: List[Device] = []
            async with db_service.get_session() as session:
                if topic.startswith("site-"):
                    # Topic is a site - get all devices for that site
                    site_id = topic.replace("site-", "")
                    result = await session.execute(
                        select(Device).where(
                            Device.site_id == int(site_id), Device.is_active.is_(True)
                        )
                    )
                    devices = list(result.scalars().all())
                elif topic == "pos-terminals":
                    # Get all POS terminals
                    result = await session.execute(
                        select(Device).where(
                            Device.device_type == DeviceType.POS_TERMINAL,
                            Device.is_active.is_(True),
                        )
                    )
                    devices = list(result.scalars().all())

            if not devices:
                return PushNotificationResult(
                    success=False,
                    message=f"No devices found for topic: {topic}",
                    platform=self.platform_name,
                    error_code="NO_DEVICES",
                )

            # Send to all devices in the topic
            notifications = [(str(device.device_id), payload) for device in devices]
            results = await self.send_bulk_notifications(notifications)

            # Summarize results
            successful = sum(1 for r in results if r.success)
            total = len(results)

            return PushNotificationResult(
                success=successful > 0,
                message=(
                    f"Topic notification sent to "
                    f"{successful}/{total} Windows devices"
                ),
                platform=self.platform_name,
            )

        except Exception as e:
            self.logger.error(f"WNS topic notification failed for {topic}: {e}")
            return PushNotificationResult(
                success=False,
                message=f"WNS topic error: {str(e)}",
                platform=self.platform_name,
                error_code="WNS_TOPIC_ERROR",
            )

    def validate_device_token(self, token: str) -> bool:
        """Validate WNS channel URI format.

        Args:
            token: WNS channel URI

        Returns:
            True if channel URI format appears valid
        """
        if not isinstance(token, str):
            return False

        # WNS channel URIs start with https://
        if not token.startswith("https://"):
            return False

        # Common WNS domains
        wns_domains = [
            "notify.windows.com",
            "db3.notify.windows.com",
            "db4.notify.windows.com",
            "db5.notify.windows.com",
            "db6.notify.windows.com",
        ]

        # Check if URI contains a valid WNS domain
        return any(domain in token for domain in wns_domains)

    async def get_platform_info(self) -> Dict[str, Any]:
        """Get WNS platform information and status.

        Returns:
            Platform status and configuration
        """
        return {
            "platform": "wns_windows",
            "package_sid": self.package_sid[:20] + "..." if self.package_sid else None,
            "service_status": "operational" if self._initialized else "not_initialized",
            "notification_type": self.notification_type,
            "batch_size": self.batch_size,
            "timeout_seconds": self.timeout_seconds,
            "cache_policy": self.cache_policy,
            "token_valid": self._is_token_valid(),
            "max_payload_size": self._get_max_payload_size(),
            "max_batch_size": self.MAX_BATCH_SIZE,
            "max_ttl_seconds": self.MAX_TTL_SECONDS,
        }

    async def cleanup(self) -> None:
        """Clean up WNS provider resources."""
        if self._session:
            await self._session.close()
            self._session = None

        self._access_token = None
        self._token_expiry = None

        await super().cleanup()

    async def _refresh_access_token(self) -> None:
        """Refresh the OAuth2 access token for WNS API."""
        if not self.package_sid or not self.client_secret:
            raise AuthenticationError(
                "Missing package_sid or client_secret", self.platform_name
            )

        try:
            # Prepare authentication request
            auth_data = {
                "grant_type": "client_credentials",
                "client_id": self.package_sid,
                "client_secret": self.client_secret,
                "scope": "notify.windows.com",
            }

            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
            }

            if self._session is None:
                raise RuntimeError("HTTP session not initialized")

            # Request access token
            async with self._session.post(
                self.WNS_AUTH_ENDPOINT,
                data=urlencode(auth_data),
                headers=headers,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise AuthenticationError(
                        f"WNS authentication failed: {error_text}", self.platform_name
                    )

                auth_response = await response.json()

                self._access_token = auth_response.get("access_token")
                self._token_type = auth_response.get("token_type", "Bearer")
                expires_in = int(auth_response.get("expires_in", 86400))

                # Set expiry time (with 5 minute buffer)
                self._token_expiry = time.time() + expires_in - 300

                self.logger.debug("WNS access token refreshed successfully")

        except aiohttp.ClientError as e:
            raise AuthenticationError(
                f"Network error during WNS authentication: {e}", self.platform_name
            )
        except Exception as e:
            raise AuthenticationError(
                f"Failed to refresh WNS access token: {e}", self.platform_name
            )

    def _is_token_valid(self) -> bool:
        """Check if the current access token is valid."""
        if not self._access_token or not self._token_expiry:
            return False

        # Check if token is still valid
        return time.time() < self._token_expiry

    async def _ensure_valid_token(self) -> None:
        """Ensure we have a valid access token, refresh if needed."""
        if not self._is_token_valid():
            await self._refresh_access_token()

    def _get_max_payload_size(self) -> int:
        """Get maximum payload size for current notification type."""
        if self.notification_type == WNSNotificationType.TOAST:
            return self.MAX_PAYLOAD_SIZE_TOAST
        elif self.notification_type == WNSNotificationType.TILE:
            return self.MAX_PAYLOAD_SIZE_TILE
        elif self.notification_type == WNSNotificationType.RAW:
            return self.MAX_PAYLOAD_SIZE_RAW
        else:
            return self.MAX_PAYLOAD_SIZE_TOAST

    def _build_wns_notification(
        self, payload: PushNotificationPayload
    ) -> tuple[str, str]:
        """Build WNS notification content and content type.

        Args:
            payload: Notification payload

        Returns:
            Tuple of (notification_content, content_type)
        """
        # Get notification type from platform data or use default
        platform_data = payload.platform_data.get("wns_windows", {})
        notification_type = platform_data.get("type", self.notification_type)

        if notification_type == WNSNotificationType.TOAST:
            return self._build_toast_notification(payload)
        elif notification_type == WNSNotificationType.TILE:
            return self._build_tile_notification(payload)
        elif notification_type == WNSNotificationType.BADGE:
            return self._build_badge_notification(payload)
        elif notification_type == WNSNotificationType.RAW:
            return self._build_raw_notification(payload)
        else:
            # Default to toast
            return self._build_toast_notification(payload)

    def _build_toast_notification(
        self, payload: PushNotificationPayload
    ) -> tuple[str, str]:
        """Build WNS toast notification XML.

        Args:
            payload: Notification payload

        Returns:
            Tuple of (toast_xml, content_type)
        """
        # Build toast XML (Windows 10+ adaptive toast format)
        toast_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<toast>
    <visual>
        <binding template="ToastGeneric">
            <text>{self._escape_xml(payload.title)}</text>
            <text>{self._escape_xml(payload.body)}</text>
        </binding>
    </visual>
    <actions>
        <action content="View" arguments="action=view" />
        <action content="Dismiss" arguments="action=dismiss" />
    </actions>
</toast>"""

        return toast_xml, "text/xml"

    def _build_tile_notification(
        self, payload: PushNotificationPayload
    ) -> tuple[str, str]:
        """Build WNS tile notification XML.

        Args:
            payload: Notification payload

        Returns:
            Tuple of (tile_xml, content_type)
        """
        # Build tile XML (adaptive tile format)
        tile_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<tile>
    <visual>
        <binding template="TileMedium">
            <text hint-style="caption">{self._escape_xml(payload.title)}</text>
            <text hint-style="captionSubtle">{self._escape_xml(payload.body)}</text>
        </binding>
    </visual>
</tile>"""

        return tile_xml, "text/xml"

    def _build_badge_notification(
        self, payload: PushNotificationPayload
    ) -> tuple[str, str]:
        """Build WNS badge notification XML.

        Args:
            payload: Notification payload

        Returns:
            Tuple of (badge_xml, content_type)
        """
        # Get badge value from data (default to 1)
        badge_value = payload.data.get("badge_value", 1)

        badge_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<badge value="{badge_value}"/>"""

        return badge_xml, "text/xml"

    def _build_raw_notification(
        self, payload: PushNotificationPayload
    ) -> tuple[str, str]:
        """Build WNS raw notification (JSON payload for background tasks).

        Args:
            payload: Notification payload

        Returns:
            Tuple of (raw_json, content_type)
        """
        # Build raw notification payload (JSON format)
        raw_payload = {
            "title": payload.title,
            "body": payload.body,
            "data": payload.data,
            "priority": payload.priority.value,
            "timestamp": payload.created_at.isoformat(),
        }

        return json.dumps(raw_payload), "application/octet-stream"

    def _escape_xml(self, text: str) -> str:
        """Escape XML special characters.

        Args:
            text: Text to escape

        Returns:
            XML-escaped text
        """
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    async def _send_wns_request(
        self,
        channel_uri: str,
        notification_content: str,
        content_type: str,
        payload: PushNotificationPayload,
    ) -> Dict[str, Any]:
        """Send a request to the WNS API.

        Args:
            channel_uri: WNS channel URI
            notification_content: Notification content (XML or JSON)
            content_type: Content type header
            payload: Original payload for metadata

        Returns:
            Response dictionary with success status and details
        """
        await self._ensure_valid_token()

        # Build WNS headers
        headers = {
            "Authorization": f"{self._token_type} {self._access_token}",
            "Content-Type": content_type,
            self.WNS_TYPE_HEADER: f"wns/{self.notification_type}",
            self.WNS_TTL_HEADER: str(payload.ttl_seconds),
        }

        # Add cache policy
        headers[self.WNS_CACHE_POLICY_HEADER] = self.cache_policy

        # Add collapse key as tag if provided
        if payload.collapse_key:
            headers[self.WNS_TAG_HEADER] = payload.collapse_key[:16]  # Max 16 chars

        try:
            if self._session is None:
                raise RuntimeError("HTTP session not initialized")

            async with self._session.post(
                channel_uri, data=notification_content, headers=headers
            ) as response:
                # Get WNS-specific headers
                wns_status = response.headers.get(self.WNS_REQUEST_STATUS_HEADER)
                device_status = response.headers.get(self.WNS_DEVICE_CONNECTION_STATUS)
                error_desc = response.headers.get(self.WNS_ERROR_DESCRIPTION)
                msg_id = response.headers.get(self.WNS_MSG_ID)

                # Check response status
                if response.status == 200:
                    return {
                        "success": True,
                        "message_id": msg_id,
                        "wns_status": wns_status,
                        "device_status": device_status,
                    }
                else:
                    error_code, error_message, retry_after = self._parse_wns_error(
                        response.status, wns_status, error_desc, response.headers
                    )

                    return {
                        "success": False,
                        "error_code": error_code,
                        "error_message": error_message,
                        "retry_after": retry_after,
                        "wns_status": wns_status,
                        "device_status": device_status,
                    }

        except aiohttp.ClientError as e:
            raise NetworkError(f"WNS network error: {e}", self.platform_name)

    async def _send_batch(
        self, batch: List[tuple[str, PushNotificationPayload]]
    ) -> List[PushNotificationResult]:
        """Send a batch of notifications concurrently.

        Args:
            batch: List of (channel_uri, payload) tuples

        Returns:
            List of results for each notification in the batch
        """
        tasks = [
            self.send_notification(channel_uri, payload)
            for channel_uri, payload in batch
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to failed results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                channel_uri = batch[i][0]
                processed_results.append(
                    PushNotificationResult(
                        success=False,
                        message=f"Batch error: {str(result)}",
                        platform=self.platform_name,
                        device_token=channel_uri,
                        error_code="BATCH_ERROR",
                    )
                )
            else:
                assert isinstance(result, PushNotificationResult)
                processed_results.append(result)

        return processed_results

    def _parse_wns_error(
        self,
        status_code: int,
        wns_status: Optional[str],
        error_desc: Optional[str],
        headers: Any,
    ) -> tuple[str, str, Optional[int]]:
        """Parse WNS error response.

        Args:
            status_code: HTTP status code
            wns_status: X-WNS-Status header value
            error_desc: X-WNS-Error-Description header value
            headers: Full response headers

        Returns:
            Tuple of (error_code, error_message, retry_after_seconds)
        """
        retry_after = None
        error_message = error_desc or f"HTTP {status_code} error"

        # Parse Retry-After header if present
        if "Retry-After" in headers:
            try:
                retry_after = int(headers["Retry-After"])
            except (ValueError, TypeError):
                pass

        # Map HTTP status codes to error codes
        if status_code == 400:
            return "INVALID_REQUEST", "Invalid notification request", retry_after
        elif status_code == 401:
            return "UNAUTHORIZED", "Authentication failed or token expired", retry_after
        elif status_code == 403:
            return "FORBIDDEN", "Forbidden - check package SID", retry_after
        elif status_code == 404:
            return (
                "CHANNEL_EXPIRED",
                "Channel URI expired or invalid",
                retry_after,
            )
        elif status_code == 405:
            return "METHOD_NOT_ALLOWED", "HTTP method not allowed", retry_after
        elif status_code == 406:
            return "THROTTLED", "Notification throttled by WNS", retry_after
        elif status_code == 410:
            return (
                "CHANNEL_GONE",
                "Channel no longer valid - device unregistered",
                retry_after,
            )
        elif status_code == 413:
            return (
                "PAYLOAD_TOO_LARGE",
                "Notification payload exceeds size limit",
                retry_after,
            )
        elif status_code == 500:
            return "SERVER_ERROR", "WNS internal server error", retry_after
        elif status_code == 503:
            return "SERVICE_UNAVAILABLE", "WNS service unavailable", retry_after

        # Check WNS-specific status
        if wns_status:
            if wns_status == "dropped":
                return "DROPPED", "Notification dropped by WNS", retry_after
            elif wns_status == "channelthrottled":
                return "CHANNEL_THROTTLED", "Channel is throttled", retry_after

        return f"HTTP_{status_code}", error_message, retry_after
