"""Tests for the Python credential-storage abstraction.

Mirrors the TypeScript credentialStorage tests coverage for:
- SimulationStorage (in-memory)
- LinuxFileStorage (file on disk with 0o600 permissions)
- Factory function (create_credential_storage)
"""

import json
import os
import sys
import tempfile
from pathlib import Path

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
    def test_save_and_get_api_key(self):
        storage = SimulationStorage()
        storage.save({"api_key": "sk-test-123", "device_id": "dev-1"})
        assert storage.get_api_key() == "sk-test-123"

    def test_save_and_get_device_id(self):
        storage = SimulationStorage()
        storage.save({"device_id": "dev-42"})
        assert storage.get_device_id() == "dev-42"

    def test_get_metadata(self):
        storage = SimulationStorage()
        storage.save({"device_name": "Front POS", "site_id": "site-99"})
        assert storage.get_metadata("device_name") == "Front POS"
        assert storage.get_metadata("site_id") == "site-99"

    def test_get_metadata_missing(self):
        storage = SimulationStorage()
        storage.save({"device_id": "d1"})
        assert storage.get_metadata("nonexistent") is None

    def test_get_api_key_before_save(self):
        storage = SimulationStorage()
        assert storage.get_api_key() is None

    def test_get_device_id_before_save(self):
        storage = SimulationStorage()
        assert storage.get_device_id() is None

    def test_is_provisioned_true(self):
        storage = SimulationStorage()
        storage.save({"device_id": "d1"})
        assert storage.is_provisioned() is True

    def test_is_provisioned_false(self):
        storage = SimulationStorage()
        assert storage.is_provisioned() is False

    def test_clear_removes_all(self):
        storage = SimulationStorage()
        storage.save({"api_key": "sk-test", "device_id": "d1", "site_id": "s1"})
        storage.clear()
        assert storage.get_api_key() is None
        assert storage.get_device_id() is None
        assert storage.is_provisioned() is False

    def test_save_updates_existing(self):
        storage = SimulationStorage()
        storage.save({"device_id": "d1", "device_name": "Old"})
        storage.save({"device_name": "New", "site_id": "s1"})
        assert storage.get_device_id() == "d1"
        assert storage.get_metadata("device_name") == "New"
        assert storage.get_metadata("site_id") == "s1"

    def test_save_accepts_partial_credentials(self):
        storage = SimulationStorage()
        storage.save({"api_key": "sk-test"})
        assert storage.get_api_key() == "sk-test"
        assert storage.get_device_id() is None

    def test_multiple_independent_instances(self):
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
    @pytest.fixture
    def temp_storage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / ".homepot" / "credentials"
            storage = LinuxFileStorage(file_path=file_path)
            yield storage

    def test_save_and_get_api_key(self, temp_storage):
        temp_storage.save({"api_key": "sk-linux-1", "device_id": "dev-linux-1"})
        assert temp_storage.get_api_key() == "sk-linux-1"

    def test_save_and_get_device_id(self, temp_storage):
        temp_storage.save({"device_id": "dev-linux-42"})
        assert temp_storage.get_device_id() == "dev-linux-42"

    def test_get_metadata(self, temp_storage):
        temp_storage.save({"device_name": "Linux POS", "site_id": "site-linux"})
        assert temp_storage.get_metadata("device_name") == "Linux POS"
        assert temp_storage.get_metadata("site_id") == "site-linux"

    def test_get_metadata_missing(self, temp_storage):
        temp_storage.save({"device_id": "d1"})
        assert temp_storage.get_metadata("nonexistent") is None

    def test_get_api_key_before_save(self, temp_storage):
        assert temp_storage.get_api_key() is None

    def test_get_device_id_before_save(self, temp_storage):
        assert temp_storage.get_device_id() is None

    def test_is_provisioned_true(self, temp_storage):
        temp_storage.save({"device_id": "d1"})
        assert temp_storage.is_provisioned() is True

    def test_is_provisioned_false_before_save(self, temp_storage):
        assert temp_storage.is_provisioned() is False

    def test_clear_removes_file(self, temp_storage):
        temp_storage.save({"api_key": "sk-test", "device_id": "d1"})
        assert temp_storage._file_path.exists()
        temp_storage.clear()
        assert not temp_storage._file_path.exists()
        assert temp_storage.is_provisioned() is False

    def test_file_permissions_are_strict(self, temp_storage):
        temp_storage.save({"api_key": "sk-test", "device_id": "d1"})
        assert temp_storage._file_path.exists()
        mode = os.stat(temp_storage._file_path).st_mode & 0o777
        assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"

    def test_file_content_is_valid_json(self, temp_storage):
        temp_storage.save({"api_key": "sk-json", "device_id": "d-json", "site_id": "s-1"})
        raw = temp_storage._file_path.read_text("utf-8")
        data = json.loads(raw)
        assert data["api_key"] == "sk-json"
        assert data["device_id"] == "d-json"
        assert data["site_id"] == "s-1"

    def test_clear_on_empty_storage(self, temp_storage):
        temp_storage.clear()
        assert temp_storage.is_provisioned() is False

    def test_save_overwrites_existing(self, temp_storage):
        temp_storage.save({"device_id": "d1", "device_name": "Old Name"})
        temp_storage.save({"device_name": "New Name", "site_id": "s1"})
        data = json.loads(temp_storage._file_path.read_text("utf-8"))
        assert data["device_id"] == "d1"
        assert data["device_name"] == "New Name"
        assert data["site_id"] == "s1"

    def test_multiple_instances_same_file(self, temp_storage):
        temp_storage.save({"device_id": "dev-1", "api_key": "sk-1"})
        storage2 = LinuxFileStorage(file_path=temp_storage._file_path)
        assert storage2.get_device_id() == "dev-1"
        assert storage2.get_api_key() == "sk-1"

    def test_directory_created_automatically(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = Path(tmpdir) / "a" / "b" / "c" / "creds.json"
            storage = LinuxFileStorage(file_path=nested)
            storage.save({"device_id": "d-nested"})
            assert nested.exists()
            assert storage.get_device_id() == "d-nested"

    def test_corrupted_file_returns_empty(self, temp_storage):
        temp_storage._file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_storage._file_path.write_text("not-json", encoding="utf-8")
        assert temp_storage.get_api_key() is None
        assert temp_storage.get_device_id() is None
        assert temp_storage.is_provisioned() is False

    def test_save_replaces_corrupted_file(self, temp_storage):
        temp_storage._file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_storage._file_path.write_text("garbage", encoding="utf-8")
        temp_storage.save({"device_id": "d-fixed", "api_key": "sk-fixed"})
        assert temp_storage.get_device_id() == "d-fixed"
        assert temp_storage.get_api_key() == "sk-fixed"


# ============================================================================
# Factory function
# ============================================================================


class TestCreateCredentialStorage:
    def test_returns_storage_on_linux(self):
        storage = create_credential_storage()
        if os.name == "posix" and sys.platform != "darwin":
            assert isinstance(storage, LinuxFileStorage)
        else:
            assert isinstance(storage, SimulationStorage)

    def test_accepts_custom_path_linux(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "custom" / "creds.json"
            storage = create_credential_storage(storage_path=path)
            if os.name == "posix" and sys.platform != "darwin":
                assert isinstance(storage, LinuxFileStorage)
            else:
                assert isinstance(storage, SimulationStorage)
            storage.save({"device_id": "d1"})
            assert storage.get_device_id() == "d1"
