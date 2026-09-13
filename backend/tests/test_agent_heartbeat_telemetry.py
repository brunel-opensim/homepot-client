"""Tests for heartbeat and telemetry payload utilities."""

import asyncio
from collections import deque
from datetime import datetime, timezone
import json
import time

import httpx
import pytest

from homepot.agent.real_device_agent import live_logs_loop
from homepot.agent.utils.command_poller import build_status_report
from homepot.agent.utils.heartbeat import build_heartbeat_payload, utc_now_iso
from homepot.agent.utils.telemetry import (
    build_telemetry_payload,
    collect_pos_signals,
    collect_system_telemetry,
    collect_uptime_seconds,
    measure_network_latency_ms,
)
from homepot.agent.utils.telemetry import utc_now_iso as te_utc_now
from homepot.app.schemas.agent import AgentRegisterRequest, AgentTelemetryRequest


class TestHeartbeatUtcNowIso:
    """Tests for the heartbeat ``utc_now_iso`` helper."""

    def test_returns_iso_format_string(self):
        """Returned string is parseable as an ISO-8601 datetime."""
        result = utc_now_iso()
        assert isinstance(result, str)
        parsed = datetime.fromisoformat(result)
        assert parsed.tzinfo is not None

    def test_returns_utc_time(self):
        """Returned timestamp is within 5 seconds of current UTC time."""
        result = utc_now_iso()
        parsed = datetime.fromisoformat(result)
        diff = abs((datetime.now(timezone.utc) - parsed).total_seconds())
        assert diff < 5


class TestBuildHeartbeatPayload:
    """Tests for ``build_heartbeat_payload``."""

    def test_requires_device_id(self):
        """Payload includes the provided device_id."""
        payload = build_heartbeat_payload("dev-1")
        assert payload["device_id"] == "dev-1"

    def test_includes_timestamp(self):
        """Payload includes an ISO-8601 timestamp."""
        payload = build_heartbeat_payload("dev-1")
        assert "timestamp" in payload
        parsed = datetime.fromisoformat(payload["timestamp"])
        assert parsed.tzinfo is not None

    def test_includes_status_default(self):
        """Default status is ONLINE."""
        payload = build_heartbeat_payload("dev-1")
        assert payload["status"] == "ONLINE"

    def test_accepts_custom_status(self):
        """Accepts a custom status string."""
        payload = build_heartbeat_payload("dev-1", status="OFFLINE")
        assert payload["status"] == "OFFLINE"

    def test_includes_site_id_when_provided(self):
        """Site ID is included when provided."""
        payload = build_heartbeat_payload("dev-1", site_id="site-99")
        assert payload["site_id"] == "site-99"

    def test_omits_site_id_when_not_provided(self):
        """Site ID is omitted when not provided."""
        payload = build_heartbeat_payload("dev-1")
        assert "site_id" not in payload

    def test_includes_extra_fields(self):
        """Extra fields are included in the payload."""
        payload = build_heartbeat_payload("dev-1", extra={"battery": 85})
        assert payload["extra"] == {"battery": 85}

    def test_timestamp_is_recent(self):
        """Timestamp is within 5 seconds of now."""
        payload = build_heartbeat_payload("dev-1")
        parsed = datetime.fromisoformat(payload["timestamp"])
        diff = abs((datetime.now(timezone.utc) - parsed).total_seconds())
        assert diff < 5


class TestTelemetryUtcNowIso:
    """Tests for the telemetry ``utc_now_iso`` helper."""

    def test_returns_iso_format_string(self):
        """Returned string is parseable as an ISO-8601 datetime."""
        result = te_utc_now()
        assert isinstance(result, str)
        parsed = datetime.fromisoformat(result)
        assert parsed.tzinfo is not None

    def test_returns_utc_time(self):
        """Returned timestamp is within 5 seconds of current UTC time."""
        result = te_utc_now()
        parsed = datetime.fromisoformat(result)
        diff = abs((datetime.now(timezone.utc) - parsed).total_seconds())
        assert diff < 5


