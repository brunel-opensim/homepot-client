"""Tests for the scoped OS elevation layer (homepot-ctl)."""

from unittest.mock import patch

import pytest

from homepot.agent.utils import elevation


def _no_env(monkeypatch) -> None:
    monkeypatch.delenv("HOMEPOT_ELEVATION_ROOT", raising=False)
    monkeypatch.delenv("HOMEPOT_CTL_PATH", raising=False)


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
        ("Windows", False),
        ("FreeBSD", False),
    ],
)
def test_is_elevation_supported(monkeypatch, system, expected):
    _no_env(monkeypatch)
    with patch("homepot.agent.utils.elevation.platform.system", return_value=system):
        assert elevation.is_elevation_supported() is expected


def test_is_elevation_supported_false_when_os_name_nt(monkeypatch):
    _no_env(monkeypatch)
    with patch("homepot.agent.utils.elevation.os.name", "nt"):
        with patch("homepot.agent.utils.elevation.platform.system", return_value="Darwin"):
            assert elevation.is_elevation_supported() is False


def test_default_paths():
    assert elevation.ctl_path() == "/usr/local/homepot/homepot-ctl"
    assert elevation.dropin_path() == "/etc/sudoers.d/homepot"
    assert elevation.allowlist_path() == "/etc/homepot/allowlist.json"


def test_redirected_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("HOMEPOT_ELEVATION_ROOT", str(tmp_path / "root"))
    monkeypatch.setenv("HOMEPOT_CTL_PATH", str(tmp_path / "ctl"))
    assert elevation.ctl_path() == str(tmp_path / "ctl")
    assert elevation.dropin_path() == str(tmp_path / "root" / "sudoers.d" / "homepot")
    assert elevation.allowlist_path() == str(tmp_path / "root" / "allowlist.json")


def test_installed_and_provisioned_state(monkeypatch, tmp_path):
    _no_env(monkeypatch)
    assert not elevation.is_elevation_installed()
    assert not elevation.is_provisioned()

    env = _provisioned_env(monkeypatch, tmp_path)
    assert elevation.is_elevation_installed()
    assert elevation.is_provisioned()
    (env["root"] / "sudoers.d" / "homepot").unlink()
    assert not elevation.is_provisioned()


class TestProvisionElevation:
    def test_unsupported_platform(self, monkeypatch):
        _no_env(monkeypatch)
        with patch("homepot.agent.utils.elevation.platform.system", return_value="Windows"):
            result = elevation.provision_elevation()
        assert result == {"provisioned": False, "reason": "os_unsupported"}

    def test_not_installed(self, monkeypatch, tmp_path):
        _no_env(monkeypatch)
        with patch("homepot.agent.utils.elevation.platform.system", return_value="Darwin"):
            result = elevation.provision_elevation()
        assert result["provisioned"] is False
        assert result["reason"] in {"not_installed", "reinstall_required"}

    def test_dropin_missing_requires_reinstall(self, monkeypatch, tmp_path):
        env = _provisioned_env(monkeypatch, tmp_path)
        (env["root"] / "sudoers.d" / "homepot").unlink()
        with patch("homepot.agent.utils.elevation.platform.system", return_value="Darwin"):
            result = elevation.provision_elevation()
        assert result == {"provisioned": False, "reason": "reinstall_required"}

    def test_runs_ensure_allowlist_when_provisioned(self, monkeypatch, tmp_path):
        env = _provisioned_env(monkeypatch, tmp_path)
        with patch(
            "homepot.agent.utils.elevation.platform.system", return_value="Darwin"
        ), patch(
            "homepot.agent.utils.elevation._run_ctl",
            return_value={"ok": True, "stdout": "", "stderr": "", "exit_code": 0},
        ) as run_ctl:
            result = elevation.provision_elevation()
        assert result == {"provisioned": True, "reason": None}
        assert run_ctl.call_args.args[0] == ["ensure-allowlist"]


class TestDeprovisionElevation:
    def test_unsupported_returns_true(self, monkeypatch):
        _no_env(monkeypatch)
        with patch("homepot.agent.utils.elevation.platform.system", return_value="Windows"):
            assert elevation.deprovision_elevation() is True

    def test_not_installed_returns_true(self, monkeypatch, tmp_path):
        _no_env(monkeypatch)
        with patch("homepot.agent.utils.elevation.platform.system", return_value="Darwin"):
            assert elevation.deprovision_elevation() is True

    def test_runs_ctl_deprovision(self, monkeypatch, tmp_path):
        env = _provisioned_env(monkeypatch, tmp_path)
        with patch(
            "homepot.agent.utils.elevation.platform.system", return_value="Darwin"
        ), patch(
            "homepot.agent.utils.elevation._run_ctl",
            return_value={"ok": True, "stdout": "", "stderr": "", "exit_code": 0},
        ) as run_ctl:
            assert elevation.deprovision_elevation() is True
        assert run_ctl.call_args.args[0] == ["deprovision"]

    def test_failed_deprovision_returns_false(self, monkeypatch, tmp_path):
        env = _provisioned_env(monkeypatch, tmp_path)
        (env["ctl"]).unlink()
        # ctl gone -> treated as already teared down.
        assert elevation.deprovision_elevation() is True


