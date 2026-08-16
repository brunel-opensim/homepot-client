"""Tests for command polling and push wake-up utilities."""

from datetime import datetime
from unittest.mock import patch

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


ALLOW_ALL: dict[str, bool] = {
    "root_access": True,
    "command_execution": True,
    "process_monitoring": True,
    "filesystem_access": True,
    "network_monitoring": True,
}

DENY_ALL: dict[str, bool] = {
    "root_access": False,
    "command_execution": False,
    "process_monitoring": False,
    "filesystem_access": False,
    "network_monitoring": False,
}


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

    def test_restart_allowed_with_root_access(self):
        """Restart succeeds when root_access is granted."""
        result = process_command(
            {"command_id": "c1", "command_type": "restart"}, ALLOW_ALL
        )
        assert result["status"] == "completed"

    def test_restart_denied_without_root_access(self):
        """Restart fails when root_access is denied."""
        result = process_command(
            {"command_id": "c1", "command_type": "restart"}, DENY_ALL
        )
        assert result["status"] == "failed"
        assert "denied" in result["result"]["error"]

    def test_shutdown_allowed_with_root_access(self):
        """Shutdown succeeds when root_access is granted."""
        result = process_command(
            {"command_id": "c1", "command_type": "shutdown"}, ALLOW_ALL
        )
        assert result["status"] == "completed"

    def test_shutdown_denied_without_root_access(self):
        """Shutdown fails when root_access is denied."""
        result = process_command(
            {"command_id": "c1", "command_type": "shutdown"}, DENY_ALL
        )
        assert result["status"] == "failed"
        assert "denied" in result["result"]["error"]

    def test_update_config_allowed_with_filesystem_access(self):
        """Update_config succeeds when filesystem_access is granted."""
        result = process_command(
            {
                "command_id": "c1",
                "command_type": "update_config",
                "payload": {"theme": "dark", "polling_rate": 30},
            },
            ALLOW_ALL,
        )
        assert result["status"] == "completed"
        assert set(result["result"]["applied_keys"]) == {"theme", "polling_rate"}

    def test_update_config_denied_without_filesystem_access(self):
        """Update_config fails when filesystem_access is denied."""
        result = process_command(
            {"command_id": "c1", "command_type": "update_config"}, DENY_ALL
        )
        assert result["status"] == "failed"
        assert "denied" in result["result"]["error"]

    def test_update_config_without_payload(self):
        """Update_config command with no payload returns empty applied_keys."""
        result = process_command(
            {"command_id": "c1", "command_type": "update_config"}, ALLOW_ALL
        )
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

    def test_denied_without_permissions(self):
        """Privileged command fails when permissions dict is None."""
        result = process_command({"command_id": "c1", "command_type": "restart"})
        assert result["status"] == "failed"
        assert "not available" in result["result"]["error"]

    def test_run_command_requires_command_execution(self):
        """Command execution is denied without the owner grant."""
        result = process_command(
            {
                "command_id": "c1",
                "command_type": "run_command",
                "payload": {"data": {"command": "whoami"}},
            },
            DENY_ALL,
        )
        assert result["status"] == "failed"
        assert "command_execution" in result["result"]["error"]

    def test_root_command_requires_both_grants(self):
        """Root execution requires command and root grants."""
        permissions = {**ALLOW_ALL, "root_access": False}
        result = process_command(
            {
                "command_id": "c1",
                "command_type": "run_command",
                "payload": {"data": {"command": "id", "run_as_root": True}},
            },
            permissions,
        )
        assert result["status"] == "failed"
        assert "root_access" in result["result"]["error"]

    def test_script_cannot_embed_sudo_without_root_request(self):
        """Scripts cannot bypass explicit root approval with embedded sudo."""
        result = process_command(
            {
                "command_id": "c1",
                "command_type": "run_script",
                "payload": {"data": {"script": "echo ready\nsudo id"}},
            },
            ALLOW_ALL,
        )
        assert result["status"] == "failed"
        assert "run_as_root" in result["result"]["error"]

    @patch("homepot.agent.utils.command_poller.subprocess.run")
    def test_root_script_uses_non_interactive_sudo(self, run):
        """Approved root scripts use non-interactive sudo."""
        run.return_value.returncode = 0
        run.return_value.stdout = "root\n"
        run.return_value.stderr = ""
        result = process_command(
            {
                "command_id": "c1",
                "command_type": "run_script",
                "payload": {
                    "data": {
                        "script": "id -u",
                        "run_as_root": True,
                        "timeout_seconds": 10,
                    }
                },
            },
            ALLOW_ALL,
        )
        assert result["status"] == "completed"
        assert run.call_args.args[0] == ["sudo", "-n", "--", "/bin/sh", "-s"]
        assert run.call_args.kwargs["input"] == "id -u"


class TestBuildStatusUpdatePayload:
    """Tests for ``build_status_update_payload``."""

    def test_minimal_payload(self):
        """Payload with just command_id and status."""
        payload = build_status_update_payload("c1", "completed")
        assert payload["status"] == "completed"
        assert "executed_at" in payload
        datetime.fromisoformat(payload["executed_at"])  # must be parseable

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
