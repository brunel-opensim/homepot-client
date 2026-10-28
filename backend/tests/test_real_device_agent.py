"""Transport-level tests for the real device agent HTTP calls."""

import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from homepot.agent import real_device_agent as rda
from homepot.agent.real_device_agent import post_json, update_command_status

CONFIG: Dict[str, Any] = {
    "device_id": "DEVICE-STATUS-1",
    "api_key": "test-api-key",
    "backend_url": "http://testserver",
}


@pytest.mark.parametrize(
    ("method", "expected"),
    [("POST", "POST"), ("put", "PUT"), ("get", "GET")],
)
def test_post_json_honours_explicit_method(method: str, expected: str) -> None:
    """``post_json`` sends the requested HTTP method verbatim."""
    recorded: List[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request.method)
        return httpx.Response(200, json={"ok": True})

    async def run() -> bool:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await post_json(
                client,
                f"{CONFIG['backend_url']}/api/v1/devices/DEVICE-STATUS-1/status",
                {"command_id": "cmd-1", "status": "failed"},
                {"X-Device-ID": CONFIG["device_id"], "X-API-Key": CONFIG["api_key"]},
                method=method,
            )

    assert asyncio.run(run()) is True
    assert recorded == [expected]


def test_update_command_status_uses_put_to_status_route() -> None:
    """Command status must be reported via ``PUT .../{command_id}/status``."""
    requests: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    async def run() -> bool:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await update_command_status(
                client,
                CONFIG,
                "cmd-refused-1",
                "failed",
                {"error": "not allowlisted"},
            )

    assert asyncio.run(run()) is True
    assert len(requests) == 1
    assert requests[0].method == "PUT"
    assert requests[0].url.path == "/api/v1/devices/cmd-refused-1/status"
    body = requests[0].read().decode()
    assert '"status":"failed"' in body
    assert "not allowlisted" in body


def test_post_json_defaults_to_post() -> None:
    """Posting without an explicit method falls back to ``POST``."""
    recorded: List[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request.method)
        return httpx.Response(200, json={"ok": True})

    async def run() -> bool:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await post_json(
                client,
                f"{CONFIG['backend_url']}/api/v1/devices/DEVICE-STATUS-1/status",
                {"command_id": "cmd-1", "status": "failed"},
                {"X-Device-ID": CONFIG["device_id"], "X-API-Key": CONFIG["api_key"]},
            )

    assert asyncio.run(run()) is True
    assert recorded == ["POST"]


def test_firmware_version_returns_nonempty() -> None:
    """The firmware/OS version helper returns a non-empty string."""
    rda.get_firmware_version.cache_clear()
    try:
        assert rda._firmware_version().strip() != ""
    finally:
        rda.get_firmware_version.cache_clear()


def test_firmware_version_prefers_platform_version(monkeypatch) -> None:
    """Non-Windows hosts fall back to platform.version() when available."""
    rda.get_firmware_version.cache_clear()
    monkeypatch.setattr(rda.platform, "system", lambda: "Linux")
    monkeypatch.setattr(rda.platform, "version", lambda: "10.0.26300")
    try:
        assert rda._firmware_version() == "10.0.26300"
    finally:
        rda.get_firmware_version.cache_clear()


def test_pending_commands_loop_wakes_on_push_event() -> None:
    """The command poller wakes early when the push wake_event is set."""
    config = {
        "command_poll_interval_seconds": 60,
        "device_id": "dev-1",
        "api_key": "key",
        "backend_url": "http://x",
    }
    wake_event = asyncio.Event()
    polls: List[str] = []

    async def fake_get_json(client: Any, url: str, headers: Any) -> None:
        polls.append(url)
        return None

    async def run() -> None:
        with (
            patch.object(
                rda, "fetch_device_permissions", new=AsyncMock(return_value=None)
            ),
            patch.object(rda, "get_json", side_effect=fake_get_json),
            patch.object(rda, "parse_pending_commands", return_value=[]),
        ):
            task = asyncio.create_task(
                rda.pending_commands_loop(None, config, None, None, wake_event)
            )
            # Let the first poll complete, then the loop waits on wake_event.
            await asyncio.sleep(0.15)
            wake_event.set()
            # The loop should wake immediately and poll again (interval is 60s).
            await asyncio.sleep(0.15)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    asyncio.run(run())
    assert len(polls) >= 2
