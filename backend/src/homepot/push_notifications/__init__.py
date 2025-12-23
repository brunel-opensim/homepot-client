"""Push Notification System for HOMEPOT Client.

This module provides a plugin-based push notification system that supports
multiple platforms including FCM (Linux/Android), APNs (macOS/iOS),
WNS (Windows), and Web Push (browsers).

The system is designed to be:
- Platform-agnostic: Each platform has its own implementation
- Extensible: Easy to add new platforms
- Collaborative: Clear separation allows independent development
- Fallback-ready: Graceful degradation when platforms are unavailable

Example usage:
    from homepot.push_notifications import get_push_provider

    # Get FCM provider for Linux devices
    fcm_provider = get_push_provider("fcm_linux")

    # Send notification
    success = await fcm_provider.send_notification(
        device_token="fcm_token_here",
        payload={
            "title": "Configuration Update",
            "body": "New payment gateway settings available",
            "data": {
                "config_url": "https://config.example.com/v2.1.0.json",
                "priority": "high"
            }
        }
    )
"""

from typing import Dict

from .base import PushNotificationPayload, PushNotificationProvider
from .factory import get_available_platforms, get_push_provider

__version__ = "1.0.0"
__author__ = "HOMEPOT Consortium"

# Export main interfaces
__all__ = [
    "PushNotificationProvider",
    "PushNotificationPayload",
    "get_push_provider",
    "get_available_platforms",
]

# Platform availability status
PLATFORM_STATUS: Dict[str, bool] = {}


def check_platform_availability() -> Dict[str, bool]:
    """Check which push notification platforms are available.

    Returns:
        Dictionary mapping platform names to availability status
    """
    global PLATFORM_STATUS

    platforms = {
        "fcm_linux": False,
        "apns_apple": False,  # APNs for iOS/macOS devices
        "wns_windows": False,
        "web_push": False,
        "fcm_android": False,
        "unified_push": False,
        "simulation": True,  # Always available for testing
    }

    # Check FCM Linux
    try:
        from .fcm_linux import FCMLinuxProvider  # noqa: F401

        platforms["fcm_linux"] = True
    except ImportError:
        pass

    # Check APNs Apple (iOS/macOS)
    try:
        from .apns_apple import APNsProvider  # noqa: F401

        platforms["apns_apple"] = True
    except ImportError:
        pass

    # Check WNS Windows
    try:
        from .wns_windows import WNSWindowsProvider  # noqa: F401

        platforms["wns_windows"] = True
    except ImportError:
        pass

    # Check Web Push (when implemented)
    try:
        from .web_push import WebPushProvider  # noqa: F401

        platforms["web_push"] = True
    except ImportError:
        pass

    # Check FCM Android (when implemented)
    # try:
    #     from .fcm_android import FCMAndroidProvider  # noqa: F401
    #
    #     platforms["fcm_android"] = True
    # except ImportError:
    #     pass

    # Check UnifiedPush (when implemented)
    # try:
    #     from .unified_push import UnifiedPushProvider  # noqa: F401
    #
    #     platforms["unified_push"] = True
    # except ImportError:
    #     pass

    PLATFORM_STATUS = platforms
    return platforms


def get_platform_status() -> Dict[str, bool]:
    """Get cached platform availability status.

    Returns:
        Dictionary mapping platform names to availability status
    """
    if not PLATFORM_STATUS:
        return check_platform_availability()
    return PLATFORM_STATUS


# Initialize platform status on import
check_platform_availability()
