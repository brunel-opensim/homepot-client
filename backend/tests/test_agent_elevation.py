"""Tests for the scoped OS elevation layer (homepot-ctl)."""

import json
import os
import subprocess  # noqa: S404 - test doubles only
from unittest.mock import patch

import pytest

from homepot.agent.utils import elevation


def _no_env(monkeypatch) -> None:
    monkeypatch.delenv("HOMEPOT_ELEVATION_ROOT", raising=False)
    monkeypatch.delenv("HOMEPOT_CTL_PATH", raising=False)


def _missing_env(monkeypatch, tmp_path) -> None:
    """Redirect elevation paths to entries that do not exist on disk."""
    monkeypatch.setenv("HOMEPOT_ELEVATION_ROOT", str(tmp_path / "missing-root"))
    monkeypatch.setenv("HOMEPOT_CTL_PATH", str(tmp_path / "missing-ctl"))


def _posix_env(monkeypatch) -> None:
    """Ensure os.name is posix for tests that expect macOS/Linux elevation support."""
    monkeypatch.setattr(os, "name", "posix")


def _provisioned_env(monkeypatch, tmp_path):
    """Point the elevation layer at a fake installed helper + drop-in."""
    root = tmp_path / "elevation"
    root.mkdir()
    ctl = root / "homepot-ctl"
    ctl.write_text("#!/bin/sh\nexit 0\n")
    ctl.chmod(0o755)
    dropin_dir = root / "sudoers.d"
    dropin_dir.mkdir()
    (dropin_dir / "homepot").write_text("user ALL=(ALL) NOPASSWD: /tmp/homepot-ctl\n")
    monkeypatch.setenv("HOMEPOT_ELEVATION_ROOT", str(root))
    monkeypatch.setenv("HOMEPOT_CTL_PATH", str(ctl))
    return {"root": root, "ctl": ctl}


@pytest.mark.parametrize(
    "system, expected",
    [
        ("Darwin", True),
        ("Linux", True),
        ("Windows", True),
        ("FreeBSD", False),
    ],
)
def test_is_elevation_supported(monkeypatch, system, expected):
    """Elevation is supported on macOS/Linux/Windows but not FreeBSD."""
    _no_env(monkeypatch)
    _posix_env(monkeypatch)
    with patch("homepot.agent.utils.elevation.platform.system", return_value=system):
        assert elevation.is_elevation_supported() is expected


def test_is_elevation_supported_false_when_os_name_nt(monkeypatch):
    """Windows is elevation-supported when platform.system() returns Windows."""
    _no_env(monkeypatch)
    with patch("homepot.agent.utils.elevation.os.name", "nt"):
        with patch(
            "homepot.agent.utils.elevation.platform.system", return_value="Windows"
        ):
            assert elevation.is_elevation_supported() is True


def test_default_paths(monkeypatch):
    """Paths point at the standard host locations when not redirected."""
    monkeypatch.setattr(os, "name", "posix")
    assert elevation.ctl_path() == os.path.join("/usr/local/homepot", "homepot-ctl")
    assert elevation.dropin_path() == "/etc/sudoers.d/homepot"
    assert elevation.allowlist_path() == "/etc/homepot/allowlist.json"


def test_redirected_paths(monkeypatch, tmp_path):
    """Env overrides redirect all elevation paths (tests/staging/packaging)."""
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setenv("HOMEPOT_ELEVATION_ROOT", str(tmp_path / "root"))
    monkeypatch.setenv("HOMEPOT_CTL_PATH", str(tmp_path / "ctl"))
    assert elevation.ctl_path() == str(tmp_path / "ctl")
    assert elevation.dropin_path() == str(tmp_path / "root" / "sudoers.d" / "homepot")
    assert elevation.allowlist_path() == str(tmp_path / "root" / "allowlist.json")


def test_installed_and_provisioned_state(monkeypatch, tmp_path):
    """Installed/provisioned reflect the presence of the helper and drop-in."""
    _missing_env(monkeypatch, tmp_path)
    _posix_env(monkeypatch)
    with patch("homepot.agent.utils.elevation.platform.system", return_value="Darwin"):
        assert not elevation.is_elevation_installed()
        assert not elevation.is_provisioned()

        env = _provisioned_env(monkeypatch, tmp_path)
        assert elevation.is_elevation_installed()
        assert elevation.is_provisioned()
        (env["root"] / "sudoers.d" / "homepot").unlink()
        assert not elevation.is_provisioned()