class TestCollectSystemTelemetry:
    """Tests for ``collect_system_telemetry``."""

    def test_returns_dict_with_expected_keys(self):
        """Returned dict contains cpu, memory, and disk keys."""
        metrics = collect_system_telemetry()
        assert "cpu_usage" in metrics
        assert "memory_usage" in metrics
        assert "disk_usage" in metrics

    def test_values_are_floats(self):
        """All metric values are floats."""
        metrics = collect_system_telemetry()
        for key in ("cpu_usage", "memory_usage", "disk_usage"):
            assert isinstance(metrics[key], float), f"{key} should be float"

    def test_cpu_usage_in_range(self):
        """CPU usage is between 0 and 100."""
        metrics = collect_system_telemetry()
        assert 0 <= metrics["cpu_usage"] <= 100

    def test_cpu_is_interval_average_since_last_sample(self, monkeypatch):
        """cpu_usage samples the non-blocking average since the last call."""
        calls: list = []

        def fake_cpu_percent(interval=None):
            calls.append(interval)
            return 12.34

        monkeypatch.setattr(
            "homepot.agent.utils.telemetry.psutil.cpu_percent", fake_cpu_percent
        )
        metrics = collect_system_telemetry()
        assert calls == [None]
        assert metrics["cpu_usage"] == 12.3

    def test_cpu_usage_clamps_negative_delta(self, monkeypatch):
        """A backwards time delta never yields a negative CPU value."""
        monkeypatch.setattr(
            "homepot.agent.utils.telemetry.psutil.cpu_percent",
            lambda interval=None: -4.2,
        )
        metrics = collect_system_telemetry()
        assert metrics["cpu_usage"] == 0.0

    def test_disk_io_is_throughput_since_last_read(self, monkeypatch):
        """disk_io_bytes_s reports combined read/write bytes per second."""
        import homepot.agent.utils.telemetry as telemetry

        # Seed one anchor snapshot ~10s in the past so the window has a baseline.
        baseline_ts = time.time() - 10.0
        telemetry._disk_io_samples = deque([(baseline_ts, (0, 0))])

        class FakeIO:
            def __init__(self, read_bytes, write_bytes):
                self.read_bytes = read_bytes
                self.write_bytes = write_bytes

        current = FakeIO(10_000_000, 2_000_000)
        monkeypatch.setattr(telemetry.psutil, "disk_io_counters", lambda: current)

        metrics = collect_system_telemetry()
        assert metrics["disk_io_bytes_s"] == pytest.approx(1_200_000.0, rel=1e-3)

    def test_disk_io_zero_when_sampled_too_quickly(self, monkeypatch):
        """disk_io_bytes_s remains 0.0 before the minimum sample interval elapses."""
        import homepot.agent.utils.telemetry as telemetry

        # Anchor is *now*, so no meaningful window has elapsed yet.
        telemetry._disk_io_samples = deque([(time.time(), (0, 0))])

        class FakeIO:
            def __init__(self, read_bytes, write_bytes):
                self.read_bytes = read_bytes
                self.write_bytes = write_bytes

        current = FakeIO(10_000_000, 2_000_000)
        monkeypatch.setattr(telemetry.psutil, "disk_io_counters", lambda: current)

        metrics = collect_system_telemetry()
        assert metrics["disk_io_bytes_s"] == 0.0

    def test_disk_io_rate_is_cadence_independent(self, monkeypatch):
        """A burst of samples right after another caller still reports the rate.

        Regression: telemetry posts previously landed a few milliseconds after
        the live-logs loop sampled the same module, so the per-read window was
        effectively empty and disk I/O rounded to ``0.0`` on every post.
        """
        import homepot.agent.utils.telemetry as telemetry

        # A real-looking sampling history spanning a full telemetry window.
        base = time.time() - 30.0
        telemetry._disk_io_samples = deque(
            [
                (base, (0, 0)),
                (base + 15.0, (6_000_000, 0)),
                (base + 29.999, (9_000_000, 3_000_000)),
            ]
        )

        class FakeIO:
            def __init__(self, read_bytes, write_bytes):
                self.read_bytes = read_bytes
                self.write_bytes = write_bytes

        current = FakeIO(9_000_000, 3_000_000)
        monkeypatch.setattr(telemetry.psutil, "disk_io_counters", lambda: current)

        # Two rapid samples (telemetry right after a live-logs read).
        first = collect_system_telemetry()["disk_io_bytes_s"]
        second = collect_system_telemetry()["disk_io_bytes_s"]

        # Both must reflect ~30s of real I/O, not a sub-second zeroed window.
        expected = (9_000_000 + 3_000_000) / 30.0
        assert first == pytest.approx(expected, rel=1e-1)
        assert second == pytest.approx(expected, rel=1e-1)

    def test_disk_io_zero_when_no_baseline(self, monkeypatch):
        """disk_io_bytes_s falls back to 0.0 when counters are unavailable."""
        import homepot.agent.utils.telemetry as telemetry

        monkeypatch.setattr(telemetry.psutil, "disk_io_counters", lambda: None)

        metrics = collect_system_telemetry()
        assert metrics["disk_io_bytes_s"] == 0.0

    def test_disk_io_sample_cap_trims_oldest_only(self, monkeypatch):
        """When history exceeds the cap, only the oldest samples are discarded."""
        import homepot.agent.utils.telemetry as telemetry

        now = 1_000.0
        max_samples = telemetry._DISK_IO_MAX_SAMPLES
        seeded = deque(
            [
                (
                    now - 10.0 + (10.0 * i / (max_samples + 1)),
                    (float(i), float(i)),
                )
                for i in range(max_samples + 1)
            ]
        )
        telemetry._disk_io_samples = seeded

        class FakeIO:
            def __init__(self, read_bytes, write_bytes):
                self.read_bytes = read_bytes
                self.write_bytes = write_bytes

        current = FakeIO(float(max_samples + 500), float(max_samples + 500))
        monkeypatch.setattr(telemetry.time, "time", lambda: now)
        monkeypatch.setattr(telemetry.psutil, "disk_io_counters", lambda: current)

        rate = telemetry._disk_io_bytes_per_second()

        assert len(telemetry._disk_io_samples) == max_samples
        anchor_ts, anchor_io = telemetry._disk_io_samples[0]
        assert anchor_io == (0.0, 0.0)
        expected = (
            (current.read_bytes - anchor_io[0]) + (current.write_bytes - anchor_io[1])
        ) / (now - anchor_ts)
        assert rate == pytest.approx(expected, rel=1e-6)

    def test_memory_usage_in_range(self):
        """Memory usage is between 0 and 100."""
        metrics = collect_system_telemetry()
        assert 0 <= metrics["memory_usage"] <= 100

    def test_disk_usage_in_range(self):
        """Disk usage is between 0 and 100."""
        metrics = collect_system_telemetry()
        assert 0 <= metrics["disk_usage"] <= 100

    def test_includes_uptime_seconds(self):
        """System telemetry includes a whole-second host uptime value."""
        metrics = collect_system_telemetry()
        assert "uptime_seconds" in metrics
        assert isinstance(metrics["uptime_seconds"], int)
        assert metrics["uptime_seconds"] >= 0


