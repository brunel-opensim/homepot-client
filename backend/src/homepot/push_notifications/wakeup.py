"""Backend-side command wake-up.

After a command is queued, the backend sends a minimal **silent** push so the
device polls its pending-command queue immediately instead of waiting for the
next poll interval. The authoritative command stays in the pending-command
queue; the push only carries a reference (``type: command_wakeup``) per the
"push as wake-up, pull as payload" pattern.

Devices without a push channel/token (or without a configured provider) get no
wake-up — plain HTTP polling covers delivery.
"""

import logging
from typing import Any, Optional

from homepot.push_notifications.base import (
    PushNotificationPayload,
    PushNotificationResult,
    PushPriority,
)
from homepot.push_notifications.factory import get_fallback_provider

logger = logging.getLogger(__name__)

# Map the stored Device.push_channel to candidate provider platforms, in
# preference order. Real providers require platform credentials; when none is
# configured the wake-up is still persisted (see _record_wakeup_log) so
# polling agents / emulators can pick it up.
_CHANNEL_PROVIDERS = {
    "fcm": ["fcm_android", "fcm_linux"],
    "wns": ["wns_windows"],
    "apns": ["apns"],
}

_WAKEUP_TTL_SECONDS = 300


def _record_wakeup_log(device: Any, payload: PushNotificationPayload) -> None:
    """Persist the wake-up so polling agents/emulators read it from /push/pending.

    This is the simulated delivery path: a push-capable device without a real
    push provider (e.g. an Android emulator) picks the wake-up up from the
    pending-push queue and reacts by polling pending commands immediately.
    """
    try:
        from datetime import datetime, timezone
        import uuid

        from homepot.app.models.AnalyticsModel import PushNotificationLog
        from homepot.database import SessionLocal

        db = SessionLocal()
        try:
            db.add(
                PushNotificationLog(
                    message_id=str(uuid.uuid4()),
                    device_id=getattr(device, "device_id", ""),
                    provider="command_wakeup",
                    payload=payload.to_dict(),
                    sent_at=datetime.now(timezone.utc),
                    status="sent",
                )
            )
            db.commit()
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 - best-effort wake-up
        logger.warning("Failed to persist command wake-up log: %s", exc)


async def send_command_wakeup(device: Any) -> Optional[PushNotificationResult]:
    """Send a minimal silent wake-up for a newly queued command.

    Parameters
    ----------
    device:
        The target ``Device`` (must expose ``device_id``, ``push_channel`` and
        ``push_token``).

    Returns
    -------
    The provider result when a wake-up was attempted, or ``None`` when the
    device has no push channel/token or no provider is configured. Never
    raises — wake-up failures are best-effort and must not fail the queue.
    """
    channel = getattr(device, "push_channel", None)
    token = getattr(device, "push_token", None)
    if not channel or not token:
        return None

    payload = PushNotificationPayload(
        title="",
        body="",
        data={
            "type": "command_wakeup",
            "device_id": getattr(device, "device_id", ""),
        },
        priority=PushPriority.HIGH,
        ttl_seconds=_WAKEUP_TTL_SECONDS,
        collapse_key="command",
    )

    # Simulated delivery: persist so polling agents / emulators pick it up from
    # /push/pending even when no real push provider is configured.
    _record_wakeup_log(device, payload)

    providers = _CHANNEL_PROVIDERS.get(channel)
    if not providers:
        return None
    try:
        provider = await get_fallback_provider(providers)
    except Exception as exc:  # noqa: BLE001 - best-effort wake-up
        logger.warning("No push provider for channel=%s wake-up: %s", channel, exc)
        return None
    if provider is None:
        return None

    try:
        result = await provider.send_notification(token, payload)
        logger.info(
            "Command wake-up sent via %s (success=%s)",
            provider.platform_name,
            result.success,
        )
        return result
    except Exception as exc:  # noqa: BLE001 - best-effort wake-up
        logger.warning("Command wake-up send failed: %s", exc)
        return None