class TestProvisionElevation:
    """Provisioning repairs the allowlist when the drop-in still exists."""

    def test_unsupported_platform(self, monkeypatch):
        """Unsupported platforms report os_unsupported."""
        _no_env(monkeypatch)
        _posix_env(monkeypatch)
        with patch(
            "homepot.agent.utils.elevation.platform.system", return_value="FreeBSD"
        ):
            result = elevation.provision_elevation()
        assert result == {"provisioned": False, "reason": "os_unsupported"}

    def test_not_installed(self, monkeypatch, tmp_path):
        """A missing helper/drop-in cannot be repaired autonomously."""
        _missing_env(monkeypatch, tmp_path)
        _posix_env(monkeypatch)
        with patch(
            "homepot.agent.utils.elevation.platform.system", return_value="Darwin"
        ):
            result = elevation.provision_elevation()
        assert result["provisioned"] is False
        assert result["reason"] in {"not_installed", "reinstall_required"}

    def test_dropin_missing_requires_reinstall(self, monkeypatch, tmp_path):
        """A removed drop-in forces the one-time installer (no rule left)."""
        env = _provisioned_env(monkeypatch, tmp_path)
        (env["root"] / "sudoers.d" / "homepot").unlink()
        _posix_env(monkeypatch)
        with patch(
            "homepot.agent.utils.elevation.platform.system", return_value="Darwin"
        ):
            result = elevation.provision_elevation()
        assert result == {"provisioned": False, "reason": "reinstall_required"}

    def test_runs_ensure_allowlist_when_provisioned(self, monkeypatch, tmp_path):
        """A healthy installed layer re-pushes the allowlist via the helper."""
        _provisioned_env(monkeypatch, tmp_path)
        _posix_env(monkeypatch)
        with (
            patch(
                "homepot.agent.utils.elevation.platform.system", return_value="Darwin"
            ),
            patch(
                "homepot.agent.utils.elevation._run_ctl",
                return_value={"ok": True, "stdout": "", "stderr": "", "exit_code": 0},
            ) as run_ctl,
        ):
            result = elevation.provision_elevation()
        assert result == {"provisioned": True, "reason": None}
        assert run_ctl.call_args.args[0] == ["ensure-allowlist"]


class TestDeprovisionElevation:
    """Teardown is autonomous and safe on unsupported/missing states."""

    def test_unsupported_returns_true(self, monkeypatch):
        """Unsupported platforms are treated as already torn down."""
        _no_env(monkeypatch)
        with patch(
            "homepot.agent.utils.elevation.platform.system", return_value="Windows"
        ):
            assert elevation.deprovision_elevation() is True

    def test_not_installed_returns_true(self, monkeypatch, tmp_path):
        """A missing layer is treated as already torn down."""
        _no_env(monkeypatch)
        _posix_env(monkeypatch)
        with patch(
            "homepot.agent.utils.elevation.platform.system", return_value="Darwin"
        ):
            assert elevation.deprovision_elevation() is True

    def test_runs_ctl_deprovision(self, monkeypatch, tmp_path):
        """Deprovision shells out to the helper with no admin prompt."""
        _provisioned_env(monkeypatch, tmp_path)
        _posix_env(monkeypatch)
        with (
            patch(
                "homepot.agent.utils.elevation.platform.system", return_value="Darwin"
            ),
            patch(
                "homepot.agent.utils.elevation._run_ctl",
                return_value={"ok": True, "stdout": "", "stderr": "", "exit_code": 0},
            ) as run_ctl,
        ):
            assert elevation.deprovision_elevation() is True
        assert run_ctl.call_args.args[0] == ["deprovision"]

    def test_failed_deprovision_returns_true(self, monkeypatch, tmp_path):
        """A missing helper is treated as already torn down."""
        env = _provisioned_env(monkeypatch, tmp_path)
        (env["ctl"]).unlink()
        assert elevation.deprovision_elevation() is True