class TestCollectUptimeSeconds:
    """Tests for ``collect_uptime_seconds``."""

    def test_returns_non_negative_int(self):
        """Uptime is a non-negative integer, as the backend schema expects."""
        uptime = collect_uptime_seconds()
        assert isinstance(uptime, int)
        assert uptime >= 0


class TestTelemetryPayloadMatchesBackendSchema:
    """The agent's telemetry payload must validate against the live backend schema."""

    def test_build_telemetry_payload_validates(self):
        """Telemetry payload built by the agent passes the backend schema."""
        payload = build_telemetry_payload("DEVICE-TEST-0001")
        AgentTelemetryRequest(**payload)

    def test_build_telemetry_payload_with_site_id_validates(self):
        """Telemetry payload with an extra site_id still passes the schema."""
        payload = build_telemetry_payload(
            "DEVICE-TEST-0001", collection_interval_seconds=30
        )
        payload["site_id"] = "SITE-TEST"
        AgentTelemetryRequest(**payload)


class TestDeviceDnaPayloadMatchesBackendSchema:
    """The agent's device-DNA payload must validate against the backend schema."""

    def test_dna_payload_with_int_site_id_validates(self):
        """DNA payload stringifies the int site_id so the schema accepts it."""
        config = {
            "device_id": "DEVICE-TEST-0001",
            "site_id": 2,
            "device_name": "test-device",
            "device_type": "pos_terminal",
            "os_details": "Darwin 25.6.0",
        }
        payload = {
            "device_id": config["device_id"],
            "site_id": str(config.get("site_id") or ""),
            "device_name": config.get("device_name"),
            "device_type": config.get("device_type", "pos_terminal"),
            "mac_address": "00:00:00:00:00:00",
            "os_details": config.get("os_details"),
            "local_ip": None,
            "wan_ip": None,
            "peripherals": {"printers": [], "scanners": [], "card_readers": []},
        }
        AgentRegisterRequest(**payload)


