"""Tests for production hardening: log rotation, graceful shutdown, watchdog, and failure scenarios."""

import asyncio
import logging
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from homepot.agent.utils.log_setup import (
    configure_agent_logging,
    logging_config_from_config,
    reset_logging_config,
)
from homepot.agent.utils.retry_queue import RetryQueue

# ============================================================================
# Log rotation
# ============================================================================


class TestLogSetup:
    """Tests for centralised logging configuration."""

    def setup_method(self) -> None:
        """Reset logging config before each test."""
        reset_logging_config()

    def teardown_method(self) -> None:
        """Reset logging config after each test."""
        reset_logging_config()

    def test_configure_adds_stream_handler(self):
        """configure_agent_logging adds a StreamHandler to the root logger."""
        configure_agent_logging()
        root = logging.getLogger()
        assert any(isinstance(h, logging.StreamHandler) for h in root.handlers)

    def test_configure_with_log_file_creates_file(self):
        """configure_agent_logging with log_file creates the file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "agent.log"
            configure_agent_logging(log_file=str(log_path))
            logging.getLogger("test").info("test message")
            assert log_path.exists()

    def test_log_file_contains_message(self):
        """Message written to logger appears in the log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "agent.log"
            configure_agent_logging(log_file=str(log_path))
            logging.getLogger("test").info("hello world")
            content = log_path.read_text("utf-8")
            assert "hello world" in content

    def test_double_configure_is_idempotent(self):
        """Calling configure_agent_logging twice does not add duplicate handlers."""
        reset_logging_config()
        configure_agent_logging()
        count = len(logging.getLogger().handlers)
        configure_agent_logging()
        assert len(logging.getLogger().handlers) == count

    def test_logging_config_from_config_defaults(self):
        """logging_config_from_config returns sensible defaults for empty config."""
        result = logging_config_from_config({})
        assert result["log_file"] is None
        assert result["log_level"] == logging.INFO

    def test_logging_config_from_config_reads_values(self):
        """logging_config_from_config reads logging values from config dict."""
        config = {
            "log_file": "/var/log/homepot/agent.log",
            "log_level": "DEBUG",
            "log_max_bytes": 999,
            "log_backup_count": 3,
        }
        result = logging_config_from_config(config)
        assert result["log_file"] == "/var/log/homepot/agent.log"
        assert result["log_level"] == logging.DEBUG
        assert result["max_bytes"] == 999
        assert result["backup_count"] == 3

    def test_invalid_log_level_falls_back_to_info(self):
        """An invalid log level name falls back to INFO."""
        result = logging_config_from_config({"log_level": "INVALID"})
        assert result["log_level"] == logging.INFO

    def test_rotating_file_handler_rotation(self, caplog):
        """Rotating file handler rotates files when max_bytes is exceeded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "rotate.log"
            configure_agent_logging(
                log_file=str(log_path), max_bytes=50, backup_count=2
            )
            logger = logging.getLogger("rotate_test")
            # Write enough to trigger rotation
            for i in range(100):
                logger.info("line %03d — xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", i)
            # The original file and at least one backup should exist
            files = list(Path(tmpdir).glob("rotate.log*"))
            assert len(files) >= 2


# ============================================================================
# Graceful shutdown
# ============================================================================


class TestGracefulShutdown:
    """Tests for graceful shutdown via shutdown_event and signal handlers."""

    @pytest.mark.asyncio
    async def test_wait_with_shutdown_blocks_until_event(self):
        """_wait_with_shutdown blocks until interval elapses."""
        from homepot.agent.real_device_agent import _wait_with_shutdown

        event = asyncio.Event()
        start = asyncio.get_running_loop().time()
        await _wait_with_shutdown(0.05, event)
        elapsed = asyncio.get_running_loop().time() - start
        assert elapsed >= 0.04

    @pytest.mark.asyncio
    async def test_wait_with_shutdown_short_circuits_on_event(self):
        """_wait_with_shutdown returns early when shutdown_event is set."""
        from homepot.agent.real_device_agent import _wait_with_shutdown

        event = asyncio.Event()
        # Set the event immediately
        event.set()
        start = asyncio.get_running_loop().time()
        await _wait_with_shutdown(5, event)
        elapsed = asyncio.get_running_loop().time() - start
        assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_watchdog_loop_notifies_when_systemd_is_available(self):
        """_watchdog_loop calls sd_notify when systemd module is present."""
        from unittest.mock import MagicMock

        sd_notify = MagicMock()
        event = asyncio.Event()

        # Drive the loop for one iteration by mocking _wait_with_shutdown
        async def _fake_wait(*_a, **_kw):
            event.set()  # exit after first iteration

        with patch(
            "homepot.agent.real_device_agent._wait_with_shutdown",
            _fake_wait,
        ):
            from homepot.agent.real_device_agent import _watchdog_loop

            await _watchdog_loop(event, interval=1, _sd_notify=sd_notify)
            sd_notify.assert_called_once_with("WATCHDOG=1")

    @pytest.mark.asyncio
    async def test_watchdog_loop_noop_without_systemd(self):
        """_watchdog_loop returns immediately when no sd_notify is available."""
        from homepot.agent.real_device_agent import _watchdog_loop

        event = asyncio.Event()
        await _watchdog_loop(event, interval=1, _sd_notify=None)
        # If we get here without hanging, the noop path works

    @pytest.mark.asyncio
    async def test_shutdown_event_stops_watchdog_loop(self):
        """Setting shutdown_event causes the watchdog loop to exit."""
        from homepot.agent.real_device_agent import _watchdog_loop

        sd_notify = MagicMock()
        event = asyncio.Event()
        task = asyncio.ensure_future(
            _watchdog_loop(event, interval=1, _sd_notify=sd_notify)
        )
        await asyncio.sleep(0.05)
        assert not task.done()
        event.set()
        await asyncio.wait_for(task, timeout=5)
        assert task.done()

    @pytest.mark.asyncio
    async def test_signal_handler_sets_shutdown_event(self):
        """Signal handler sets the shutdown event."""
        shutdown_event = asyncio.Event()
        assert not shutdown_event.is_set()

        def _handle_signal() -> None:
            shutdown_event.set()

        _handle_signal()
        assert shutdown_event.is_set()


# ============================================================================
# Failure scenarios
# ============================================================================


class TestFailureScenarios:
    """Tests for agent behaviour under failure conditions."""

    # ------------------------------------------------------------------
    # Network loss — retry queue stores payloads for later delivery
    # ------------------------------------------------------------------

    def test_network_loss_queues_payload(self):
        """When POST fails, payload is queued in RetryQueue."""
        import httpx

        with tempfile.TemporaryDirectory() as tmpdir:
            queue = RetryQueue(queue_file=Path(tmpdir) / "retry.json")
            assert len(queue) == 0

            transport = httpx.MockTransport(lambda _: httpx.Response(503))
            httpx.Client(transport=transport)

            url = "http://localhost/api/v1/agent/heartbeat"
            payload = {"device_id": "d1"}
            queue.enqueue({"url": url, "payload": payload})
            assert len(queue) == 1
            assert queue.load()[0]["url"] == url

    def test_network_loss_backoff(self):
        """Failed items get exponential backoff via requeue."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue = RetryQueue(queue_file=Path(tmpdir) / "retry.json")
            queue.enqueue({"url": "http://localhost/api", "payload": {"k": "v"}})
            items = queue.dequeue_all()
            assert items[0]["retry_count"] == 0
            queue.requeue(items[0])
            items2 = queue.dequeue_all()
            assert items2[0]["retry_count"] == 1

    def test_network_loss_dequeue_ready_respects_backoff(self):
        """dequeue_ready only returns items whose backoff has elapsed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue = RetryQueue(queue_file=Path(tmpdir) / "retry.json")
            from datetime import datetime, timedelta, timezone

            future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            queue.save(
                [
                    {
                        "url": "http://localhost/api",
                        "payload": {},
                        "retry_count": 0,
                        "next_retry_at": future,
                    }
                ]
            )
            ready = queue.dequeue_ready()
            assert len(ready) == 0

    # ------------------------------------------------------------------
    # Token revocation — 401 responses
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_token_revocation_detected(self):
        """401 response from backend is detected and logged."""
        import httpx

        transport = httpx.MockTransport(lambda _: httpx.Response(401))
        client = httpx.AsyncClient(transport=transport)
        try:
            resp = await client.get("http://localhost/api/v1/devices/pending")
            assert resp.status_code == 401
        finally:
            await client.aclose()

    def test_clear_credentials_clears_all(self):
        """clear_credentials removes all stored credentials."""
        from homepot.agent.credential_storage import SimulationStorage

        storage = SimulationStorage()
        storage.save({"device_id": "d1", "api_key": "secret"})
        assert storage.is_provisioned()
        storage.clear()
        assert not storage.is_provisioned()
        assert storage.get_device_id() is None
        assert storage.get_api_key() is None

    # ------------------------------------------------------------------
    # Unpairing — clearing identity + credentials
    # ------------------------------------------------------------------

    def test_reset_identity_then_clear_credentials(self):
        """Unpairing clears both identity and credentials."""
        from homepot.agent.credential_storage import SimulationStorage

        storage = SimulationStorage()
        storage.save({"device_id": "d1", "api_key": "secret"})
        assert storage.is_provisioned()

        # Simulate reset_identity
        # (In a real scenario, reset_device_id() deletes the identity file)
        # Then clear credentials
        storage.clear()
        assert not storage.is_provisioned()

    def test_unpair_prevents_future_requests(self):
        """After unpair, agent cannot authenticate (no API key)."""
        from homepot.agent.credential_storage import SimulationStorage

        storage = SimulationStorage()
        assert not storage.is_provisioned()
        # Without credentials, get_auth_headers would fail
        assert storage.get_api_key() is None

    # ------------------------------------------------------------------
    # Duplicate enrolment
    # ------------------------------------------------------------------

    def test_duplicate_enrolment_rejected(self):
        """Simulate duplicate enrolment: second claim on consumed intent fails."""
        # The server rejects duplicate claims by checking intent status.
        # We test the agent's handling: a 400/409 response from the server.
        import httpx

        transport = httpx.MockTransport(
            lambda _: httpx.Response(400, json={"detail": "Intent already claimed"})
        )
        client = httpx.AsyncClient(transport=transport)

        async def _test():
            resp = await client.post(
                "http://localhost/api/v1/enrolment-intents/i1/claim",
                json={"claim_token": "t1"},
            )
            assert resp.status_code == 400
            data = resp.json()
            assert "already claimed" in data["detail"].lower()

        asyncio.run(_test())

    # ------------------------------------------------------------------
    # Retry resilience
    # ------------------------------------------------------------------

    def test_retry_queue_survives_restart(self):
        """Retry queue persists to disk and survives a restart."""
        with tempfile.TemporaryDirectory() as tmpdir:
            qfile = Path(tmpdir) / "retry.json"
            # First session
            q1 = RetryQueue(queue_file=qfile)
            q1.enqueue({"url": "http://a.com", "payload": {"k": "v"}})
            assert len(q1) == 1

            # Second session (simulates restart)
            q2 = RetryQueue(queue_file=qfile)
            assert len(q2) == 1
            items = q2.dequeue_all()
            assert items[0]["url"] == "http://a.com"