class TestElevatedCommandArgv:
    """The elevated argv is built only for installed, allowlisted ops."""

    def test_windows_returns_none_when_not_installed(self, monkeypatch):
        """Windows returns None when elevation helper is not installed."""
        _no_env(monkeypatch)
        with patch("homepot.agent.utils.elevation.os.name", "nt"):
            with patch(
                "homepot.agent.utils.elevation.platform.system", return_value="Windows"
            ):
                assert elevation.elevated_command_argv("restart") is None

    def test_not_installed_returns_none(self, monkeypatch, tmp_path):
        """A missing layer produces no argv — dispatch fails actionably."""
        _missing_env(monkeypatch, tmp_path)
        _posix_env(monkeypatch)
        with patch(
            "homepot.agent.utils.elevation.platform.system", return_value="Darwin"
        ):
            assert elevation.elevated_command_argv("restart") is None

    def test_allowlisted_op_builds_ctl_argv(self, monkeypatch, tmp_path):
        """Allowlisted power ops run through sudo -n <ctl> run <op>."""
        env = _provisioned_env(monkeypatch, tmp_path)
        _posix_env(monkeypatch)
        with patch(
            "homepot.agent.utils.elevation.platform.system", return_value="Darwin"
        ):
            assert elevation.elevated_command_argv("restart") == [
                "sudo",
                "-n",
                str(env["ctl"]),
                "run",
                "restart",
            ]
            assert elevation.elevated_command_argv("shutdown") == [
                "sudo",
                "-n",
                str(env["ctl"]),
                "run",
                "shutdown",
            ]

    def test_non_allowlisted_op_returns_none(self, monkeypatch, tmp_path):
        """Free-form ops never build an elevated argv."""
        _provisioned_env(monkeypatch, tmp_path)
        _posix_env(monkeypatch)
        with patch(
            "homepot.agent.utils.elevation.platform.system", return_value="Darwin"
        ):
            assert elevation.elevated_command_argv("update_config") is None
            assert elevation.elevated_command_argv("run_command") is None


class TestElevatedExecArgv:
    """Free-form shell execution reuses the scoped helper (`exec` op)."""

    def test_windows_returns_none_when_not_installed(self, monkeypatch):
        """Windows returns None when elevation helper is not installed."""
        _no_env(monkeypatch)
        with patch("homepot.agent.utils.elevation.os.name", "nt"):
            with patch(
                "homepot.agent.utils.elevation.platform.system", return_value="Windows"
            ):
                assert elevation.elevated_exec_argv() is None

    def test_missing_layer_returns_none(self, monkeypatch, tmp_path):
        """A missing helper produces no exec argv — dispatch fails actionably."""
        _missing_env(monkeypatch, tmp_path)
        _posix_env(monkeypatch)
        with patch(
            "homepot.agent.utils.elevation.platform.system", return_value="Darwin"
        ):
            assert elevation.elevated_exec_argv() is None

    def test_installed_layer_builds_exec_argv(self, monkeypatch, tmp_path):
        """Free-form commands run via ``sudo -n <ctl> run exec``."""
        env = _provisioned_env(monkeypatch, tmp_path)
        _posix_env(monkeypatch)
        with patch(
            "homepot.agent.utils.elevation.platform.system", return_value="Darwin"
        ):
            assert elevation.elevated_exec_argv() == [
                "sudo",
                "-n",
                str(env["ctl"]),
                "run",
                "exec",
            ]

    def test_exec_op_allowlisted(self):
        """The free-form exec op is part of the helper's allowlist."""
        assert "exec" in elevation.ALLOWED_OPS


