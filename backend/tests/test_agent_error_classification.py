"""Tests for delivery-failure classification in the on-device agent (W1).

Covers the pure classification helpers and the HTTP-layer behaviour: permanent
statuses (401/403/404/409) must raise a typed error (so callers stop retrying),
while transient failures (5xx, network errors) keep the existing
return-False/None + retry behaviour.
"""

import asyncio

import httpx
import pytest

from homepot.agent.real_device_agent import get_json, post_json, post_json_parsed
from homepot.agent.utils.command_poller import fetch_device_permissions
from homepot.agent.utils.errors import (
    DeviceRemovedError,
    DeviceSuspendedError,
    PermanentDeliveryError,
    classify_status,
    is_device_terminal_status,
    is_permanent_status,
)
from homepot.agent.utils.submission_log import SubmissionLog


@pytest.mark.parametrize("code", [401, 403, 404, 409])
def test_is_permanent_status_true_for_permanent_codes(code: int) -> None:
    """Permanent statuses are classified as non-retryable."""
    assert is_permanent_status(code) is True


@pytest.mark.parametrize("code", [200, 400, 408, 429, 500, 502, 503])
def test_is_permanent_status_false_for_transient_codes(code: int) -> None:
    """Transient/unknown statuses are not classified as permanent."""
    assert is_permanent_status(code) is False


@pytest.mark.parametrize("code", [401, 403])
def test_is_device_terminal_status_true(code: int) -> None:
    """401/403 mean the device credential/lifecycle is dead."""
    assert is_device_terminal_status(code) is True


@pytest.mark.parametrize("code", [404, 409, 500])
def test_is_device_terminal_status_false(code: int) -> None:
    """404/409/5xx are not device-terminal."""
    assert is_device_terminal_status(code) is False


@pytest.mark.parametrize("code", [401, 403])
def test_classify_status_returns_device_removed(code: int) -> None:
    """A device-terminal status maps to ``DeviceRemovedError``."""
    err = classify_status("https://x/heartbeat", code)
    assert isinstance(err, DeviceRemovedError)
    assert err.status_code == code
    assert err.url == "https://x/heartbeat"


@pytest.mark.parametrize("code", [404, 409])
def test_classify_status_returns_permanent_delivery(code: int) -> None:
    """A gone/conflicted status maps to ``PermanentDeliveryError``."""
    err = classify_status("https://x/heartbeat", code)
    assert isinstance(err, PermanentDeliveryError)
    assert err.status_code == code


@pytest.mark.parametrize("code", [408, 429, 500, 502, 503])
def test_classify_status_returns_none_for_transient(code: int) -> None:
    """Transient statuses are not classified at all."""
    assert classify_status("https://x/heartbeat", code) is None


def test_classify_status_returns_device_suspended() -> None:
    """423 Locked maps to the recoverable ``DeviceSuspendedError``."""
    err = classify_status("https://x/heartbeat", 423)
    assert isinstance(err, DeviceSuspendedError)
    assert err.status_code == 423
    assert err.url == "https://x/heartbeat"
    assert not isinstance(err, DeviceRemovedError)


def test_suspended_status_is_not_permanent_or_terminal() -> None:
    """Suspension must never be treated as a dead credential."""
    assert is_permanent_status(423) is False
    assert is_device_terminal_status(423) is False


