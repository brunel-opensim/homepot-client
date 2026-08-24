"""Tests for the backend command wake-up."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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


@patch("homepot.push_notifications.wakeup._record_wakeup_log")
def test_channel_without_token_is_noop(record):
    """A channel without a registered token is a no-op."""
    result = __import__("asyncio").run(send_command_wakeup(_device(push_channel="fcm")))
    assert result is None
    record.assert_not_called()


@patch(
    "homepot.push_notifications.wakeup.get_fallback_provider", new_callable=AsyncMock
)
@patch("homepot.push_notifications.wakeup._record_wakeup_log")
async def test_wakeup_persisted_and_sent_to_provider(record, fallback_provider):
    """A fcm device gets a persisted wake-up plus a silent provider push."""
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
    record.assert_called_once()
    assert record.call_args.args[1].data["type"] == "command_wakeup"


@patch(
    "homepot.push_notifications.wakeup.get_fallback_provider", new_callable=AsyncMock
)
@patch("homepot.push_notifications.wakeup._record_wakeup_log")
async def test_no_configured_provider_still_persists(record, fallback_provider):
    """Without a real provider the wake-up is persisted for polling agents."""
    fallback_provider.return_value = None
    result = await send_command_wakeup(_device(push_channel="apns", push_token="t"))
    assert result is None
    record.assert_called_once()


@patch(
    "homepot.push_notifications.wakeup.get_fallback_provider", new_callable=AsyncMock
)
@patch("homepot.push_notifications.wakeup._record_wakeup_log")
async def test_provider_failure_is_best_effort(record, fallback_provider):
    """A provider error never raises — the command stays queued regardless."""
    provider = AsyncMock()
    provider.platform_name = "wns"
    provider.send_notification.side_effect = RuntimeError("provider down")
    fallback_provider.return_value = provider

    result = await send_command_wakeup(_device(push_channel="wns", push_token="t"))
    assert result is None
    record.assert_called_once()


@patch("homepot.database.SessionLocal")
def test_record_wakeup_log_persists_row(session_local):
    """The wake-up is written as a sent PushNotificationLog row."""
    from homepot.push_notifications.wakeup import _record_wakeup_log

    session = MagicMock()
    session_local.return_value = session

    _record_wakeup_log(
        _device(push_channel="fcm", push_token="tok"),
        SimpleNamespace(to_dict=lambda: {"type": "command_wakeup"}),
    )

    session.add.assert_called_once()
    log = session.add.call_args.args[0]
    assert log.device_id == "device-test-001"
    assert log.provider == "command_wakeup"
    assert log.status == "sent"
    assert log.payload == {"type": "command_wakeup"}
    session.commit.assert_called_once()
