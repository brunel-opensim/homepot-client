"""Factory for creating platform-specific push notification providers.

This module provides a centralized factory for creating push notification
providers based on platform names. It handles provider instantiation,
configuration, and provides fallback mechanisms.

The factory supports:
- Dynamic provider loading
- Configuration validation
- Platform availability checking
- Fallback provider selection
- Provider caching and reuse
"""

import logging
from typing import Dict, List, Optional, Type

from .base import PushNotificationProvider

logger = logging.getLogger(__name__)

# Registry of available providers
_PROVIDER_REGISTRY: Dict[str, Type[PushNotificationProvider]] = {}
_PROVIDER_INSTANCES: Dict[str, PushNotificationProvider] = {}


def register_provider(
    platform: str, provider_class: Type[PushNotificationProvider]
) -> None:
    """Register a push notification provider.

    Args:
        platform: Platform identifier (e.g., 'fcm_linux', 'apns_apple')
        provider_class: Provider class to register
    """
    _PROVIDER_REGISTRY[platform] = provider_class
    logger.info(f"Registered push notification provider: {platform}")


def get_available_platforms() -> List[str]:
    """Get list of available platform identifiers.

    Returns:
        List of platform names that have registered providers
    """
    return list(_PROVIDER_REGISTRY.keys())


def is_platform_available(platform: str) -> bool:
    """Check if a platform provider is available.

    Args:
        platform: Platform identifier to check

    Returns:
        True if platform is available, False otherwise
    """
    return platform in _PROVIDER_REGISTRY


async def get_push_provider(
    platform: str, config: Optional[Dict] = None, force_new: bool = False
) -> PushNotificationProvider:
    """Get a push notification provider for the specified platform.

    Args:
        platform: Platform identifier (e.g., 'fcm_linux', 'apns_apple')
        config: Platform-specific configuration dictionary
        force_new: If True, create a new instance instead of reusing cached one

    Returns:
        Initialized push notification provider

    Raises:
        ValueError: If platform is not available
        RuntimeError: If provider initialization fails
    """
    if platform not in _PROVIDER_REGISTRY:
        available = get_available_platforms()
        raise ValueError(
            f"Platform '{platform}' not available. " f"Available platforms: {available}"
        )

    # Check if we have a cached instance and don't need a new one
    if not force_new and platform in _PROVIDER_INSTANCES:
        return _PROVIDER_INSTANCES[platform]

    # Create new provider instance
    provider_class = _PROVIDER_REGISTRY[platform]
    config = config or {}

    try:
        provider = provider_class(config)

        # Initialize the provider
        success = await provider.initialize()
        if not success:
            raise RuntimeError(f"Failed to initialize {platform} provider")

        # Cache the provider instance
        _PROVIDER_INSTANCES[platform] = provider

        logger.info(f"Created and initialized {platform} provider")
        return provider

    except Exception as e:
        logger.error(f"Failed to create {platform} provider: {e}")
        raise RuntimeError(f"Failed to create {platform} provider: {e}")


async def get_fallback_provider(
    preferred_platforms: List[str], config: Optional[Dict] = None
) -> Optional[PushNotificationProvider]:
    """Get the first available provider from a list of preferred platforms.

    Args:
        preferred_platforms: List of platform names in order of preference
        config: Configuration dictionary (same config used for all platforms)

    Returns:
        First available and working provider, or None if none work
    """
    for platform in preferred_platforms:
        if not is_platform_available(platform):
            logger.debug(f"Platform {platform} not available, trying next...")
            continue

        try:
            provider = await get_push_provider(platform, config)
            logger.info(f"Using fallback provider: {platform}")
            return provider
        except Exception as e:
            logger.warning(f"Failed to initialize {platform} provider: {e}")
            continue

    logger.error(f"No working providers found from: {preferred_platforms}")
    return None


async def cleanup_all_providers() -> None:
    """Clean up all cached provider instances."""
    for platform, provider in _PROVIDER_INSTANCES.items():
        try:
            await provider.cleanup()
            logger.info(f"Cleaned up {platform} provider")
        except Exception as e:
            logger.error(f"Error cleaning up {platform} provider: {e}")

    _PROVIDER_INSTANCES.clear()
    logger.info("All push notification providers cleaned up")


def get_provider_status() -> Dict[str, Dict]:
    """Get status information for all providers.

    Returns:
        Dictionary mapping platform names to status information
    """
    status = {}

    for platform, provider_class in _PROVIDER_REGISTRY.items():
        is_instantiated = platform in _PROVIDER_INSTANCES

        status[platform] = {
            "available": True,
            "class": provider_class.__name__,
            "instantiated": is_instantiated,
        }

        if is_instantiated:
            provider = _PROVIDER_INSTANCES[platform]
            status[platform]["initialized"] = provider._initialized

    return status


# Auto-registration of providers when modules are imported
def _auto_register_providers() -> None:
    """Automatically register providers when their modules can be imported."""
    # Try to register FCM Linux
    try:
        from .fcm_linux import FCMLinuxProvider

        register_provider("fcm_linux", FCMLinuxProvider)
    except ImportError:
        logger.debug("FCM Linux provider not available")

    # Try to register APNs
    try:
        from .apns_apple import APNsProvider

        register_provider("apns", APNsProvider)
    except ImportError:
        logger.debug("APNs provider not available")

    # Try to register WNS Windows (when implemented)
    try:
        from .wns_windows import WNSWindowsProvider

        register_provider("wns_windows", WNSWindowsProvider)
    except ImportError:
        logger.debug("WNS Windows provider not available")

    # Try to register Web Push (when implemented)
    try:
        from .web_push import WebPushProvider

        register_provider("web_push", WebPushProvider)
    except ImportError:
        logger.debug("Web Push provider not available")

    # Try to register FCM Android (when implemented)
    try:
        from .fcm_android import FCMAndroidProvider

        register_provider("fcm_android", FCMAndroidProvider)
    except ImportError:
        logger.debug("FCM Android provider not available")

    # Try to register UnifiedPush (when implemented)
    try:
        from .unified_push import UnifiedPushProvider

        register_provider("unified_push", UnifiedPushProvider)
    except ImportError:
        logger.debug("UnifiedPush provider not available")

    # Always register simulation provider for testing
    try:
        from .simulation import SimulationProvider

        register_provider("simulation", SimulationProvider)
    except ImportError:
        logger.debug("Simulation provider not available")


# Initialize providers registry on module import
_auto_register_providers()