class TestPostJsonSuspended:
    """``post_json`` surfaces 423 as a recoverable suspension."""

    def test_post_json_raises_device_suspended(self) -> None:
        """A 423 response raises ``DeviceSuspendedError``, not removal."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(423, json={"detail": "Device is suspended"})

        async def run() -> bool:
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                return await post_json(
                    client,
                    "https://x/api/v1/agent/heartbeat",
                    {"device_id": "d1"},
                    {"X-Device-ID": "d1"},
                )

        with pytest.raises(DeviceSuspendedError):
            asyncio.run(run())


class TestPostJsonPermanent:
    """``post_json`` raises on permanent statuses and returns False on transient."""

    @pytest.mark.parametrize(
        ("code", "exc"),
        [
            (401, DeviceRemovedError),
            (403, DeviceRemovedError),
            (404, PermanentDeliveryError),
            (409, PermanentDeliveryError),
        ],
    )
    def test_post_json_raises_on_permanent(self, code: int, exc: type) -> None:
        """A permanent HTTP status raises the corresponding typed error."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(code, json={"detail": "nope"})

        async def run() -> bool:
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                return await post_json(
                    client,
                    "https://x/api/v1/agent/heartbeat",
                    {"device_id": "d1"},
                    {"X-Device-ID": "d1"},
                )

        with pytest.raises(exc):
            asyncio.run(run())

    @pytest.mark.parametrize("code", [500, 502, 503])
    def test_post_json_returns_false_on_transient_5xx(self, code: int) -> None:
        """A 5xx response returns False (transient) rather than raising."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(code, json={"detail": "boom"})

        async def run() -> bool:
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                return await post_json(
                    client,
                    "https://x/api/v1/agent/heartbeat",
                    {"device_id": "d1"},
                    {"X-Device-ID": "d1"},
                )

        assert asyncio.run(run()) is False

    def test_post_json_returns_false_on_connect_error(self) -> None:
        """A network error returns False (transient) rather than raising."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        async def run() -> bool:
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                return await post_json(
                    client,
                    "https://x/api/v1/agent/heartbeat",
                    {"device_id": "d1"},
                    {"X-Device-ID": "d1"},
                )

        assert asyncio.run(run()) is False

    def test_post_json_records_submission_before_raising(self, tmp_path) -> None:
        """A permanent failure is still recorded in the submission log."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"detail": "Invalid Device ID"})

        async def run() -> None:
            log = SubmissionLog(log_path=tmp_path / "subs.jsonl")
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                await post_json(
                    client,
                    "https://x/api/v1/agent/heartbeat",
                    {"device_id": "d1"},
                    {"X-Device-ID": "d1"},
                    submission_log=log,
                )

        with pytest.raises(DeviceRemovedError):
            asyncio.run(run())
        records = SubmissionLog(log_path=tmp_path / "subs.jsonl").read_all()
        assert len(records) == 1
        assert records[0]["status_code"] == 401
        assert records[0]["accepted"] is False


class TestPostJsonParsedPermanent:
    """``post_json_parsed`` raises on permanent statuses."""

    def test_post_json_parsed_raises_on_permanent(self) -> None:
        """A 403 response raises ``DeviceRemovedError``."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, json={"detail": "suspended"})

        async def run() -> None:
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                await post_json_parsed(
                    client,
                    "https://x/api/v1/agent/alert",
                    {"device_id": "d1"},
                    {"X-Device-ID": "d1"},
                )

        with pytest.raises(DeviceRemovedError):
            asyncio.run(run())


class TestGetJsonPermanent:
    """``get_json`` raises on permanent statuses and returns None on transient."""

    def test_get_json_raises_on_permanent(self) -> None:
        """A 401 response raises ``DeviceRemovedError``."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"detail": "Invalid Device ID"})

        async def run() -> None:
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                await get_json(
                    client,
                    "https://x/api/v1/devices/pending",
                    {"X-Device-ID": "d1"},
                )

        with pytest.raises(DeviceRemovedError):
            asyncio.run(run())

    def test_get_json_returns_none_on_transient(self) -> None:
        """A network error returns None (transient) rather than raising."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused")

        async def run() -> None:
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                return await get_json(
                    client,
                    "https://x/api/v1/devices/pending",
                    {"X-Device-ID": "d1"},
                )

        assert asyncio.run(run()) is None


class TestFetchDevicePermissionsPermanent:
    """``fetch_device_permissions`` raises on permanent statuses."""

    def test_fetch_device_permissions_raises_on_permanent(self) -> None:
        """A 401 response raises ``DeviceRemovedError``."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"detail": "Invalid Device ID"})

        async def run() -> None:
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                await fetch_device_permissions(
                    client,
                    {"device_id": "d1", "backend_url": "https://x"},
                    {"X-Device-ID": "d1"},
                )

        with pytest.raises(DeviceRemovedError):
            asyncio.run(run())

    def test_fetch_device_permissions_returns_none_on_transient(self) -> None:
        """A network error returns None (transient) rather than raising."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused")

        async def run() -> None:
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                return await fetch_device_permissions(
                    client,
                    {"device_id": "d1", "backend_url": "https://x"},
                    {"X-Device-ID": "d1"},
                )

        assert asyncio.run(run()) is None
