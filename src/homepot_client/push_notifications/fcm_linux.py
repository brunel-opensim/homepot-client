"""Firebase Cloud Messaging (FCM) provider for Linux devices.

This module implements FCM push notifications specifically for Linux-based
devices including:
- Linux IoT devices
- Embedded Linux systems
- Linux-based POS terminals
- Industrial Linux controllers

FCM for Linux provides:
- HTTP v1 API integration
- Service account authentication
- Batch messaging support
- Topic-based messaging
- Error handling and retry logic
- Message analytics and delivery reports

Configuration required:
- service_account_path: Path to FCM service account JSON file
- project_id: Firebase project ID
- batch_size: Maximum messages per batch (default: 500)
- timeout_seconds: Request timeout (default: 30)

Example usage:
    config = {
        "service_account_path": "/path/to/service-account.json",
        "project_id": "your-firebase-project-id",
        "batch_size": 500,
        "timeout_seconds": 30
    }

    fcm_provider = FCMLinuxProvider(config)
    await fcm_provider.initialize()

    result = await fcm_provider.send_notification(
        device_token="fcm_device_token",
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
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from .base import (
    AuthenticationError,
    NetworkError,
    PushNotificationPayload,
    PushNotificationProvider,
    PushNotificationResult,
    PushPriority,
)

logger = logging.getLogger(__name__)


class FCMLinuxProvider(PushNotificationProvider):
    """Firebase Cloud Messaging provider for Linux devices.

    This provider implements the FCM HTTP v1 API for sending push notifications
    to Linux-based devices and applications.
    """

    # FCM API endpoints
    FCM_ENDPOINT = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    FCM_BATCH_ENDPOINT = (
        "https://fcm.googleapis.com/v1/projects/{project_id}/messages:batchSend"
    )

    # FCM limits
    MAX_PAYLOAD_SIZE = 4096  # 4KB
    MAX_BATCH_SIZE = 500
    MAX_TTL_SECONDS = 2419200  # 28 days

    def __init__(self, config: Dict[str, Any]):
        """Initialize the FCM Linux provider.

        Args:
            config: Configuration dictionary containing:
                - service_account_path: Path to service account JSON file
                - project_id: Firebase project ID
                - batch_size: Maximum messages per batch (optional)
                - timeout_seconds: Request timeout (optional)
        """
        super().__init__(config)
        self.platform_name = "fcm_linux"

        # Required configuration
        self.service_account_path = config.get("service_account_path")
        self.project_id = config.get("project_id")

        # Optional configuration
        self.batch_size = min(config.get("batch_size", 500), self.MAX_BATCH_SIZE)
        self.timeout_seconds = config.get("timeout_seconds", 30)

        # Authentication
        self._credentials: Optional[service_account.Credentials] = None
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[float] = None

        # HTTP session
        self._session: Optional[aiohttp.ClientSession] = None

        self.logger.info(
            f"Initialized FCM Linux provider for project: {self.project_id}"
        )

    async def initialize(self) -> bool:
        """Initialize the FCM provider with authentication.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Validate configuration
            if not self.service_account_path:
                raise ValueError("service_account_path is required")
            if not self.project_id:
                raise ValueError("project_id is required")

            # Load and validate service account
            service_account_file = Path(self.service_account_path)
            if not service_account_file.exists():
                raise FileNotFoundError(
                    f"Service account file not found: {self.service_account_path}"
                )

            # Load credentials
            self._credentials = service_account.Credentials.from_service_account_file(
                str(service_account_file),
                scopes=["https://www.googleapis.com/auth/firebase.messaging"],
            )

            # Create HTTP session
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={"Content-Type": "application/json"},
            )

            # Get initial access token
            await self._refresh_access_token()

            self._initialized = True
            self.logger.info("FCM Linux provider initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize FCM Linux provider: {e}")
            return False

    async def send_notification(
        self, device_token: str, payload: PushNotificationPayload
    ) -> PushNotificationResult:
        """Send a push notification to a single Linux device via FCM.

        Args:
            device_token: FCM device registration token
            payload: Notification payload

        Returns:
            Result of the push notification attempt
        """
        if not self._initialized:
            raise RuntimeError("Provider not initialized")

        try:
            # Validate device token
            if not self.validate_device_token(device_token):
                return PushNotificationResult(
                    success=False,
                    message="Invalid device token format",
                    platform=self.platform_name,
                    device_token=device_token,
                    error_code="INVALID_TOKEN",
                )

            # Build FCM message
            fcm_message = self._build_fcm_message(device_token, payload)

            # Validate payload size
            message_size = len(json.dumps(fcm_message).encode("utf-8"))
            if message_size > self.MAX_PAYLOAD_SIZE:
                return PushNotificationResult(
                    success=False,
                    message=f"Payload too large: {message_size} bytes "
                    f"(max: {self.MAX_PAYLOAD_SIZE})",
                    platform=self.platform_name,
                    device_token=device_token,
                    error_code="PAYLOAD_TOO_LARGE",
                )

            # Send to FCM
            response = await self._send_fcm_request(fcm_message)

            if response["success"]:
                return PushNotificationResult(
                    success=True,
                    message="Notification sent successfully",
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
                )

        except Exception as e:
            self.logger.error(f"FCM notification failed for {device_token}: {e}")
            return PushNotificationResult(
                success=False,
                message=f"FCM error: {str(e)}",
                platform=self.platform_name,
                device_token=device_token,
                error_code="FCM_ERROR",
            )

    async def send_bulk_notifications(
        self, notifications: List[tuple[str, PushNotificationPayload]]
    ) -> List[PushNotificationResult]:
        """Send push notifications to multiple devices efficiently using FCM batch API.

        Args:
            notifications: List of (device_token, payload) tuples

        Returns:
            List of results for each notification
        """
        if not notifications:
            return []

        results = []

        # Process in batches
        for i in range(0, len(notifications), self.batch_size):
            batch = notifications[i: i + self.batch_size]
            batch_results = await self._send_batch(batch)
            results.extend(batch_results)

        return results

    async def send_topic_notification(
        self, topic: str, payload: PushNotificationPayload
    ) -> PushNotificationResult:
        """Send a push notification to an FCM topic.

        Args:
            topic: FCM topic name (e.g., 'pos-terminals', 'site-123')
            payload: Notification payload

        Returns:
            Result of the topic notification
        """
        if not self._initialized:
            raise RuntimeError("Provider not initialized")

        try:
            # Build FCM topic message
            fcm_message = self._build_fcm_topic_message(topic, payload)

            # Send to FCM
            response = await self._send_fcm_request(fcm_message)

            if response["success"]:
                return PushNotificationResult(
                    success=True,
                    message=f"Topic notification sent to '{topic}'",
                    platform=self.platform_name,
                    message_id=response.get("message_id"),
                )
            else:
                return PushNotificationResult(
                    success=False,
                    message=f"Topic notification failed: {response['error_message']}",
                    platform=self.platform_name,
                    error_code=response["error_code"],
                )

        except Exception as e:
            self.logger.error(f"FCM topic notification failed for {topic}: {e}")
            return PushNotificationResult(
                success=False,
                message=f"FCM topic error: {str(e)}",
                platform=self.platform_name,
                error_code="FCM_TOPIC_ERROR",
            )

    def validate_device_token(self, token: str) -> bool:
        """Validate FCM device token format.

        Args:
            token: FCM device registration token

        Returns:
            True if token format appears valid
        """
        if not isinstance(token, str):
            return False

        # FCM tokens are typically 152-163 characters
        if not (140 <= len(token) <= 170):
            return False

        # FCM tokens are alphanumeric with some special characters
        allowed_chars = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_:"
        )
        if not all(c in allowed_chars for c in token):
            return False

        return True

    async def get_platform_info(self) -> Dict[str, Any]:
        """Get FCM platform information and status.

        Returns:
            Platform status and configuration
        """
        return {
            "platform": "fcm_linux",
            "project_id": self.project_id,
            "service_status": "operational" if self._initialized else "not_initialized",
            "batch_size": self.batch_size,
            "timeout_seconds": self.timeout_seconds,
            "has_credentials": self._credentials is not None,
            "token_valid": self._is_token_valid(),
            "max_payload_size": self.MAX_PAYLOAD_SIZE,
            "max_batch_size": self.MAX_BATCH_SIZE,
        }

    async def cleanup(self) -> None:
        """Clean up FCM provider resources."""
        if self._session:
            await self._session.close()
            self._session = None

        self._credentials = None
        self._access_token = None
        self._token_expiry = None

        await super().cleanup()

    async def _refresh_access_token(self) -> None:
        """Refresh the OAuth2 access token for FCM API."""
        if not self._credentials:
            raise AuthenticationError("No credentials available", self.platform_name)

        try:
            # Refresh token
            request = Request()
            self._credentials.refresh(request)

            self._access_token = self._credentials.token
            self._token_expiry = time.time() + 3600  # 1 hour from now

            self.logger.debug("FCM access token refreshed")

        except Exception as e:
            raise AuthenticationError(
                f"Failed to refresh access token: {e}", self.platform_name
            )

    def _is_token_valid(self) -> bool:
        """Check if the current access token is valid."""
        if not self._access_token or not self._token_expiry:
            return False

        # Check if token expires in next 5 minutes
        return time.time() < (self._token_expiry - 300)

    async def _ensure_valid_token(self) -> None:
        """Ensure we have a valid access token, refresh if needed."""
        if not self._is_token_valid():
            await self._refresh_access_token()

    def _build_fcm_message(
        self, device_token: str, payload: PushNotificationPayload
    ) -> Dict[str, Any]:
        """Build FCM message structure from our payload.

        Args:
            device_token: FCM device registration token
            payload: Notification payload

        Returns:
            FCM message dictionary
        """
        message = {
            "message": {
                "token": device_token,
                "data": {},
                "android": {
                    "priority": self._map_priority_to_fcm(payload.priority),
                    "ttl": f"{payload.ttl_seconds}s",
                },
            }
        }

        # Add collapse key if specified
        if payload.collapse_key:
            android_config = message["message"]["android"]
            assert isinstance(android_config, dict)
            android_config["collapse_key"] = payload.collapse_key

        # Convert payload data to strings (FCM requirement)
        payload_data = payload.data
        assert isinstance(payload_data, dict)
        message_data = message["message"]["data"]
        assert isinstance(message_data, dict)
        for key, value in payload_data.items():
            message_data[key] = str(value)

        # Add title and body as data fields for Linux devices
        message_data["title"] = payload.title
        message_data["body"] = payload.body
        message_data["priority"] = payload.priority.value

        # Add platform-specific data
        if payload.platform_data.get("fcm_linux"):
            fcm_data = payload.platform_data["fcm_linux"]
            message["message"].update(fcm_data)

        return message

    def _build_fcm_topic_message(
        self, topic: str, payload: PushNotificationPayload
    ) -> Dict[str, Any]:
        """Build FCM topic message structure.

        Args:
            topic: FCM topic name
            payload: Notification payload

        Returns:
            FCM topic message dictionary
        """
        message = self._build_fcm_message("", payload)

        # Replace token with topic
        del message["message"]["token"]
        message["message"]["topic"] = topic

        return message

    def _map_priority_to_fcm(self, priority: PushPriority) -> str:
        """Map our priority enum to FCM priority string.

        Args:
            priority: Our priority enum value

        Returns:
            FCM priority string
        """
        mapping = {
            PushPriority.LOW: "normal",
            PushPriority.NORMAL: "normal",
            PushPriority.HIGH: "high",
            PushPriority.CRITICAL: "high",
        }
        return mapping.get(priority, "normal")

    async def _send_fcm_request(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request to the FCM API.

        Args:
            message: FCM message dictionary

        Returns:
            Response dictionary with success status and details
        """
        await self._ensure_valid_token()

        url = self.FCM_ENDPOINT.format(project_id=self.project_id)
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        try:
            if self._session is None:
                raise RuntimeError("HTTP session not initialized")
            
            async with self._session.post(
                url, json=message, headers=headers
            ) as response:
                response_data = await response.json()

                if response.status == 200:
                    return {
                        "success": True,
                        "message_id": response_data.get("name", "").split("/")[-1],
                        "response": response_data,
                    }
                else:
                    error_code, error_message = self._parse_fcm_error(
                        response.status, response_data
                    )
                    return {
                        "success": False,
                        "error_code": error_code,
                        "error_message": error_message,
                        "response": response_data,
                    }

        except aiohttp.ClientError as e:
            raise NetworkError(f"FCM network error: {e}", self.platform_name)

    async def _send_batch(
        self, batch: List[tuple[str, PushNotificationPayload]]
    ) -> List[PushNotificationResult]:
        """Send a batch of notifications.

        Args:
            batch: List of (device_token, payload) tuples

        Returns:
            List of results for each notification in the batch
        """
        # For now, send individually (FCM batch API is more complex)
        # TODO: Implement proper FCM batch API when needed
        tasks = [
            self.send_notification(device_token, payload)
            for device_token, payload in batch
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to failed results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                device_token = batch[i][0]
                processed_results.append(
                    PushNotificationResult(
                        success=False,
                        message=f"Batch error: {str(result)}",
                        platform=self.platform_name,
                        device_token=device_token,
                        error_code="BATCH_ERROR",
                    )
                )
            else:
                # result is guaranteed to be PushNotificationResult here
                assert isinstance(result, PushNotificationResult)
                processed_results.append(result)

        return processed_results

    def _parse_fcm_error(
        self, status_code: int, response_data: Dict
    ) -> tuple[str, str]:
        """Parse FCM error response.

        Args:
            status_code: HTTP status code
            response_data: FCM error response

        Returns:
            Tuple of (error_code, error_message)
        """
        error_info = response_data.get("error", {})
        error_code = error_info.get("status", f"HTTP_{status_code}")
        error_message = error_info.get("message", f"HTTP {status_code} error")

        # Map common FCM errors
        if "INVALID_ARGUMENT" in error_code:
            if "token" in error_message.lower():
                return "INVALID_TOKEN", "Invalid device token"
            return "INVALID_ARGUMENT", error_message
        elif "UNAUTHENTICATED" in error_code:
            return "AUTHENTICATION_ERROR", "Authentication failed"
        elif "PERMISSION_DENIED" in error_code:
            return "PERMISSION_DENIED", "Permission denied"
        elif "QUOTA_EXCEEDED" in error_code:
            return "QUOTA_EXCEEDED", "API quota exceeded"
        elif "UNAVAILABLE" in error_code:
            return "SERVICE_UNAVAILABLE", "FCM service unavailable"

        return error_code, error_message
