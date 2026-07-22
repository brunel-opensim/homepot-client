"""Tests for persistent device identity management.

Covers:
- get_or_create_device_id()
- get_device_id()
- reset_device_id()
- identity_path()
- identity_dir()
- Fallback to machine-id when identity dir is unwritable
- Windows-specific identity (WindowsCredManager placeholder)
"""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from homepot.agent.identity import (
    _generate_uuid_identity,
    _machine_id_identity,
    _platform_machine_id,
    _windows_machine_id_identity,
    get_device_id,
    get_or_create_device_id,
    identity_dir,
    identity_path,
    reset_device_id,
)

# ============================================================================
# Unit tests for internal helpers
# ============================================================================


class TestGenerateUuidIdentity:
    """Tests for the _generate_uuid_identity helper."""

    def test_returns_string_with_device_prefix(self):
        """Generated identity starts with 'device-' and has sufficient length."""
        ident = _generate_uuid_identity()
        assert ident.startswith("device-")
        assert len(ident) > len("device-")

    def test_returns_unique_values(self):
        """Each call to _generate_uuid_identity returns a unique value."""
        id1 = _generate_uuid_identity()
        id2 = _generate_uuid_identity()
        assert id1 != id2


class TestMachineIdIdentity:
    """Tests for the _machine_id_identity helper."""

    def test_returns_none_when_no_machine_id(self):
        """Returns None when /etc/machine-id does not exist."""
        with patch("homepot.agent.identity.Path.exists", return_value=False):
            result = _machine_id_identity()
            assert result is None

    def test_returns_none_on_empty_machine_id(self):
        """Returns None when machine-id file is empty."""
        with patch("homepot.agent.identity.Path.exists", return_value=True):
            with patch("homepot.agent.identity.Path.read_text", return_value=""):
                result = _machine_id_identity()
                assert result is None

    def test_returns_deterministic_id_from_machine_id(self):
        """A known machine-id produces a deterministic device identity."""
        fake_id = "abc123def456"
        expected_prefix = "device-"
        with patch("homepot.agent.identity.Path.exists", return_value=True):
            with patch("homepot.agent.identity.Path.read_text", return_value=fake_id):
                result = _machine_id_identity()
                assert result is not None
                assert result.startswith(expected_prefix)
                assert len(result) > len(expected_prefix)

    def test_same_machine_id_gives_same_device_id(self):
        """The same machine-id always yields the same device identity."""
        fake_id = "same-machine-id"
        with patch("homepot.agent.identity.Path.exists", return_value=True):
            with patch("homepot.agent.identity.Path.read_text", return_value=fake_id):
                r1 = _machine_id_identity()
                r2 = _machine_id_identity()
                assert r1 == r2


class TestWindowsMachineIdIdentity:
    """Tests for the _windows_machine_id_identity helper."""

    def test_returns_none_when_powershell_fails(self):
        """Returns None when the PowerShell command returns a non-zero exit code."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("homepot.agent.identity.subprocess.run", return_value=mock_result):
            result = _windows_machine_id_identity()
            assert result is None

    def test_returns_none_on_empty_output(self):
        """Returns None when PowerShell returns empty output."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        with patch("homepot.agent.identity.subprocess.run", return_value=mock_result):
            result = _windows_machine_id_identity()
            assert result is None

    def test_returns_none_on_timeout(self):
        """Returns None when the PowerShell command times out."""
        with patch(
            "homepot.agent.identity.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="powershell", timeout=10),
        ):
            result = _windows_machine_id_identity()
            assert result is None

    def test_returns_none_on_file_not_found(self):
        """Returns None when PowerShell is not available."""
        with patch(
            "homepot.agent.identity.subprocess.run",
            side_effect=FileNotFoundError("No such file"),
        ):
            result = _windows_machine_id_identity()
            assert result is None

    def test_returns_deterministic_id_from_uuid(self):
        """A known system UUID produces a deterministic device identity."""
        fake_uuid = "12345678-1234-1234-1234-123456789abc"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = fake_uuid + "\n"
        with patch("homepot.agent.identity.subprocess.run", return_value=mock_result):
            result = _windows_machine_id_identity()
            assert result is not None
            assert result.startswith("device-")
            assert len(result) > len("device-")

    def test_same_uuid_gives_same_device_id(self):
        """The same system UUID always yields the same device identity."""
        fake_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = fake_uuid + "\n"
        with patch("homepot.agent.identity.subprocess.run", return_value=mock_result):
            r1 = _windows_machine_id_identity()
            r2 = _windows_machine_id_identity()
            assert r1 == r2


