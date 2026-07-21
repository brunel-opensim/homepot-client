"""Tests for command polling and push wake-up utilities."""

from homepot.agent.utils.command_poller import (
    build_status_update_payload,
    parse_pending_commands,
    process_command,
)
from homepot.agent.utils.push_listener import PushWakeupListener


class TestParsePendingCommands:
    """Tests for ``parse_pending_commands``."""

    def test_none_returns_empty_list(self):
        """None input returns an empty list."""
        assert parse_pending_commands(None) == []

    def test_empty_list_returns_empty_list(self):
        """Empty list input returns an empty list."""
        assert parse_pending_commands([]) == []

    def test_list_of_dicts_returns_same(self):
        """A list of command dicts is returned as-is."""
        cmds = [{"command_id": "1"}, {"command_id": "2"}]
        result = parse_pending_commands(cmds)
        assert len(result) == 2
        assert result[0]["command_id"] == "1"

    def test_filters_non_dict_items(self):
        """Non-dict items in a list are filtered out."""
        cmds = [{"command_id": "1"}, "not-a-dict", {"command_id": "2"}]
        result = parse_pending_commands(cmds)
        assert len(result) == 2

    def test_dict_with_commands_key(self):
        """A dict with a 'commands' key is unwrapped."""
        data = {"commands": [{"command_id": "1"}, {"command_id": "2"}]}
        result = parse_pending_commands(data)
        assert len(result) == 2

    def test_dict_without_commands_key(self):
        """A plain dict without a 'commands' key returns empty list."""
        assert parse_pending_commands({"status": "ok"}) == []

    def test_dict_with_non_list_commands_value(self):
        """A dict with a non-list 'commands' value returns empty list."""
        assert parse_pending_commands({"commands": "invalid"}) == []

    def test_empty_dict_returns_empty_list(self):
        """An empty dict returns empty list."""
        assert parse_pending_commands({}) == []


class TestProcessCommand:
    """Tests for ``process_command``."""

    def test_unknown_command_type_returns_failed(self):
        """Unknown command_type returns status 'failed'."""
        result = process_command({"command_id": "c1", "command_type": "unknown_cmd"})
        assert result["status"] == "failed"
        assert "error" in result["result"]

    def test_ping_returns_completed_with_pong(self):
        """Ping command returns status 'completed' with 'pong' message."""
        result = process_command({"command_id": "c1", "command_type": "ping"})
        assert result["status"] == "completed"
        assert result["result"]["message"] == "pong"

    def test_restart_returns_completed(self):
        """Restart command returns status 'completed'."""
        result = process_command({"command_id": "c1", "command_type": "restart"})
        assert result["status"] == "completed"

    def test_shutdown_returns_completed(self):
        """Shutdown command returns status 'completed'."""
        result = process_command({"command_id": "c1", "command_type": "shutdown"})
        assert result["status"] == "completed"

    def test_update_config_with_payload(self):
        """Update_config command includes applied_keys in result."""
        result = process_command(
            {
                "command_id": "c1",
                "command_type": "update_config",
                "payload": {"theme": "dark", "polling_rate": 30},
            }
        )
        assert result["status"] == "completed"
        assert set(result["result"]["applied_keys"]) == {"theme", "polling_rate"}

    def test_update_config_without_payload(self):
        """Update_config command with no payload returns empty applied_keys."""
        result = process_command({"command_id": "c1", "command_type": "update_config"})
        assert result["status"] == "completed"
        assert result["result"]["applied_keys"] == []

    def test_missing_command_id_does_not_raise(self):
        """Missing command_id does not raise."""
        result = process_command({"command_type": "ping"})
        assert result["status"] == "completed"

    def test_missing_command_type_uses_empty_string(self):
        """Missing command_type is treated as empty string (unknown)."""
        result = process_command({"command_id": "c1"})
        assert result["status"] == "failed"


class TestBuildStatusUpdatePayload:
    """Tests for ``build_status_update_payload``."""

    def test_minimal_payload(self):
        """Payload with just command_id and status."""
        payload = build_status_update_payload("c1", "completed")
        assert payload["status"] == "completed"

    def test_payload_with_result(self):
        """Payload includes result dict when provided."""
        payload = build_status_update_payload("c1", "completed", {"message": "done"})
        assert payload["status"] == "completed"
        assert payload["result"] == {"message": "done"}

    def test_payload_without_result(self):
        """Payload omits result key when not provided."""
        payload = build_status_update_payload("c1", "failed")
        assert "result" not in payload


class TestPushWakeupListener:
    """Tests for ``PushWakeupListener``."""

    def test_creates_event(self):
        """Listener creates an asyncio Event."""
        listener = PushWakeupListener("dev-1")
        assert listener.wake_event is not None

    def test_event_cleared_by_default(self):
        """Wake event is not set by default."""
        listener = PushWakeupListener("dev-1")
        assert not listener.wake_event.is_set()

    def test_stop_without_start_does_not_raise(self):
        """Calling stop without start does not raise."""
        import asyncio

        listener = PushWakeupListener("dev-1")
        asyncio.run(listener.stop())

    def test_simulated_mode_when_no_mqtt_host(self):
        """Listener logs simulated mode when no MQTT host is configured."""
        import asyncio

        listener = PushWakeupListener("dev-1")
        # Should not raise when MQTT is not configured
        asyncio.run(listener.start())
        asyncio.run(listener.stop())

    def test_mqtt_device_topic_format(self):
        """Device topic follows expected format."""
        listener = PushWakeupListener("dev-42")
        assert listener._topic == "devices/dev-42/commands"

    def test_custom_topic_prefix(self):
        """Topic prefix can be customised."""
        listener = PushWakeupListener("dev-1", topic_prefix="custom")
        assert listener._topic == "custom/dev-1/commands"
