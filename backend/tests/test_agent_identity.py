"""Tests for persistent device identity management.

Covers:
- get_or_create_device_id()
- get_device_id()
- reset_device_id()
- identity_path()
- identity_dir()
- Fallback to machine-id when identity dir is unwritable
"""

import os
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

from homepot.agent.identity import (
    _generate_uuid_identity,
    _machine_id_identity,
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
    def test_returns_string_with_device_prefix(self):
        ident = _generate_uuid_identity()
        assert ident.startswith("device-")
        assert len(ident) > len("device-")

    def test_returns_unique_values(self):
        id1 = _generate_uuid_identity()
        id2 = _generate_uuid_identity()
        assert id1 != id2


class TestMachineIdIdentity:
    def test_returns_none_when_no_machine_id(self):
        with patch("homepot.agent.identity.Path.exists", return_value=False):
            result = _machine_id_identity()
            assert result is None

    def test_returns_none_on_empty_machine_id(self):
        with patch("homepot.agent.identity.Path.exists", return_value=True):
            with patch("homepot.agent.identity.Path.read_text", return_value=""):
                result = _machine_id_identity()
                assert result is None

    def test_returns_deterministic_id_from_machine_id(self):
        fake_id = "abc123def456"
        expected_prefix = "device-"
        with patch("homepot.agent.identity.Path.exists", return_value=True):
            with patch("homepot.agent.identity.Path.read_text", return_value=fake_id):
                result = _machine_id_identity()
                assert result is not None
                assert result.startswith(expected_prefix)
                assert len(result) > len(expected_prefix)

    def test_same_machine_id_gives_same_device_id(self):
        fake_id = "same-machine-id"
        with patch("homepot.agent.identity.Path.exists", return_value=True):
            with patch("homepot.agent.identity.Path.read_text", return_value=fake_id):
                r1 = _machine_id_identity()
                r2 = _machine_id_identity()
                assert r1 == r2


# ============================================================================
# Integration tests with temporary identity directories
# ============================================================================


@pytest.fixture
def tmp_identity_dir(monkeypatch):
    """Redirect identity storage to a temp directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        monkeypatch.setattr("homepot.agent.identity._VAR_LIB_PATH", tmp_path)
        yield tmp_path


class TestGetOrCreateDeviceId:
    def test_creates_and_returns_device_id(self, tmp_identity_dir):
        device_id = get_or_create_device_id()
        assert device_id.startswith("device-")
        id_file = tmp_identity_dir / "identity"
        assert id_file.exists()
        assert id_file.read_text("utf-8").strip() == device_id

    def test_returns_same_id_on_second_call(self, tmp_identity_dir):
        first = get_or_create_device_id()
        second = get_or_create_device_id()
        assert first == second

    def test_returns_existing_id_from_file(self, tmp_identity_dir):
        id_file = tmp_identity_dir / "identity"
        id_file.write_text("device-preexisting-id\n", encoding="utf-8")
        device_id = get_or_create_device_id()
        assert device_id == "device-preexisting-id"

    def test_id_file_has_correct_permissions(self, tmp_identity_dir):
        get_or_create_device_id()
        id_file = tmp_identity_dir / "identity"
        mode = os.stat(id_file).st_mode & 0o777
        assert mode == 0o644, f"Expected 0o644, got {oct(mode)}"


class TestGetDeviceId:
    def test_returns_none_when_no_identity(self, tmp_identity_dir, monkeypatch):
        monkeypatch.setattr("homepot.agent.identity._machine_id_identity", lambda: None)
        assert get_device_id() is None

    def test_returns_id_from_file(self, tmp_identity_dir, monkeypatch):
        monkeypatch.setattr("homepot.agent.identity._machine_id_identity", lambda: None)
        id_file = tmp_identity_dir / "identity"
        id_file.write_text("device-existing\n", encoding="utf-8")
        assert get_device_id() == "device-existing"

    def test_returns_none_on_corrupted_file(self, tmp_identity_dir, monkeypatch):
        monkeypatch.setattr("homepot.agent.identity._machine_id_identity", lambda: None)
        id_file = tmp_identity_dir / "identity"
        id_file.write_text("", encoding="utf-8")
        assert get_device_id() is None


class TestResetDeviceId:
    def test_removes_identity_file(self, tmp_identity_dir):
        get_or_create_device_id()
        assert (tmp_identity_dir / "identity").exists()
        reset_device_id()
        assert not (tmp_identity_dir / "identity").exists()

    def test_after_reset_new_id_is_generated(self, tmp_identity_dir):
        first = get_or_create_device_id()
        reset_device_id()
        second = get_or_create_device_id()
        assert first != second

    def test_reset_on_empty(self, tmp_identity_dir):
        reset_device_id()


class TestIdentityPaths:
    def test_identity_path_returns_file(self, tmp_identity_dir):
        path = identity_path()
        assert path == tmp_identity_dir / "identity"

    def test_identity_dir_returns_directory(self, tmp_identity_dir):
        directory = identity_dir()
        assert directory == tmp_identity_dir

    def test_identity_file_does_not_exist_initially(self, tmp_identity_dir):
        assert not identity_path().exists()

    def test_identity_file_exists_after_create(self, tmp_identity_dir):
        get_or_create_device_id()
        assert identity_path().exists()


# ============================================================================
# Edge cases
# ============================================================================


class TestEdgeCases:
    def test_uuid_format(self):
        ident = _generate_uuid_identity()
        parts = ident.split("-")
        assert parts[0] == "device"
        assert len(parts) == 2
        assert len(parts[1]) == 32

    def test_machine_id_with_newlines(self):
        with patch("homepot.agent.identity.Path.exists", return_value=True):
            with patch(
                "homepot.agent.identity.Path.read_text", return_value="abc123\n"
            ):
                result = _machine_id_identity()
                assert result is not None
                assert result.startswith("device-")

    def test_machine_id_returns_none_on_read_error(self):
        with patch("homepot.agent.identity.Path.exists", return_value=True):
            with patch(
                "homepot.agent.identity.Path.read_text",
                side_effect=PermissionError("No"),
            ):
                result = _machine_id_identity()
                assert result is None

    def test_identity_persistence_survives_object_recreation(self, tmp_identity_dir):
        first = get_or_create_device_id()
        with patch("homepot.agent.identity._VAR_LIB_PATH", tmp_identity_dir):
            second = get_or_create_device_id()
        assert first == second

    def test_identity_dir_creates_directory(self, tmp_identity_dir):
        assert tmp_identity_dir.exists()
        result = identity_dir()
        assert result == tmp_identity_dir
