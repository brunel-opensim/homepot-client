"""Base classes and interfaces for push notification providers.

This module defines the abstract base classes that all platform-specific
push notification providers must implement. This ensures consistent
interfaces across all platforms while allowing platform-specific
optimizations.

The base classes provide:
- Standardized notification payload structure
- Common authentication patterns
- Error handling and retry mechanisms
- Logging and monitoring hooks
- Configuration management
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PushPriority(str, Enum):
    """Push notification priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class PushStatus(str, Enum):
    """Push notification delivery status."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    EXPIRED = "expired"
    RETRYING = "retrying"


@dataclass
class PushNotificationPayload:
    """Standardized push notification payload structure.

    This class provides a platform-agnostic way to define push notifications
    that can be adapted to each platform's specific requirements.
    """

    # Core notification content
    title: str
    body: str

    # Platform-agnostic data
    data: Dict[str, Any] = field(default_factory=dict)

    # Delivery settings
    priority: PushPriority = PushPriority.NORMAL
    ttl_seconds: int = 300  # Time to live
    collapse_key: Optional[str] = None  # For message grouping

    # Targeting
    device_tokens: List[str] = field(default_factory=list)
    topic: Optional[str] = None  # For topic-based messaging

    # Platform-specific data
    platform_data: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = field(default=None)

    def __post_init__(self) -> None:
        """Set expiration time based on TTL."""
        if self.expires_at is None:
            self.expires_at = self.created_at + timedelta(seconds=self.ttl_seconds)

    def is_expired(self) -> bool:
        """Check if the notification has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "body": self.body,
            "data": self.data,
            "priority": self.priority.value,
            "ttl_seconds": self.ttl_seconds,
            "collapse_key": self.collapse_key,
            "device_tokens": self.device_tokens,
            "topic": self.topic,
            "platform_data": self.platform_data,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass
class PushNotificationResult:
    """Result of a push notification attempt."""

    success: bool
    message: str
    platform: str
    device_token: Optional[str] = None
    message_id: Optional[str] = None
    error_code: Optional[str] = None
    retry_after: Optional[int] = None  # Seconds to wait before retry
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "success": self.success,
            "message": self.message,
            "platform": self.platform,
            "device_token": self.device_token,
            "message_id": self.message_id,
            "error_code": self.error_code,
            "retry_after": self.retry_after,
            "timestamp": self.timestamp.isoformat(),
        }


class PushNotificationProvider(ABC):
    """Abstract base class for all push notification providers.

    Each platform-specific provider (FCM, APNs, WNS, etc.) must implement
    this interface to ensure consistent behavior across platforms.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the push notification provider.

        Args:
            config: Platform-specific configuration dictionary
        """
        self.config = config
        self.platform_name = self.__class__.__name__.lower()
        self.logger = logging.getLogger(f"{__name__}.{self.platform_name}")
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the provider (authenticate, setup connections, etc.).

        Returns:
            True if initialization successful, False otherwise
        """
        pass

    @abstractmethod
    async def send_notification(
        self, device_token: str, payload: PushNotificationPayload
    ) -> PushNotificationResult:
        """Send a push notification to a single device.

        Args:
            device_token: Platform-specific device token
            payload: Notification payload

        Returns:
            Result of the push notification attempt
        """
        pass

    @abstractmethod
    async def send_bulk_notifications(
        self, notifications: List[tuple[str, PushNotificationPayload]]
    ) -> List[PushNotificationResult]:
        """Send push notifications to multiple devices efficiently.

        Args:
            notifications: List of (device_token, payload) tuples

        Returns:
            List of results for each notification attempt
        """
        pass

    @abstractmethod
    async def send_topic_notification(
        self, topic: str, payload: PushNotificationPayload
    ) -> PushNotificationResult:
        """Send a push notification to a topic (if supported).

        Args:
            topic: Topic name
            payload: Notification payload

        Returns:
            Result of the push notification attempt
        """
        pass

    @abstractmethod
    def validate_device_token(self, token: str) -> bool:
        """Validate a device token format for this platform.

        Args:
            token: Device token to validate

        Returns:
            True if token format is valid, False otherwise
        """
        pass

    @abstractmethod
    async def get_platform_info(self) -> Dict[str, Any]:
        """Get platform-specific information and status.

        Returns:
            Dictionary containing platform information
        """
        pass

    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the provider.

        Returns:
            Health check results
        """
        try:
            if not self._initialized:
                await self.initialize()

            platform_info = await self.get_platform_info()

            return {
                "status": "healthy",
                "platform": self.platform_name,
                "initialized": self._initialized,
                "platform_info": platform_info,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            self.logger.error(f"Health check failed for {self.platform_name}: {e}")
            return {
                "status": "unhealthy",
                "platform": self.platform_name,
                "initialized": self._initialized,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def cleanup(self) -> None:
        """Clean up resources when shutting down the provider."""
        self.logger.info(f"Cleaning up {self.platform_name} provider")
        self._initialized = False


class RetryStrategy(ABC):
    """Abstract base class for retry strategies."""

    @abstractmethod
    def should_retry(self, attempt: int, error: Exception) -> bool:
        """Determine if an operation should be retried.

        Args:
            attempt: Current attempt number (1-based)
            error: The exception that occurred

        Returns:
            True if should retry, False otherwise
        """
        pass

    @abstractmethod
    def get_delay(self, attempt: int) -> float:
        """Get delay in seconds before next retry.

        Args:
            attempt: Current attempt number (1-based)

        Returns:
            Delay in seconds
        """
        pass


class ExponentialBackoffRetry(RetryStrategy):
    """Exponential backoff retry strategy."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
    ):
        """Initialize exponential backoff retry strategy.

        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            backoff_factor: Backoff multiplication factor
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor

    def should_retry(self, attempt: int, error: Exception) -> bool:
        """Check if should retry based on attempt count."""
        return attempt < self.max_attempts

    def get_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        delay = self.base_delay * (self.backoff_factor ** (attempt - 1))
        return min(delay, self.max_delay)


class PushNotificationError(Exception):
    """Base exception for push notification errors."""

    def __init__(self, message: str, platform: str, error_code: Optional[str] = None):
        """Initialize push notification error.

        Args:
            message: Error message
            platform: Platform name where error occurred
            error_code: Optional error code
        """
        super().__init__(message)
        self.platform = platform
        self.error_code = error_code


class AuthenticationError(PushNotificationError):
    """Authentication/authorization error."""

    pass


class InvalidTokenError(PushNotificationError):
    """Invalid device token error."""

    pass


class QuotaExceededError(PushNotificationError):
    """API quota exceeded error."""

    pass


class NetworkError(PushNotificationError):
    """Network connectivity error."""

    pass


class PayloadTooLargeError(PushNotificationError):
    """Payload size exceeds platform limits."""

    pass