class TestMeasureNetworkLatencyMs:
    """Tests for ``measure_network_latency_ms``."""

    def test_returns_elapsed_ms_on_http_response(self):
        """A responding backend yields a non-negative latency in milliseconds."""

        async def _handler(request):
            return httpx.Response(404, json={})

        async def _run():
            transport = httpx.MockTransport(_handler)
            async with httpx.AsyncClient(transport=transport) as client:
                return await measure_network_latency_ms(
                    client, "https://backend.example.com"
                )

        result = asyncio.run(_run())
        assert isinstance(result, float)
        assert result >= 0

    def test_returns_none_on_transport_error(self):
        """An unreachable backend yields no latency measurement."""

        async def _handler(request):
            raise httpx.ConnectError("connection refused")

        async def _run():
            transport = httpx.MockTransport(_handler)
            async with httpx.AsyncClient(transport=transport) as client:
                return await measure_network_latency_ms(
                    client, "https://backend.example.com"
                )

        result = asyncio.run(_run())
        assert result is None


class TestCollectPosSignals:
    """Tests for ``collect_pos_signals``."""

    def test_returns_none_when_unconfigured(self):
        """No source configured means no POS signals (never fabricated)."""
        assert collect_pos_signals(None) is None

    def test_reads_json_source(self, tmp_path):
        """A configured JSON source yields its POS metrics object."""
        source = tmp_path / "pos_signals.json"
        source.write_text(
            json.dumps({"transaction_count": 42, "transaction_volume": 120.5}),
            encoding="utf-8",
        )
        result = collect_pos_signals(str(source))
        assert result == {
            "transaction_count": 42,
            "transaction_volume": 120.5,
        }

    def test_returns_none_for_invalid_source(self, tmp_path):
        """A missing or malformed source yields no POS signals."""
        assert collect_pos_signals(str(tmp_path / "missing.json")) is None
        bad = tmp_path / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        assert collect_pos_signals(str(bad)) is None