class TestPlatformMachineId:
    """Tests for the _platform_machine_id dispatcher."""

    def test_delegates_to_windows_on_win32(self):
        """On Windows, _platform_machine_id calls _windows_machine_id_identity."""
        with patch("homepot.agent.identity._is_windows", return_value=True):
            with patch(
                "homepot.agent.identity._windows_machine_id_identity",
                return_value="device-windows-id",
            ):
                result = _platform_machine_id()
                assert result == "device-windows-id"

    def test_delegates_to_linux_on_posix(self):
        """On Linux, _platform_machine_id calls _machine_id_identity."""
        with patch("homepot.agent.identity._is_windows", return_value=False):
            with patch(
                "homepot.agent.identity._machine_id_identity",
                return_value="device-linux-id",
            ):
                result = _platform_machine_id()
                assert result == "device-linux-id"


# ============================================================================
# Integration tests with temporary identity directories
# ============================================================================


@pytest.fixture
def tmp_identity_dir(monkeypatch):
    """Redirect identity storage to a temp directory.

    Works cross-platform by mocking ``_get_identity_dir`` to return
    the temp dir directly.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        monkeypatch.setattr(
            "homepot.agent.identity._get_identity_dir", lambda: tmp_path
        )
        yield tmp_path


class TestGetOrCreateDeviceId:
    """Tests for get_or_create_device_id with a temporary directory."""

    def test_creates_and_returns_device_id(self, tmp_identity_dir):
        """Creates a new UUID-based identity and persists it to disk."""
        device_id = get_or_create_device_id()
        assert device_id.startswith("device-")
        id_file = tmp_identity_dir / "identity"
        assert id_file.exists()
        assert id_file.read_text("utf-8").strip() == device_id

    def test_returns_same_id_on_second_call(self, tmp_identity_dir):
        """Calling get_or_create_device_id twice returns the same ID."""
        first = get_or_create_device_id()
        second = get_or_create_device_id()
        assert first == second

    def test_returns_existing_id_from_file(self, tmp_identity_dir):
        """If an identity file already exists, its content is returned."""
        id_file = tmp_identity_dir / "identity"
        id_file.write_text("device-preexisting-id\n", encoding="utf-8")
        device_id = get_or_create_device_id()
        assert device_id == "device-preexisting-id"

    def test_id_file_has_correct_permissions(self, tmp_identity_dir):
        """Identity file is created with 0o644 permissions."""
        if sys.platform == "win32":
            pytest.skip("Windows does not support Unix file permissions")
        get_or_create_device_id()
        id_file = tmp_identity_dir / "identity"
        mode = os.stat(id_file).st_mode & 0o777
        assert mode == 0o644, f"Expected 0o644, got {oct(mode)}"

    def test_skips_chmod_on_windows(self, tmp_identity_dir, monkeypatch):
        """On Windows, chmod is not called when persisting the identity."""
        monkeypatch.setattr("homepot.agent.identity._is_windows", lambda: True)
        monkeypatch.setattr("homepot.agent.identity._platform_machine_id", lambda: None)
        device_id = get_or_create_device_id()
        id_file = tmp_identity_dir / "identity"
        assert id_file.exists()
        assert id_file.read_text("utf-8").strip() == device_id

    def test_falls_back_to_hardware_id_when_dir_unwritable(self, monkeypatch):
        """When the identity directory cannot be written, falls back to hardware ID."""
        monkeypatch.setattr(
            "homepot.agent.identity._identity_file_path",
            lambda: Path("/nonexistent/homepot/identity"),
        )
        monkeypatch.setattr(
            "homepot.agent.identity._platform_machine_id",
            lambda: "device-hardware-fallback",
        )
        result = get_or_create_device_id()
        assert result == "device-hardware-fallback"


class TestGetDeviceId:
    """Tests for get_device_id (read-only, no creation)."""

    def test_returns_none_when_no_identity(self, tmp_identity_dir, monkeypatch):
        """Returns None when no identity file or hardware ID exists."""
        monkeypatch.setattr("homepot.agent.identity._platform_machine_id", lambda: None)
        assert get_device_id() is None

    def test_returns_id_from_file(self, tmp_identity_dir, monkeypatch):
        """Returns the device ID from an existing identity file."""
        monkeypatch.setattr("homepot.agent.identity._platform_machine_id", lambda: None)
        id_file = tmp_identity_dir / "identity"
        id_file.write_text("device-existing\n", encoding="utf-8")
        assert get_device_id() == "device-existing"

    def test_returns_none_on_corrupted_file(self, tmp_identity_dir, monkeypatch):
        """Returns None when the identity file is empty."""
        monkeypatch.setattr("homepot.agent.identity._platform_machine_id", lambda: None)
        id_file = tmp_identity_dir / "identity"
        id_file.write_text("", encoding="utf-8")
        assert get_device_id() is None


class TestResetDeviceId:
    """Tests for reset_device_id."""

    def test_removes_identity_file(self, tmp_identity_dir):
        """reset_device_id removes the identity file from disk."""
        get_or_create_device_id()
        assert (tmp_identity_dir / "identity").exists()
        reset_device_id()
        assert not (tmp_identity_dir / "identity").exists()

    def test_after_reset_new_id_is_generated(self, tmp_identity_dir):
        """After reset, get_or_create_device_id generates a new ID."""
        first = get_or_create_device_id()
        reset_device_id()
        second = get_or_create_device_id()
        assert first != second

    def test_reset_on_empty(self, tmp_identity_dir):
        """Calling reset_device_id when no identity file exists does not raise."""
        reset_device_id()


class TestIdentityPaths:
    """Tests for identity_path and identity_dir."""

    def test_identity_path_returns_file(self, tmp_identity_dir):
        """identity_path returns the path to the identity file."""
        path = identity_path()
        assert path == tmp_identity_dir / "identity"

    def test_identity_dir_returns_directory(self, tmp_identity_dir):
        """identity_dir returns the directory containing the identity file."""
        directory = identity_dir()
        assert directory == tmp_identity_dir

    def test_identity_file_does_not_exist_initially(self, tmp_identity_dir):
        """The identity file does not exist before any call to create it."""
        assert not identity_path().exists()

    def test_identity_file_exists_after_create(self, tmp_identity_dir):
        """The identity file exists after get_or_create_device_id is called."""
        get_or_create_device_id()
        assert identity_path().exists()


# ============================================================================
# Edge cases
# ============================================================================


class TestEdgeCases:
    """Edge-case tests for device identity."""

    def test_uuid_format(self):
        """Generated UUID identity has the expected 'device-<hex>' format."""
        ident = _generate_uuid_identity()
        parts = ident.split("-")
        assert parts[0] == "device"
        assert len(parts) == 2
        assert len(parts[1]) == 32

    def test_machine_id_with_newlines(self):
        """machine-id with trailing newline is stripped correctly."""
        with patch("homepot.agent.identity.Path.exists", return_value=True):
            with patch(
                "homepot.agent.identity.Path.read_text", return_value="abc123\n"
            ):
                result = _machine_id_identity()
                assert result is not None
                assert result.startswith("device-")

    def test_machine_id_returns_none_on_read_error(self):
        """A PermissionError reading machine-id returns None."""
        with patch("homepot.agent.identity.Path.exists", return_value=True):
            with patch(
                "homepot.agent.identity.Path.read_text",
                side_effect=PermissionError("No"),
            ):
                result = _machine_id_identity()
                assert result is None

    def test_identity_persistence_survives_object_recreation(self, tmp_identity_dir):
        """Identity persists across re-creation of the directory reference."""
        first = get_or_create_device_id()
        with patch("homepot.agent.identity._get_identity_dir", return_value=tmp_identity_dir):
            second = get_or_create_device_id()
        assert first == second

    def test_identity_dir_creates_directory(self, tmp_identity_dir):
        """identity_dir creates the directory if it does not exist."""
        assert tmp_identity_dir.exists()
        result = identity_dir()
        assert result == tmp_identity_dir

    def test_windows_machine_id_strips_whitespace(self):
        """Windows machine ID handles leading/trailing whitespace in output."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "  abc-def-ghi  \n"
        with patch("homepot.agent.identity.subprocess.run", return_value=mock_result):
            result = _windows_machine_id_identity()
            assert result is not None
            assert result.startswith("device-")


# ============================================================================
# _is_windows helper
# ============================================================================


class TestIsWindows:
    """Tests for the _is_windows platform detection helper."""

    def test_returns_true_on_win32(self):
        """_is_windows returns True when sys.platform is 'win32'."""
        with patch("homepot.agent.identity.sys.platform", "win32"):
            from homepot.agent.identity import _is_windows
            assert _is_windows() is True

    def test_returns_false_on_linux(self):
        """_is_windows returns False when sys.platform is 'linux'."""
        with patch("homepot.agent.identity.sys.platform", "linux"):
            from homepot.agent.identity import _is_windows
            assert _is_windows() is False
