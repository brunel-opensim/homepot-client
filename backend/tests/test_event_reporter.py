"""Tests for the structured event reporter."""

import asyncio
from typing import Any, Dict, List

import httpx

from homepot.agent.utils.event_reporter import emit_audit_event, emit_log_event

CONFIG: Dict[str, Any] = {
    "device_id": "DEVICE-EVT-1",
    "api_key": "test-api-key",
    "backend_url": "http://testserver",
}


def test_emit_log_event_posts_to_logs_endpoint() -> None:
    """emit_log_event sends a POST to /api/v1/agent/logs with the right payload."""
    requests: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"status": "success"})

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            await emit_log_event(
                client,
                CONFIG,
                level="warning",
                category="connectivity",
                message="Backend unreachable: heartbeat failed",
                context={"retry_queue_size": 3},
            )

    asyncio.run(run())
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert "/api/v1/agent/logs" in str(requests[0].url)
    import json

    body = json.loads(requests[0].content)
    assert body["device_id"] == "DEVICE-EVT-1"
    assert body["level"] == "warning"
    assert body["category"] == "connectivity"
    assert body["message"] == "Backend unreachable: heartbeat failed"
    assert body["context"] == {"retry_queue_size": 3}


def test_emit_audit_event_posts_to_audit_endpoint() -> None:
    """emit_audit_event sends a POST to /api/v1/agent/audit with the right payload."""
    requests: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"status": "success"})

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            await emit_audit_event(
                client,
                CONFIG,
                event_type="agent_started",
                description="Agent started (version 0.3.20)",
                metadata={"agent_version": "0.3.20"},
            )

    asyncio.run(run())
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert "/api/v1/agent/audit" in str(requests[0].url)
    import json

    body = json.loads(requests[0].content)
    assert body["device_id"] == "DEVICE-EVT-1"
    assert body["event_type"] == "agent_started"
    assert body["description"] == "Agent started (version 0.3.20)"
    assert body["metadata"] == {"agent_version": "0.3.20"}


def test_emit_log_event_does_not_raise_on_failure() -> None:
    """emit_log_event swallows exceptions and never propagates them."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server error"})

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            # Should not raise
            await emit_log_event(
                client,
                CONFIG,
                level="error",
                category="device",
                message="Something failed",
            )

    asyncio.run(run())  # No exception = pass


def test_emit_audit_event_does_not_raise_on_network_error() -> None:
    """emit_audit_event swallows network errors."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            # Should not raise
            await emit_audit_event(
                client,
                CONFIG,
                event_type="agent_stopped",
                description="Agent stopped",
            )

    asyncio.run(run())  # No exception = pass