class TestBuildTelemetryPayload:
    """Tests for ``build_telemetry_payload``."""

    def test_requires_device_id(self):
        """Payload includes the provided device_id."""
        payload = build_telemetry_payload("dev-1")
        assert payload["device_id"] == "dev-1"

    def test_includes_timestamp(self):
        """Payload includes an ISO-8601 timestamp."""
        payload = build_telemetry_payload("dev-1")
        assert "timestamp" in payload
        parsed = datetime.fromisoformat(payload["timestamp"])
        assert parsed.tzinfo is not None

    def test_includes_system_metrics(self):
        """Payload includes cpu, memory, disk, and uptime metrics."""
        payload = build_telemetry_payload("dev-1")
        assert "cpu_usage" in payload
        assert "memory_usage" in payload
        assert "disk_usage" in payload
        assert "uptime_seconds" in payload

    def test_includes_network_latency_when_provided(self):
        """Payload includes measured network latency when available."""
        payload = build_telemetry_payload("dev-1", network_latency_ms=8.4)
        assert payload["network_latency_ms"] == 8.4

    def test_omits_network_latency_when_not_measured(self):
        """Payload omits network latency when unavailable."""
        payload = build_telemetry_payload("dev-1")
        assert "network_latency_ms" not in payload

    def test_includes_collection_interval_when_provided(self):
        """Payload includes the configured collection interval."""
        payload = build_telemetry_payload("dev-1", collection_interval_seconds=30)
        assert payload["collection_interval_seconds"] == 30

    def test_omits_collection_interval_when_not_provided(self):
        """Payload omits the collection interval when unavailable."""
        payload = build_telemetry_payload("dev-1")
        assert "collection_interval_seconds" not in payload

    def test_timestamp_is_sample_time(self):
        """Payload timestamp is the device sample time (UTC ISO-8601)."""
        payload = build_telemetry_payload("dev-1")
        parsed = datetime.fromisoformat(payload["timestamp"])
        assert parsed.tzinfo is not None

    def test_cpu_is_float(self):
        """CPU usage is a float."""
        payload = build_telemetry_payload("dev-1")
        assert isinstance(payload["cpu_usage"], float)

    def test_includes_extra_fields(self):
        """Extra fields are included in the payload."""
        payload = build_telemetry_payload("dev-1", extra={"network_rx": 1024})
        assert payload["extra"] == {"network_rx": 1024}

    def test_omits_extra_when_not_provided(self):
        """Extra key is omitted when not provided."""
        payload = build_telemetry_payload("dev-1")
        assert "extra" not in payload

    def test_timestamp_is_recent(self):
        """Timestamp is within 5 seconds of now."""
        payload = build_telemetry_payload("dev-1")
        parsed = datetime.fromisoformat(payload["timestamp"])
        diff = abs((datetime.now(timezone.utc) - parsed).total_seconds())
        assert diff < 5


class TestLiveLogsLoop:
    """Tests for the continuous live-log status streaming loop."""

    CONFIG = {
        "device_id": "live-log-device",
        "backend_url": "https://backend.example.com",
        "live_log_interval_seconds": 1,
        "api_key": "secret",
    }

    def test_posts_status_line_to_agent_logs(self):
        """The loop POSTs a status snapshot to /agent/logs on its first iteration."""

        async def _handler(request):
            self.received = self.received + 1
            assert request.url.path == "/api/v1/agent/logs"
            body = json.loads(request.content)
            assert body["device_id"] == "live-log-device"
            assert body["category"] == "status"
            assert body["level"] == "info"
            assert "cpu" in body["message"]
            return httpx.Response(200, json={"status": "success"})

        self.received = 0
        self.cancelled = False

        async def _run():
            transport = httpx.MockTransport(_handler)
            async with httpx.AsyncClient(transport=transport) as client:
                loop = asyncio.ensure_future(live_logs_loop(client, dict(self.CONFIG)))
                await asyncio.sleep(0.3)
                loop.cancel()
                try:
                    await loop
                except asyncio.CancelledError:
                    pass

        asyncio.run(_run())
        assert self.received == 1, "expected exactly one POST on first iteration"

    def test_deduplicates_unchanged_status(self):
        """The loop skips posting when the reported metrics are unchanged."""

        async def _handler(request):
            self.received = self.received + 1
            return httpx.Response(200, json={"status": "success"})

        self.received = 0

        async def _run():
            transport = httpx.MockTransport(_handler)
            async with httpx.AsyncClient(transport=transport) as client:
                loop = asyncio.ensure_future(live_logs_loop(client, dict(self.CONFIG)))
                # Allow enough ticks for several iterations; unchanged metrics
                # should suppress duplicate posts.
                await asyncio.sleep(0.35)
                loop.cancel()
                try:
                    await loop
                except asyncio.CancelledError:
                    pass

        asyncio.run(_run())
        assert self.received == 1, (
            "expected one POST only (dedupe of unchanged metrics), got "
            f"{self.received}"
        )

    def test_build_status_report_has_live_fields(self):
        """build_status_report exposes the fields the live-log message uses."""
        report = build_status_report(dict(self.CONFIG))
        for key in ("cpu_usage", "memory_usage", "disk_usage", "uptime_seconds"):
            assert key in report, f"missing {key} in status report"
