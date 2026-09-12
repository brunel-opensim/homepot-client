"""Transport-level tests for the real device agent HTTP calls."""

import asyncio
from typing import Any, Dict, List

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


def _completed_outcome() -> Dict[str, Any]:
    """Deterministic "completed" outcome for job-reporting tests."""
    return {
        "status": "completed",
        "result": {"message": "Executed successfully", "exit_code": 0},
        "error_message": None,
    }


async def test_report_background_job_queues_then_completes(monkeypatch: Any) -> None:
    """Cycle 1 queues a job; cycle 2 completes it and queues the next."""
    monkeypatch.setattr(rda, "_next_job_outcome", _completed_outcome)
    monkeypatch.setattr(
        rda,
        "_next_background_activity",
        lambda: {"action": "Log Rotation", "description": "Rotate agent logs"},
    )
    requests: List[httpx.Request] = []
    created = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            created["n"] += 1
            return httpx.Response(
                200,
                json={"status": "success", "data": {"job_id": f"job-{created['n']}"}},
            )
        return httpx.Response(200, json={"status": "success"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        first = await rda._report_background_job(client, CONFIG, None)
        assert first == "job-1"
        second = await rda._report_background_job(client, CONFIG, first)
        assert second == "job-2"

    assert [req.method for req in requests[:3]] == ["POST", "PUT", "POST"]
    assert requests[0].url.path == "/api/v1/agent/jobs"
    assert requests[1].url.path == "/api/v1/agent/jobs/job-1"

    create_body = requests[0].read().decode()
    assert '"action":"Log Rotation"' in create_body
    assert '"priority":"low"' in create_body
    assert '"device_id":"DEVICE-STATUS-1"' in create_body

    update_body = requests[1].read().decode()
    assert '"status":"completed"' in update_body
    assert '"device_id":"DEVICE-STATUS-1"' in update_body

    final_create = requests[2].read().decode()
    assert '"action":"Log Rotation"' in final_create


async def test_report_background_job_retries_failed_update(monkeypatch: Any) -> None:
    """A failed job-status update keeps the job id so the next cycle retries."""
    monkeypatch.setattr(rda, "_next_job_outcome", _completed_outcome)
    posts: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            posts.append(request)
        return httpx.Response(500, json={"detail": "boom"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        job_id = await rda._report_background_job(client, CONFIG, "job-stuck")

    assert job_id == "job-stuck"
    assert not posts, "no new job should be created while an update is in flight"


async def test_report_background_job_returns_none_on_create_failure(
    monkeypatch: Any,
) -> None:
    """A failed job create returns ``None`` and does not raise."""
    monkeypatch.setattr(rda, "_next_job_outcome", _completed_outcome)
    monkeypatch.setattr(
        rda,
        "_next_background_activity",
        lambda: {"action": "Security Scan", "description": "Scan for threats"},
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "boom"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        job_id = await rda._report_background_job(client, CONFIG, None)

    assert job_id is None