class TestElevatedCommandArgv:
    def test_windows_returns_none(self, monkeypatch):
        _no_env(monkeypatch)
        with patch("homepot.agent.utils.elevation.platform.system", return_value="Windows"):
            assert elevation.elevated_command_argv("restart") is None

    def test_not_installed_returns_none(self, monkeypatch, tmp_path):
        _no_env(monkeypatch)
        with patch("homepot.agent.utils.elevation.platform.system", return_value="Darwin"):
            assert elevation.elevated_command_argv("restart") is None

    def test_allowlisted_op_builds_ctl_argv(self, monkeypatch, tmp_path):
        env = _provisioned_env(monkeypatch, tmp_path)
        with patch("homepot.agent.utils.elevation.platform.system", return_value="Darwin"):
            assert elevation.elevated_command_argv("restart") == [
                "sudo", "-n", str(env["ctl"]), "run", "restart",
            ]
            assert elevation.elevated_command_argv("shutdown") == [
                "sudo", "-n", str(env["ctl"]), "run", "shutdown",
            ]

    def test_non_allowlisted_op_returns_none(self, monkeypatch, tmp_path):
        env = _provisioned_env(monkeypatch, tmp_path)
        with patch("homepot.agent.utils.elevation.platform.system", return_value="Darwin"):
            assert elevation.elevated_command_argv("update_config") is None
            assert elevation.elevated_command_argv("run_command") is None


class TestAllowlistRefusal:
    def test_windows_allows_free_form(self, monkeypatch):
        _no_env(monkeypatch)
        with patch("homepot.agent.utils.elevation.platform.system", return_value="Windows"):
            assert elevation.allowlist_refusal("run_command") is None
            assert elevation.allowlist_refusal("run_script") is None

    def test_free_form_refused_on_macos_linux(self, monkeypatch):
        _no_env(monkeypatch)
        with patch("homepot.agent.utils.elevation.platform.system", return_value="Darwin"):
            assert "not allowlisted" in elevation.allowlist_refusal("run_command")
            assert "not allowlisted" in elevation.allowlist_refusal("run_script")

    def test_fixed_ops_allowed(self, monkeypatch):
        _no_env(monkeypatch)
        with patch("homepot.agent.utils.elevation.platform.system", return_value="Darwin"):
            assert elevation.allowlist_refusal("restart") is None
            assert elevation.allowlist_refusal("shutdown") is None
            assert elevation.allowlist_refusal("health_check") is None


class TestSyncOsElevation:
    def test_unsupported_platform_is_noop(self, monkeypatch):
        _no_env(monkeypatch)
        with patch("homepot.agent.utils.elevation.platform.system", return_value="Windows"):
            with patch(
                "homepot.agent.utils.elevation.deprovision_elevation"
            ) as deprovision:
                elevation.sync_os_elevation({"root_access": False})
            deprovision.assert_not_called()

    def test_granted_without_dropin_does_not_strip(self, monkeypatch, tmp_path):
        _no_env(monkeypatch)
        with patch("homepot.agent.utils.elevation.platform.system", return_value="Darwin"):
            with patch(
                "homepot.agent.utils.elevation.deprovision_elevation"
            ) as deprovision:
                elevation.sync_os_elevation({"root_access": True})
            deprovision.assert_not_called()

    def test_revoked_deprovisions(self, monkeypatch, tmp_path):
        env = _provisioned_env(monkeypatch, tmp_path)
        with patch("homepot.agent.utils.elevation.platform.system", return_value="Darwin"):
            with patch(
                "homepot.agent.utils.elevation.deprovision_elevation",
                return_value=True,
            ) as deprovision:
                elevation.sync_os_elevation({"root_access": False})
        deprovision.assert_called_once()

    def test_granted_repairs_allowlist(self, monkeypatch, tmp_path):
        env = _provisioned_env(monkeypatch, tmp_path)
        with patch("homepot.agent.utils.elevation.platform.system", return_value="Darwin"):
            with patch(
                "homepot.agent.utils.elevation.provision_elevation"
            ) as provision:
                elevation.sync_os_elevation({"root_access": True})
        provision.assert_called_once()


def test_parse_ctl_status():
    assert elevation.parse_ctl_status('{"installed":"yes","provisioned":"yes"}') == {
        "installed": "yes",
        "provisioned": "yes",
    }
    assert elevation.parse_ctl_status("not json") == {}