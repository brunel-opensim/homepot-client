"""Tests for the Python credential-storage abstraction.

Mirrors the TypeScript credentialStorage tests coverage for:
- SimulationStorage (in-memory)
- LinuxFileStorage (file on disk with 0o600 permissions)
- Factory function (create_credential_storage)
"""

import json
import os
from pathlib import Path
import sys
import tempfile

import pytest

from homepot.agent.credential_storage import (
    LinuxFileStorage,
    SimulationStorage,
    create_credential_storage,
)

# ============================================================================
# SimulationStorage
# ============================================================================


class TestSimulationStorage:
    """Tests for the in-memory SimulationStorage."""

    def test_save_and_get_api_key(self):
        """Save an API key and verify it can be retrieved."""
        storage = SimulationStorage()
        storage.save({"api_key": "sk-test-123", "device_id": "dev-1"})
        assert storage.get_api_key() == "sk-test-123"

    def test_save_and_get_device_id(self):
        """Save a device ID and verify it can be retrieved."""
        storage = SimulationStorage()
        storage.save({"device_id": "dev-42"})
        assert storage.get_device_id() == "dev-42"

    def test_get_metadata(self):
        """Save metadata fields and verify they can be retrieved by key."""
        storage = SimulationStorage()
        storage.save({"device_name": "Front POS", "site_id": "site-99"})
        assert storage.get_metadata("device_name") == "Front POS"
        assert storage.get_metadata("site_id") == "site-99"

    def test_get_metadata_missing(self):
        """Requesting a nonexistent metadata key returns None."""
        storage = SimulationStorage()
        storage.save({"device_id": "d1"})
        assert storage.get_metadata("nonexistent") is None

    def test_get_api_key_before_save(self):
        """get_api_key returns None before any credentials are saved."""
        storage = SimulationStorage()
        assert storage.get_api_key() is None

    def test_get_device_id_before_save(self):
        """get_device_id returns None before any credentials are saved."""
        storage = SimulationStorage()
        assert storage.get_device_id() is None

    def test_is_provisioned_true(self):
        """is_provisioned returns True after a device_id is saved."""
        storage = SimulationStorage()
        storage.save({"device_id": "d1"})
        assert storage.is_provisioned() is True

    def test_is_provisioned_false(self):
        """is_provisioned returns False when no credentials exist."""
        storage = SimulationStorage()
        assert storage.is_provisioned() is False

    def test_clear_removes_all(self):
        """Remove all stored credentials and reset provisioned state."""
        storage = SimulationStorage()
        storage.save({"api_key": "sk-test", "device_id": "d1", "site_id": "s1"})
        storage.clear()
        assert storage.get_api_key() is None
        assert storage.get_device_id() is None
        assert storage.is_provisioned() is False

    def test_save_updates_existing(self):
        """Save merges new fields into existing credentials."""
        storage = SimulationStorage()
        storage.save({"device_id": "d1", "device_name": "Old"})
        storage.save({"device_name": "New", "site_id": "s1"})
        assert storage.get_device_id() == "d1"
        assert storage.get_metadata("device_name") == "New"
        assert storage.get_metadata("site_id") == "s1"

    def test_save_accepts_partial_credentials(self):
        """Save works with only an API key and no device_id."""
        storage = SimulationStorage()
        storage.save({"api_key": "sk-test"})
        assert storage.get_api_key() == "sk-test"
        assert storage.get_device_id() is None

    def test_multiple_independent_instances(self):
        """Each SimulationStorage instance has its own isolated data."""
        s1 = SimulationStorage()
        s2 = SimulationStorage()
        s1.save({"device_id": "dev-1"})
        s2.save({"device_id": "dev-2"})
        assert s1.get_device_id() == "dev-1"
        assert s2.get_device_id() == "dev-2"


# ============================================================================
# LinuxFileStorage
# ============================================================================


