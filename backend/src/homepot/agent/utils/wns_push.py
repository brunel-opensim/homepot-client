"""WNS push channel management for the HOMEPOT agent on Windows.

Provides channel URI creation, periodic refresh, and backend registration
so the backend can push notifications to the agent via WNS raw notifications.
"""

import asyncio
import logging
import sys
from typing import Optional

from homepot.agent.credential_storage import CredentialStorage

logger = logging.getLogger(__name__)

# How often to refresh the channel URI (WNS channels expire ~30 days).
REFRESH_INTERVAL_SECONDS = 86400 * 25  # 25 days


def _get_channel_uri_powershell() -> Optional[str]:
    """Obtain a WNS channel URI via PowerShell.

    Uses the WinRT ``PushNotificationChannelManager`` API through PowerShell.
    Returns ``None`` if the call fails or WNS is unavailable.
    """
    import subprocess  # noqa: S404

    ps_script = (
        "[Windows.Networking.PushNotifications."
        "PushNotificationChannelManager,"
        "Windows.Networking.PushNotifications,"
        "ContentType=WindowsRuntime]::"
        "CreatePushNotificationChannelForApplicationAsync()"
        ".GetAwaiter().GetResult() | "
        "ForEach-Object { $_.Uri }"
    )
    try:
        result = subprocess.run(  # noqa: S603, S607
            ["powershell", "-NoProfile", "-Command", ps_script],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            uri = result.stdout.strip()
            if uri:
                logger.info("Obtained WNS channel URI via PowerShell")
                return uri
        logger.debug("PowerShell WNS channel failed: %s", result.stderr.strip())
    except FileNotFoundError:
        logger.debug("PowerShell not available (not Windows)")
    except subprocess.TimeoutExpired:
        logger.warning("PowerShell WNS channel timed out")
    except Exception as exc:
        logger.warning("Failed to get WNS channel via PowerShell: %s", exc)
    return None


def _get_channel_uri_winrt() -> Optional[str]:
    """Obtain a WNS channel URI via the ``winrt`` Python package.

    Requires ``winrt-Windows.Networking.PushNotifications`` to be installed.
    Returns ``None`` if the package is not available or the call fails.
    """
    try:
        from winrt.windows.networking.pushnotifications import (  # type: ignore[import-not-found]
            PushNotificationChannelManager,
        )

        channel = (
            PushNotificationChannelManager.create_push_notification_channel_for_application_async().get()
        )
        uri: str = channel.uri
        logger.info("Obtained WNS channel URI via winrt")
        return uri
    except ImportError:
        logger.debug("winrt not installed; cannot get WNS channel")
    except Exception as exc:
        logger.warning("Failed to get WNS channel via winrt: %s", exc)
    return None


def get_wns_channel_uri() -> Optional[str]:
    """Return a WNS channel URI for this device.

    Tries ``winrt`` first (Pythonic), falls back to PowerShell.
    Returns ``None`` on non-Windows or if both methods fail.
    """
    if sys.platform != "win32":
        logger.debug("WNS channels are only available on Windows")
        return None

    uri = _get_channel_uri_winrt()
    if uri:
        return uri

    uri = _get_channel_uri_powershell()
    return uri


class WNSPushChannelManager:
    """Manages the WNS push channel URI lifecycle.

    Usage::

        mgr = WNSPushChannelManager(cred)
        uri = mgr.get_or_create_channel()
        mgr.start_background_refresh()
    """

    def __init__(self, cred: CredentialStorage) -> None:
        """Initialise the manager with credential storage for channel persistence."""
        self._cred = cred
        self._refresh_task: Optional[asyncio.Task] = None

    def get_or_create_channel(self) -> Optional[str]:
        """Return a stored channel URI or create a new one.

        Prefers a previously stored URI; if missing or expired,
        requests a fresh one from Windows.
        """
        stored = self._cred.get_metadata("wns_channel_uri")
        if stored:
            logger.debug("Using stored WNS channel URI")
            return stored

        uri = get_wns_channel_uri()
        if uri:
            self._store_channel(uri)
        return uri

    def _store_channel(self, uri: str) -> None:
        """Persist the channel URI in credential storage."""
        self._cred.save({"wns_channel_uri": uri})

    def start_background_refresh(self) -> None:
        """Start a background task that periodically refreshes the channel URI."""
        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(self._refresh_loop())

    async def stop_background_refresh(self) -> None:
        """Cancel the background refresh task."""
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

    async def _refresh_loop(self) -> None:
        """Periodically refresh the WNS channel URI."""
        while True:
            await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
            try:
                uri = get_wns_channel_uri()
                if uri:
                    self._store_channel(uri)
                    logger.info("WNS channel URI refreshed")
            except Exception as exc:
                logger.warning("WNS channel refresh failed: %s", exc)

    def get_stored_uri(self) -> Optional[str]:
        """Return the currently stored channel URI without I/O."""
        return self._cred.get_metadata("wns_channel_uri")

    def clear_channel(self) -> None:
        """Remove the stored channel URI (e.g. on unpair)."""
        self._cred.save({"wns_channel_uri": ""})
