"""Tests for heartbeat and telemetry payload utilities."""

import asyncio
from datetime import datetime, timezone
import json

import httpx

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
