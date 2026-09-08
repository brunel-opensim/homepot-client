"""Transport-level tests for the real device agent HTTP calls."""

import asyncio
from typing import Any, Dict, List

import httpx
import pytest

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
