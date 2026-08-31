"""Tests for command polling and push wake-up utilities."""

import os
import sys
from datetime import datetime
from unittest.mock import patch

import pytest

from homepot.agent.utils.command_poller import (
    COMMAND_TYPES,
    build_status_report,
    build_status_update_payload,
    parse_pending_commands,
    process_command,
    required_permissions_for_command,
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


# The command-builders below assert POSIX sudo command construction. On Windows
# the agent (correctly) builds platform-native commands instead (no sudo;
# ``shutdown /r /t 0``; ``powershell -Command -``), so these assertions are
# POSIX-only and are skipped on Windows.
skip_if_windows = pytest.mark.skipif(
    os.name == "nt" or sys.platform == "win32",
    reason="asserts POSIX sudo command construction",
)


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

    @skip_if_windows
    @patch("homepot.agent.utils.command_poller.subprocess.run")
    def test_restart_allowed_with_root_access(self, run):
        """Restart succeeds when root_access is granted (sudo shutdown -r)."""
        run.return_value.returncode = 0
        run.return_value.stdout = ""
        run.return_value.stderr = ""
        result = process_command(
            {"command_id": "c1", "command_type": "restart"}, ALLOW_ALL
        )
        assert result["status"] == "completed"
        assert run.call_args.args[0] == ["sudo", "-n", "--", "shutdown", "-r", "now"]

    def test_restart_denied_without_root_access(self):
        """Restart fails when root_access is denied."""
        result = process_command(
            {"command_id": "c1", "command_type": "restart"}, DENY_ALL
        )
        assert result["status"] == "failed"
        assert "denied" in result["result"]["error"]

    @skip_if_windows
    @patch("homepot.agent.utils.command_poller.subprocess.run")
    def test_shutdown_allowed_with_root_access(self, run):
        """Shutdown succeeds when root_access is granted (sudo shutdown -h)."""
        run.return_value.returncode = 0
        run.return_value.stdout = ""
        run.return_value.stderr = ""
        result = process_command(
            {"command_id": "c1", "command_type": "shutdown"}, ALLOW_ALL
        )
        assert result["status"] == "completed"
        assert run.call_args.args[0] == ["sudo", "-n", "--", "shutdown", "-h", "now"]

    def test_shutdown_denied_without_root_access(self):
        """Shutdown fails when root_access is denied."""
        result = process_command(
            {"command_id": "c1", "command_type": "shutdown"}, DENY_ALL
        )
        assert result["status"] == "failed"
        assert "denied" in result["result"]["error"]

    def test_update_config_allowed_with_root_access(self):
        """Update_config succeeds when root_access is granted."""
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

    @patch("homepot.agent.utils.command_poller.platform.system")
    @patch("homepot.agent.utils.command_poller.subprocess.run")
    def test_update_config_brightness_applies_os_action(self, run, system):
        """A known config key (brightness) runs the platform OS action."""
        system.return_value = "Darwin"
        run.return_value.returncode = 0
        run.return_value.stdout = ""
        run.return_value.stderr = ""
        result = process_command(
            {
                "command_id": "c1",
                "command_type": "update_config",
                "payload": {"data": {"brightness": 75}},
            },
            ALLOW_ALL,
        )
        assert result["status"] == "completed"
        assert run.call_args.args[0] == ["brightness", "75"]
        assert result["result"]["results"]["brightness"]["status"] == "applied"

    @patch("homepot.agent.utils.command_poller.platform.system")
    @patch("homepot.agent.utils.command_poller.subprocess.run")
    def test_update_config_brightness_failure_is_reported(self, run, system):
        """A failed OS action is reported as failed, not silently dropped."""
        system.return_value = "Linux"
        run.return_value.returncode = 1
        run.return_value.stdout = ""
        run.return_value.stderr = "brightnessctl: no such device"
        result = process_command(
            {
                "command_id": "c1",
                "command_type": "update_config",
                "payload": {"data": {"brightness": 50}},
            },
            ALLOW_ALL,
        )
        assert result["status"] == "completed"
        assert result["result"]["results"]["brightness"]["status"] == "failed"
        assert "no such device" in result["result"]["results"]["brightness"]["stderr"]

    def test_update_config_without_payload(self):
        """Update_config command with no payload returns empty applied_keys."""
        result = process_command(
            {"command_id": "c1", "command_type": "update_config"}, ALLOW_ALL
        )
        assert result["status"] == "completed"
        assert result["result"]["applied_keys"] == []

    @patch("homepot.agent.utils.telemetry.collect_system_telemetry")
    def test_health_check_reports_per_test_results(self, telemetry):
        """Health check reports pass/fail per requested test."""
        telemetry.return_value = {
            "cpu_usage": 12.0,
            "memory_usage": 45.0,
            "disk_usage": 95.0,
            "uptime_seconds": 1000,
        }
        result = process_command(
            {
                "command_id": "c1",
                "command_type": "health_check",
                "payload": {"data": {"tests": ["cpu", "memory", "storage"]}},
            },
            ALLOW_ALL,
        )
        assert result["status"] == "failed"
        results = result["result"]["results"]
        assert results["cpu"]["status"] == "pass"
        assert results["memory"]["status"] == "pass"
        assert results["storage"]["status"] == "fail"

    def test_list_processes_returns_snapshot(self):
        """List processes returns a bounded, sorted snapshot."""
        result = process_command(
            {
                "command_id": "c1",
                "command_type": "list_processes",
                "payload": {"data": {"max_results": 5, "sort_by": "memory"}},
            },
            ALLOW_ALL,
        )
        assert result["status"] == "completed"
        assert "processes" in result["result"]
        assert result["result"]["count"] >= 0

    @patch("homepot.agent.utils.command_poller.psutil.net_connections")
    def test_list_connections_filters_by_state(self, net_connections):
        """List connections filters to the requested state."""
        import types

        laddr = types.SimpleNamespace(ip="127.0.0.1", port=9000)
        raddr = types.SimpleNamespace(ip="10.0.0.5", port=443)
        net_connections.return_value = [
            types.SimpleNamespace(
                pid=1, status="ESTABLISHED", laddr=laddr, raddr=raddr
            ),
            types.SimpleNamespace(pid=2, status="LISTEN", laddr=laddr, raddr=None),
        ]
        result = process_command(
            {
                "command_id": "c1",
                "command_type": "list_connections",
                "payload": {"data": {"filter_state": "ESTABLISHED", "limit": 10}},
            },
            ALLOW_ALL,
        )
        assert result["status"] == "completed"
        assert result["result"]["count"] == 1
        assert result["result"]["connections"][0]["pid"] == 1

    def test_scan_filesystem_walks_bounded_dirs(self, tmp_path):
        """Scan filesystem returns entries within the requested depth."""
        (tmp_path / "a").mkdir()
        (tmp_path / "a" / "b").mkdir()
        (tmp_path / "file1.txt").write_text("x")
        (tmp_path / "a" / "file2.txt").write_text("yy")
        result = process_command(
            {
                "command_id": "c1",
                "command_type": "scan_filesystem",
                "payload": {"data": {"path": str(tmp_path), "max_depth": 1}},
            },
            ALLOW_ALL,
        )
        assert result["status"] == "completed"
        paths = {e["path"] for e in result["result"]["entries"]}
        assert str(tmp_path / "a") in paths
        assert str(tmp_path / "file1.txt") in paths

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

    def test_run_command_requires_root_access(self):
        """Command execution is denied without the root_access grant."""
        result = process_command(
            {
                "command_id": "c1",
                "command_type": "run_command",
                "payload": {"data": {"command": "whoami"}},
            },
            DENY_ALL,
        )
        assert result["status"] == "failed"
        assert "root_access" in result["result"]["error"]

    @skip_if_windows
    @patch("homepot.agent.utils.command_poller.subprocess.run")
    def test_run_command_allowed_with_root_access(self, run):
        """Command execution runs via non-interactive sudo once root is granted."""
        run.return_value.returncode = 0
        run.return_value.stdout = "root\n"
        run.return_value.stderr = ""
        result = process_command(
            {
                "command_id": "c1",
                "command_type": "run_command",
                "payload": {"data": {"command": "id -u", "timeout_seconds": 10}},
            },
            ALLOW_ALL,
        )
        assert result["status"] == "completed"
        assert run.call_args.args[0] == ["sudo", "-n", "--", "id", "-u"]

    def test_scan_filesystem_requires_root_access(self):
        """Filesystem scans are denied without the root_access grant."""
        result = process_command(
            {"command_id": "c1", "command_type": "scan_filesystem"}, DENY_ALL
        )
        assert result["status"] == "failed"
        assert "root_access" in result["result"]["error"]

    def test_health_check_requires_command_execution(self):
        """Diagnostics are a manage-tier command, denied without the manage grant."""
        result = process_command(
            {"command_id": "c1", "command_type": "health_check"},
            {**ALLOW_ALL, "command_execution": False},
        )
        assert result["status"] == "failed"
        assert "command_execution" in result["result"]["error"]

    @skip_if_windows
    @patch("homepot.agent.utils.command_poller.subprocess.run")
    def test_script_runs_with_non_interactive_sudo(self, run):
        """Scripts always run through non-interactive sudo once root is granted."""
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
                        "timeout_seconds": 10,
                    }
                },
            },
            ALLOW_ALL,
        )
        assert result["status"] == "completed"
        assert run.call_args.args[0] == ["sudo", "-n", "--", "/bin/sh", "-s"]
        assert run.call_args.kwargs["input"] == "id -u"

    def test_script_with_embedded_sudo_requires_root_grant(self):
        """Embedded sudo in a script still requires the root_access grant."""
        result = process_command(
            {
                "command_id": "c1",
                "command_type": "run_script",
                "payload": {"data": {"script": "echo ready\nsudo id"}},
            },
            {**ALLOW_ALL, "root_access": False},
        )
        assert result["status"] == "failed"
        assert "root_access" in result["result"]["error"]

    @patch("homepot.agent.utils.command_poller.os.name", "nt")
    @patch("homepot.agent.utils.command_poller.platform.system")
    @patch("homepot.agent.utils.command_poller.subprocess.run")
    def test_run_command_windows_no_sudo(self, run, system):
        """On Windows run_command runs without a sudo prefix."""
        system.return_value = "Windows"
        run.return_value.returncode = 0
        run.return_value.stdout = "hello\n"
        run.return_value.stderr = ""
        result = process_command(
            {
                "command_id": "c1",
                "command_type": "run_command",
                "payload": {"data": {"command": "echo hello"}},
            },
            ALLOW_ALL,
        )
        assert result["status"] == "completed"
        assert run.call_args.args[0] == ["echo", "hello"]

    @patch("homepot.agent.utils.command_poller.os.name", "nt")
    @patch("homepot.agent.utils.command_poller.platform.system")
    @patch("homepot.agent.utils.command_poller.subprocess.run")
    def test_restart_windows_uses_shutdown_exe(self, run, system):
        """On Windows restart uses the shutdown.exe tool directly."""
        system.return_value = "Windows"
        run.return_value.returncode = 0
        run.return_value.stdout = ""
        run.return_value.stderr = ""
        result = process_command(
            {"command_id": "c1", "command_type": "restart"}, ALLOW_ALL
        )
        assert result["status"] == "completed"
        assert run.call_args.args[0][0] == "shutdown"
        assert "/r" in run.call_args.args[0]

    @patch("homepot.agent.utils.command_poller.os.name", "nt")
    @patch("homepot.agent.utils.command_poller.platform.system")
    @patch("homepot.agent.utils.command_poller.subprocess.run")
    def test_script_windows_uses_powershell(self, run, system):
        """On Windows scripts run through PowerShell, not /bin/sh."""
        system.return_value = "Windows"
        run.return_value.returncode = 0
        run.return_value.stdout = ""
        run.return_value.stderr = ""
        result = process_command(
            {
                "command_id": "c1",
                "command_type": "run_script",
                "payload": {"data": {"script": "Get-Date"}},
            },
            ALLOW_ALL,
        )
        assert result["status"] == "completed"
        argv = run.call_args.args[0]
        assert argv[0] == "powershell"
        assert run.call_args.kwargs["input"] == "Get-Date"


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


class TestStatusRequest:
    """Tests for the ``status_request`` command and status report builder."""

    def test_status_request_is_supported(self):
        """The backend accepts the status_request command type."""
        assert "status_request" in COMMAND_TYPES

    def test_status_request_requires_no_permission(self):
        """A status check is read-only and needs no device permission grant."""
        assert required_permissions_for_command("status_request") == []

    def test_build_status_report_returns_snapshot(self):
        """The report contains the expected live device fields."""
        report = build_status_report(
            {
                "device_id": "DEVICE-TEST-0001",
                "device_name": "test-pos",
                "device_type": "pos_terminal",
                "os_details": "macOS 14",
            }
        )
        assert report["device_id"] == "DEVICE-TEST-0001"
        assert report["device_name"] == "test-pos"
        assert report["status"] == "online"
        assert report["connectivity_state"] == "online"
        assert isinstance(report["uptime_seconds"], int)
        assert isinstance(report["cpu_usage"], float)
        assert isinstance(report["memory_usage"], float)
        assert isinstance(report["disk_usage"], float)
        assert "hostname" in report
        assert "timestamp" in report


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
