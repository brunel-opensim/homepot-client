"""Tests for the backend command wake-up."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homepot.push_notifications.wakeup import send_command_wakeup


def _device(push_channel=None, push_token=None):
    return SimpleNamespace(
        device_id="device-test-001",
        push_channel=push_channel,
        push_token=push_token,
    )


def test_no_push_channel_is_noop():
    """Devices without a push channel get no wake-up (polling covers it)."""
    result = __import__("asyncio").run(send_command_wakeup(_device()))
    assert result is None


def test_channel_without_token_is_noop():
    """A channel without a registered token is a no-op."""
    result = __import__("asyncio").run(send_command_wakeup(_device(push_channel="fcm")))
    assert result is None


@patch(
    "homepot.push_notifications.wakeup.get_fallback_provider", new_callable=AsyncMock
)
async def test_wakeup_sent_to_provider(fallback_provider):
    """A fcm device receives a silent command_wakeup payload."""
    provider = AsyncMock()
    provider.platform_name = "simulation"
    provider.send_notification.return_value = SimpleNamespace(success=True)
    fallback_provider.return_value = provider

    result = await send_command_wakeup(_device(push_channel="fcm", push_token="tok-1"))

    assert result is not None
    assert result.success is True
    payload = provider.send_notification.await_args.args[1]
    assert payload.data["type"] == "command_wakeup"
    assert payload.data["device_id"] == "device-test-001"
    assert provider.send_notification.await_args.args[0] == "tok-1"


@patch(
    "homepot.push_notifications.wakeup.get_fallback_provider", new_callable=AsyncMock
)
async def test_no_configured_provider_is_noop(fallback_provider):
    """When no provider is configured the wake-up is skipped."""
    fallback_provider.return_value = None
    result = await send_command_wakeup(_device(push_channel="apns", push_token="t"))
    assert result is None


@patch(
    "homepot.push_notifications.wakeup.get_fallback_provider", new_callable=AsyncMock
)
async def test_provider_failure_is_best_effort(fallback_provider):
    """A provider error never raises — the command stays queued regardless."""
    provider = AsyncMock()
    provider.platform_name = "wns"
    provider.send_notification.side_effect = RuntimeError("provider down")
    fallback_provider.return_value = provider

    result = await send_command_wakeup(_device(push_channel="wns", push_token="t"))
    assert result is None
