"""Tests for heartbeat and telemetry payload utilities."""

from datetime import datetime, timezone

from homepot.agent.utils.heartbeat import build_heartbeat_payload, utc_now_iso
from homepot.agent.utils.telemetry import (
    build_telemetry_payload,
    collect_system_telemetry,
)
from homepot.agent.utils.telemetry import utc_now_iso as te_utc_now


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
        """Payload includes cpu, memory, and disk metrics."""
        payload = build_telemetry_payload("dev-1")
        assert "cpu_usage" in payload
        assert "memory_usage" in payload
        assert "disk_usage" in payload

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
