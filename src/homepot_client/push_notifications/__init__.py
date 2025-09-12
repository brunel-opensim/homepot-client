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
    from homepot_client.push_notifications import get_push_provider
    
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

from typing import Dict, Optional

from .base import PushNotificationProvider, PushNotificationPayload
from .factory import get_push_provider, get_available_platforms

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
        "apns_macos": False,
        "wns_windows": False,
        "web_push": False,
        "fcm_android": False,
        "unified_push": False,
        "simulation": True,  # Always available for testing
    }
    
    # Check FCM Linux
    try:
        from .fcm_linux import FCMLinuxProvider
        platforms["fcm_linux"] = True
    except ImportError:
        pass
    
    # Check APNs macOS (when implemented)
    try:
        from .apns_macos import APNsMacOSProvider
        platforms["apns_macos"] = True
    except ImportError:
        pass
    
    # Check WNS Windows (when implemented)
    try:
        from .wns_windows import WNSWindowsProvider
        platforms["wns_windows"] = True
    except ImportError:
        pass
    
    # Check Web Push (when implemented)
    try:
        from .web_push import WebPushProvider
        platforms["web_push"] = True
    except ImportError:
        pass
    
    # Check FCM Android (when implemented)
    try:
        from .fcm_android import FCMAndroidProvider
        platforms["fcm_android"] = True
    except ImportError:
        pass
    
    # Check UnifiedPush (when implemented)
    try:
        from .unified_push import UnifiedPushProvider
        platforms["unified_push"] = True
    except ImportError:
        pass
        
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