class TestSyncOsElevation:
    """Per-poll reconciliation keeps OS elevation aligned with the grant."""

    def test_unsupported_platform_is_noop(self, monkeypatch):
        """Unsupported platforms never touch the elevation layer."""
        _no_env(monkeypatch)
        _posix_env(monkeypatch)
        with patch(
            "homepot.agent.utils.elevation.platform.system", return_value="FreeBSD"
        ):
            with patch(
                "homepot.agent.utils.elevation.deprovision_elevation"
            ) as deprovision:
                elevation.sync_os_elevation({"root_access": False})
            deprovision.assert_not_called()

    def test_granted_without_dropin_does_not_strip(self, monkeypatch, tmp_path):
        """A grant without an installed drop-in must not be torn down."""
        _no_env(monkeypatch)
        _posix_env(monkeypatch)
        with patch(
            "homepot.agent.utils.elevation.platform.system", return_value="Darwin"
        ):
            with patch(
                "homepot.agent.utils.elevation.deprovision_elevation"
            ) as deprovision:
                elevation.sync_os_elevation({"root_access": True})
            deprovision.assert_not_called()

    def test_revoked_deprovisions(self, monkeypatch, tmp_path):
        """A revoke triggers autonomous teardown even if deprovision is a no-op."""
        _provisioned_env(monkeypatch, tmp_path)
        _posix_env(monkeypatch)
        with patch(
            "homepot.agent.utils.elevation.platform.system", return_value="Darwin"
        ):
            with patch(
                "homepot.agent.utils.elevation.deprovision_elevation",
                return_value=True,
            ) as deprovision:
                elevation.sync_os_elevation({"root_access": False})
        deprovision.assert_called_once()

    def test_granted_repairs_allowlist(self, monkeypatch, tmp_path):
        """A grant re-provisions to repair/stage the allowlist."""
        _provisioned_env(monkeypatch, tmp_path)
        _posix_env(monkeypatch)
        with patch(
            "homepot.agent.utils.elevation.platform.system", return_value="Darwin"
        ):
            with patch(
                "homepot.agent.utils.elevation.provision_elevation"
            ) as provision:
                elevation.sync_os_elevation({"root_access": True})
        provision.assert_called_once()


def test_parse_ctl_status():
    """CTL JSON output is parsed robustly, tolerating non-JSON."""
    assert elevation.parse_ctl_status('{"installed":"yes","provisioned":"yes"}') == {
        "installed": "yes",
        "provisioned": "yes",
    }
    assert elevation.parse_ctl_status("not json") == {}


def _windows_env(monkeypatch, tmp_path):
    """Point the elevation layer at a fake installed Windows helper."""
    root = tmp_path / "elevation"
    root.mkdir()
    ctl = root / "homepot-ctl.ps1"
    ctl.write_text("# helper\n")
    monkeypatch.setenv("HOMEPOT_ELEVATION_ROOT", str(root))
    monkeypatch.setenv("HOMEPOT_CTL_PATH", str(ctl))
    return root


def _completed(argv, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr=stderr)


class TestWindowsTaskState:
    """The agent can tell a missing task from one with a stale action."""

    def test_not_registered_when_query_fails(self):
        """A failed query means the task does not exist."""
        with patch("homepot.agent.utils.elevation.os.name", "nt"):
            with patch(
                "homepot.agent.utils.elevation.subprocess.run",
                return_value=_completed([], 1, stderr="ERROR: not found"),
            ):
                state = elevation.windows_task_state()
        assert state == {"registered": False, "action": "", "current": False}
        assert elevation.is_windows_task_current() is False

    def test_detects_current_action(self):
        """A task running `execute-request` is the current one."""
        stdout = (
            "TaskName:         \\HOMEPOT-Elevation\n"
            "Task To Run:      powershell.exe -NoProfile -NonInteractive "
            '-ExecutionPolicy Bypass -File "C:\\ProgramData\\Homepot\\homepot-ctl.ps1" '
            "execute-request\n"
        )
        with patch("homepot.agent.utils.elevation.os.name", "nt"):
            with patch(
                "homepot.agent.utils.elevation.subprocess.run",
                return_value=_completed([], 0, stdout=stdout),
            ):
                state = elevation.windows_task_state()
                assert elevation.is_windows_task_current() is True
        assert state["registered"] is True
        assert state["current"] is True
        assert "execute-request" in state["action"]

    def test_detects_stale_action(self):
        """A task from an older release is registered but never answers."""
        stdout = (
            "TaskName:         \\HOMEPOT-Elevation\n"
            "Task To Run:      powershell.exe -NoProfile -NonInteractive "
            '-ExecutionPolicy Bypass -File "C:\\ProgramData\\Homepot\\homepot-ctl.ps1"\n'
        )
        with patch("homepot.agent.utils.elevation.os.name", "nt"):
            with patch(
                "homepot.agent.utils.elevation.subprocess.run",
                return_value=_completed([], 0, stdout=stdout),
            ):
                state = elevation.windows_task_state()
        assert state["registered"] is True
        assert state["current"] is False
        assert elevation.is_windows_task_current() is False