class TestLinuxFileStorage:
    """Tests for the Linux file-based credential storage."""

    @pytest.fixture
    def temp_storage(self):
        """Create a LinuxFileStorage backed by a temp directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / ".homepot" / "credentials"
            storage = LinuxFileStorage(file_path=file_path)
            yield storage

    def test_save_and_get_api_key(self, temp_storage):
        """Save an API key and verify it can be retrieved from disk."""
        temp_storage.save({"api_key": "sk-linux-1", "device_id": "dev-linux-1"})
        assert temp_storage.get_api_key() == "sk-linux-1"

    def test_save_and_get_device_id(self, temp_storage):
        """Save a device ID and verify it can be retrieved from disk."""
        temp_storage.save({"device_id": "dev-linux-42"})
        assert temp_storage.get_device_id() == "dev-linux-42"

    def test_get_metadata(self, temp_storage):
        """Save metadata and verify it can be retrieved by key."""
        temp_storage.save({"device_name": "Linux POS", "site_id": "site-linux"})
        assert temp_storage.get_metadata("device_name") == "Linux POS"
        assert temp_storage.get_metadata("site_id") == "site-linux"

    def test_get_metadata_missing(self, temp_storage):
        """get_metadata for a missing key returns None."""
        temp_storage.save({"device_id": "d1"})
        assert temp_storage.get_metadata("nonexistent") is None

    def test_get_api_key_before_save(self, temp_storage):
        """get_api_key returns None when no credentials are stored."""
        assert temp_storage.get_api_key() is None

    def test_get_device_id_before_save(self, temp_storage):
        """get_device_id returns None when no credentials are stored."""
        assert temp_storage.get_device_id() is None

    def test_is_provisioned_true(self, temp_storage):
        """is_provisioned returns True after a device_id is saved."""
        temp_storage.save({"device_id": "d1"})
        assert temp_storage.is_provisioned() is True

    def test_is_provisioned_false_before_save(self, temp_storage):
        """is_provisioned returns False before any data is saved."""
        assert temp_storage.is_provisioned() is False

    def test_clear_removes_file(self, temp_storage):
        """Remove the credentials file from disk."""
        temp_storage.save({"api_key": "sk-test", "device_id": "d1"})
        assert temp_storage._file_path.exists()
        temp_storage.clear()
        assert not temp_storage._file_path.exists()
        assert temp_storage.is_provisioned() is False

    def test_file_permissions_are_strict(self, temp_storage):
        """Credentials file is created with 0o600 permissions."""
        if sys.platform == "win32":
            pytest.skip("Windows does not support Unix file permissions")
        temp_storage.save({"api_key": "sk-test", "device_id": "d1"})
        assert temp_storage._file_path.exists()
        mode = os.stat(temp_storage._file_path).st_mode & 0o777
        assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"

    def test_file_content_is_valid_json(self, temp_storage):
        """Credentials file content is valid JSON with all saved fields."""
        temp_storage.save(
            {"api_key": "sk-json", "device_id": "d-json", "site_id": "s-1"}
        )
        raw = temp_storage._file_path.read_text("utf-8")
        data = json.loads(raw)
        assert data["api_key"] == "sk-json"
        assert data["device_id"] == "d-json"
        assert data["site_id"] == "s-1"

    def test_clear_on_empty_storage(self, temp_storage):
        """Clear on an empty storage does not raise."""
        temp_storage.clear()
        assert temp_storage.is_provisioned() is False

    def test_save_overwrites_existing(self, temp_storage):
        """Save merges and overwrites fields in the existing file."""
        temp_storage.save({"device_id": "d1", "device_name": "Old Name"})
        temp_storage.save({"device_name": "New Name", "site_id": "s1"})
        data = json.loads(temp_storage._file_path.read_text("utf-8"))
        assert data["device_id"] == "d1"
        assert data["device_name"] == "New Name"
        assert data["site_id"] == "s1"

    def test_multiple_instances_same_file(self, temp_storage):
        """Two LinuxFileStorage instances pointing to the same file see the same data."""
        temp_storage.save({"device_id": "dev-1", "api_key": "sk-1"})
        storage2 = LinuxFileStorage(file_path=temp_storage._file_path)
        assert storage2.get_device_id() == "dev-1"
        assert storage2.get_api_key() == "sk-1"

    def test_directory_created_automatically(self):
        """Parent directories are created automatically when saving."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = Path(tmpdir) / "a" / "b" / "c" / "creds.json"
            storage = LinuxFileStorage(file_path=nested)
            storage.save({"device_id": "d-nested"})
            assert nested.exists()
            assert storage.get_device_id() == "d-nested"

    def test_corrupted_file_returns_empty(self, temp_storage):
        """A corrupted credentials file returns None for all fields."""
        temp_storage._file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_storage._file_path.write_text("not-json", encoding="utf-8")
        assert temp_storage.get_api_key() is None
        assert temp_storage.get_device_id() is None
        assert temp_storage.is_provisioned() is False

    def test_save_replaces_corrupted_file(self, temp_storage):
        """Saving overwrites a corrupted credentials file."""
        temp_storage._file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_storage._file_path.write_text("garbage", encoding="utf-8")
        temp_storage.save({"device_id": "d-fixed", "api_key": "sk-fixed"})
        assert temp_storage.get_device_id() == "d-fixed"
        assert temp_storage.get_api_key() == "sk-fixed"


# ============================================================================
# Factory function
# ============================================================================


class TestCreateCredentialStorage:
    """Tests for the create_credential_storage factory."""

    def test_returns_storage_on_linux(self):
        """Factory returns LinuxFileStorage on Linux, SimulationStorage elsewhere."""
        storage = create_credential_storage()
        if os.name == "posix" and sys.platform != "darwin":
            assert isinstance(storage, LinuxFileStorage)
        else:
            assert isinstance(storage, SimulationStorage)

    def test_accepts_custom_path(self):
        """Factory accepts an optional storage_path argument."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "custom" / "creds.json"
            storage = create_credential_storage(storage_path=path)
            if os.name == "posix" and sys.platform != "darwin":
                assert isinstance(storage, LinuxFileStorage)
            else:
                assert isinstance(storage, SimulationStorage)
            storage.save({"device_id": "d1"})
            assert storage.get_device_id() == "d1"
