"""Tests for the start_program / stop_program command handlers."""

from unittest.mock import MagicMock, patch

import psutil

from homepot.agent.utils.command_poller import _start_program, _stop_program


class TestStartProgram:
    """Tests for start_program."""

    def test_requires_path(self) -> None:
        """A missing path fails the command."""
        assert _start_program({})["status"] == "failed"
        assert _start_program({"path": "   "})["status"] == "failed"

    def test_launches_in_background(self) -> None:
        """A background launch returns a pid and completes."""
        fake_proc = MagicMock()
        fake_proc.pid = 42
        with patch(
            "homepot.agent.utils.command_poller.subprocess.Popen",
            return_value=fake_proc,
        ) as popen:
            result = _start_program({"path": "app.exe", "args": ["--flag"]})
        assert result["status"] == "completed"
        assert result["result"]["pid"] == 42
        assert result["result"]["path"] == "app.exe"
        assert result["result"].get("timed_out") is not True
        popen.assert_called_once()
        assert popen.call_args.args[0] == ["app.exe", "--flag"]

    def test_not_found(self) -> None:
        """A missing executable fails with not found."""
        with patch(
            "homepot.agent.utils.command_poller.subprocess.Popen",
            side_effect=FileNotFoundError,
        ):
            result = _start_program({"path": "missing.exe"})
        assert result["status"] == "failed"
        assert "not found" in result["result"]["error"]

    def test_wait_returns_returncode(self) -> None:
        """Waiting captures the process returncode."""
        fake_proc = MagicMock()
        fake_proc.pid = 7
        fake_proc.wait.return_value = None
        fake_proc.returncode = 0
        with patch(
            "homepot.agent.utils.command_poller.subprocess.Popen",
            return_value=fake_proc,
        ):
            result = _start_program({"path": "app.exe", "wait": True})
        assert result["status"] == "completed"
        assert result["result"]["returncode"] == 0

    def test_wait_timeout(self) -> None:
        """A wait timeout reports timed_out without failing."""
        import subprocess as _sp  # noqa: S404

        fake_proc = MagicMock()
        fake_proc.pid = 7
        fake_proc.wait.side_effect = _sp.TimeoutExpired(cmd="app.exe", timeout=1)
        with patch(
            "homepot.agent.utils.command_poller.subprocess.Popen",
            return_value=fake_proc,
        ):
            result = _start_program(
                {"path": "app.exe", "wait": True, "timeout_seconds": 1}
            )
        assert result["status"] == "completed"
        assert result["result"].get("timed_out") is True

    def test_working_dir_validation(self) -> None:
        """A missing working directory fails the command."""
        result = _start_program({"path": "app.exe", "working_dir": "/no/such/dir"})
        assert result["status"] == "failed"

    def test_args_string_coercion(self) -> None:
        """A string args value is split into argv entries."""
        fake_proc = MagicMock()
        fake_proc.pid = 1
        with patch(
            "homepot.agent.utils.command_poller.subprocess.Popen",
            return_value=fake_proc,
        ) as popen:
            _start_program({"path": "app.exe", "args": "--flag value"})
        assert popen.call_args.args[0] == ["app.exe", "--flag", "value"]


class TestStopProgram:
    """Tests for stop_program."""

    def test_requires_name_or_pid(self) -> None:
        """A missing name and pid fails the command."""
        assert _stop_program({})["status"] == "failed"

    def test_stop_by_pid(self) -> None:
        """Stop by PID terminates the process and reports killed count."""
        fake_proc = MagicMock()
        fake_proc.name.return_value = "app.exe"
        fake_proc.wait.return_value = None
        with patch(
            "homepot.agent.utils.command_poller.psutil.Process", return_value=fake_proc
        ):
            result = _stop_program({"pid": 123})
        assert result["status"] == "completed"
        assert result["result"]["killed"] == 1
        assert result["result"]["pid"] == 123
        fake_proc.terminate.assert_called_once()

    def test_stop_by_pid_force(self) -> None:
        """Force stop uses kill instead of terminate."""
        fake_proc = MagicMock()
        fake_proc.name.return_value = "app.exe"
        fake_proc.wait.return_value = None
        with patch(
            "homepot.agent.utils.command_poller.psutil.Process", return_value=fake_proc
        ):
            result = _stop_program({"pid": 123, "force": True})
        assert result["status"] == "completed"
        fake_proc.kill.assert_called_once()

    def test_stop_by_pid_not_running(self) -> None:
        """A non-existent PID yields completed with zero kills."""
        with patch(
            "homepot.agent.utils.command_poller.psutil.Process",
            side_effect=psutil.NoSuchProcess(999),
        ):
            result = _stop_program({"pid": 999})
        assert result["status"] == "completed"
        assert result["result"]["killed"] == 0

    def test_stop_by_pid_invalid(self) -> None:
        """Invalid or non-positive PIDs are rejected."""
        assert _stop_program({"pid": "abc"})["status"] == "failed"
        assert _stop_program({"pid": 0})["status"] == "failed"

    def test_stop_critical_process_refused(self) -> None:
        """Critical system processes cannot be stopped by PID."""
        fake_proc = MagicMock()
        fake_proc.name.return_value = "lsass.exe"
        with patch(
            "homepot.agent.utils.command_poller.psutil.Process", return_value=fake_proc
        ):
            result = _stop_program({"pid": 4})
        assert result["status"] == "failed"
        assert "critical" in result["result"]["error"]

    def test_stop_by_name(self) -> None:
        """Stop by name kills matching processes and reports their PIDs."""
        fake_proc = MagicMock()
        fake_proc.info = {"pid": 55, "name": "app.exe"}
        with patch(
            "homepot.agent.utils.command_poller.psutil.process_iter",
            return_value=[fake_proc],
        ):
            result = _stop_program({"name": "app"})
        assert result["status"] == "completed"
        assert result["result"]["killed"] == 1
        assert 55 in result["result"]["pids"]

    def test_stop_by_name_not_found(self) -> None:
        """No matching process yields a completed result with zero kills."""
        with patch(
            "homepot.agent.utils.command_poller.psutil.process_iter", return_value=[]
        ):
            result = _stop_program({"name": "nope.exe"})
        assert result["status"] == "completed"
        assert result["result"]["killed"] == 0

    def test_stop_critical_name_refused(self) -> None:
        """Critical system processes cannot be stopped."""
        result = _stop_program({"name": "lsass.exe"})
        assert result["status"] == "failed"
        assert "critical" in result["result"]["error"]

    def test_stop_invalid_name(self) -> None:
        """Names containing path separators are rejected."""
        assert _stop_program({"name": "bad/name"})["status"] == "failed"