class TestRunElevatedWindows:
    """The Windows request/result protocol is diagnosed, not just timed out."""

    def test_reads_result_written_with_a_utf8_bom(self, monkeypatch, tmp_path):
        """Windows PowerShell writes UTF-8 with a BOM; the result still parses."""
        root = _windows_env(monkeypatch, tmp_path)

        def fake_run(argv, **_kwargs):
            return _completed(argv, 0)

        def fake_sleep(_seconds):
            request = json.loads((root / "elevation-request.json").read_text())
            payload = {
                "request_id": request["request_id"],
                "exit_code": 0,
                "stdout": "nt authority\\system",
                "stderr": "",
            }
            (root / f"elevation-result-{request['request_id']}.json").write_bytes(
                b"\xef\xbb\xbf" + json.dumps(payload).encode("utf-8")
            )

        with (
            patch("homepot.agent.utils.elevation.os.name", "nt"),
            patch(
                "homepot.agent.utils.elevation.platform.system",
                return_value="Windows",
            ),
            patch("homepot.agent.utils.elevation.subprocess.run", side_effect=fake_run),
            patch("homepot.agent.utils.elevation.time.sleep", side_effect=fake_sleep),
        ):
            outcome = elevation.run_elevated("exec", "whoami", timeout=5)

        assert outcome["ok"] is True
        assert outcome["stdout"].strip() == "nt authority\\system"

    def test_trigger_failure_is_reported(self, monkeypatch, tmp_path):
        """A failing `schtasks /run` is surfaced instead of a bare timeout."""
        _windows_env(monkeypatch, tmp_path)
        with (
            patch("homepot.agent.utils.elevation.os.name", "nt"),
            patch(
                "homepot.agent.utils.elevation.platform.system",
                return_value="Windows",
            ),
            patch(
                "homepot.agent.utils.elevation.subprocess.run",
                return_value=_completed([], 1, stderr="ERROR: access denied"),
            ),
        ):
            outcome = elevation.run_elevated("exec", "whoami", timeout=5)

        assert outcome["ok"] is False
        assert "could not trigger elevation task" in outcome["error"]
        assert "access denied" in outcome["error"]

    def test_timeout_reports_that_the_task_never_ran(self, monkeypatch, tmp_path):
        """A pending request means the scheduled task never ran the helper."""
        root = _windows_env(monkeypatch, tmp_path)

        def fake_run(argv, **_kwargs):
            if "/fo" in argv:
                return _completed(argv, 1, stderr="ERROR: not found")
            return _completed(argv, 0)

        with (
            patch("homepot.agent.utils.elevation.os.name", "nt"),
            patch(
                "homepot.agent.utils.elevation.platform.system",
                return_value="Windows",
            ),
            patch("homepot.agent.utils.elevation.subprocess.run", side_effect=fake_run),
            patch("homepot.agent.utils.elevation.time.sleep"),
        ):
            outcome = elevation.run_elevated("exec", "whoami", timeout=0.05)

        assert outcome["ok"] is False
        assert "still pending" in outcome["error"]
        assert "is not registered" in outcome["error"]
        # The pending request must not be left for a later task run to execute.
        assert not (root / "elevation-request.json").exists()

    def test_stale_request_is_replaced(self, monkeypatch, tmp_path):
        """A request left over from an earlier attempt is not executed later."""
        root = _windows_env(monkeypatch, tmp_path)
        (root / "elevation-request.json").write_text('{"request_id": "stale"}')
        seen = {}

        def fake_run(argv, **_kwargs):
            if "/fo" in argv:
                return _completed(argv, 1, stderr="ERROR: not found")
            # The task is triggered after the request is written, so this is
            # where the request the agent actually sent can be observed.
            seen["request"] = json.loads((root / "elevation-request.json").read_text())
            return _completed(argv, 0)

        with (
            patch("homepot.agent.utils.elevation.os.name", "nt"),
            patch(
                "homepot.agent.utils.elevation.platform.system",
                return_value="Windows",
            ),
            patch("homepot.agent.utils.elevation.subprocess.run", side_effect=fake_run),
            patch("homepot.agent.utils.elevation.time.sleep"),
        ):
            elevation.run_elevated("exec", "whoami", timeout=0.05)

        assert seen["request"]["request_id"] != "stale"
        assert seen["request"]["op"] == "exec"
        assert seen["request"]["script"] == "whoami"
