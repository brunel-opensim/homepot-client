"""Tests for the Python credential-storage abstraction.

Mirrors the TypeScript credentialStorage tests coverage for:
- SimulationStorage (in-memory)
- LinuxFileStorage (file on disk with 0o600 permissions)
- KeyringCredentialStorage (OS keyring)
- Factory function (create_credential_storage)
"""

import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from homepot.agent.credential_storage import (
    KeyringCredentialStorage,
    LinuxFileStorage,
    SimulationStorage,
    WindowsCredManager,
    WindowsFileStorage,
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

    # ------------------------------------------------------------------
    # Backend URL helpers
    # ------------------------------------------------------------------

    def test_get_backend_url_returns_none_by_default(self):
        """get_backend_url returns None before a URL is set."""
        storage = SimulationStorage()
        assert storage.get_backend_url() is None

    def test_set_and_get_backend_url(self):
        """set_backend_url persists the URL and get_backend_url retrieves it."""
        storage = SimulationStorage()
        storage.set_backend_url("https://api.example.com")
        assert storage.get_backend_url() == "https://api.example.com"

    def test_set_backend_url_overwrites(self):
        """set_backend_url overwrites the previous URL."""
        storage = SimulationStorage()
        storage.set_backend_url("https://old.example.com")
        storage.set_backend_url("https://new.example.com")
        assert storage.get_backend_url() == "https://new.example.com"

    # ------------------------------------------------------------------
    # TLS config helpers
    # ------------------------------------------------------------------

    def test_tls_verify_defaults_to_true(self):
        """get_tls_verify returns True when no TLS config is set."""
        storage = SimulationStorage()
        assert storage.get_tls_verify() is True

    def test_set_tls_verify_false(self):
        """set_tls_config with verify=False makes get_tls_verify return False."""
        storage = SimulationStorage()
        storage.set_tls_config(verify=False)
        assert storage.get_tls_verify() is False

    def test_set_tls_config_with_ca_cert(self):
        """set_tls_config stores a CA cert path that get_tls_ca_cert retrieves."""
        storage = SimulationStorage()
        storage.set_tls_config(ca_cert="/etc/ssl/certs/ca.pem")
        assert storage.get_tls_ca_cert() == "/etc/ssl/certs/ca.pem"

    def test_set_tls_config_with_client_cert(self):
        """set_tls_config stores client cert and key paths."""
        storage = SimulationStorage()
        storage.set_tls_config(
            client_cert="/etc/ssl/client.pem",
            client_key="/etc/ssl/client.key",
        )
        assert storage.get_tls_client_cert() == "/etc/ssl/client.pem"
        assert storage.get_tls_client_key() == "/etc/ssl/client.key"

    def test_set_tls_config_merge_preserves_other_fields(self):
        """set_tls_config merges into existing credentials without clearing them."""
        storage = SimulationStorage()
        storage.save({"device_id": "d1", "site_id": "s1"})
        storage.set_tls_config(verify=False)
        assert storage.get_device_id() == "d1"
        assert storage.get_metadata("site_id") == "s1"
        assert storage.get_tls_verify() is False


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

    # ------------------------------------------------------------------
    # Backend URL helpers
    # ------------------------------------------------------------------

    def test_get_backend_url_returns_none_by_default(self, temp_storage):
        """get_backend_url returns None before a URL is set."""
        assert temp_storage.get_backend_url() is None

    def test_set_and_get_backend_url(self, temp_storage):
        """set_backend_url persists the URL and get_backend_url retrieves it."""
        temp_storage.set_backend_url("https://api.example.com")
        assert temp_storage.get_backend_url() == "https://api.example.com"

    def test_backend_url_survives_reload(self, temp_storage):
        """Backend URL persists across LinuxFileStorage instances."""
        temp_storage.set_backend_url("https://persist.test")
        storage2 = LinuxFileStorage(file_path=temp_storage._file_path)
        assert storage2.get_backend_url() == "https://persist.test"

    # ------------------------------------------------------------------
    # TLS config helpers
    # ------------------------------------------------------------------

    def test_tls_verify_defaults_to_true(self, temp_storage):
        """get_tls_verify returns True when no TLS config is set."""
        assert temp_storage.get_tls_verify() is True

    def test_set_tls_verify_false(self, temp_storage):
        """set_tls_config with verify=False makes get_tls_verify return False."""
        temp_storage.set_tls_config(verify=False)
        assert temp_storage.get_tls_verify() is False

    def test_set_tls_config_with_all_options(self, temp_storage):
        """set_tls_config stores all TLS options correctly."""
        temp_storage.set_tls_config(
            verify=True,
            ca_cert="/etc/ca.pem",
            client_cert="/etc/client.pem",
            client_key="/etc/client.key",
        )
        assert temp_storage.get_tls_verify() is True
        assert temp_storage.get_tls_ca_cert() == "/etc/ca.pem"
        assert temp_storage.get_tls_client_cert() == "/etc/client.pem"
        assert temp_storage.get_tls_client_key() == "/etc/client.key"

    def test_tls_config_merge_preserves_credentials(self, temp_storage):
        """set_tls_config merges into existing credentials without clearing them."""
        temp_storage.save({"device_id": "d1", "site_id": "s1"})
        temp_storage.set_tls_config(verify=False, ca_cert="/etc/ca.pem")
        assert temp_storage.get_device_id() == "d1"
        assert temp_storage.get_metadata("site_id") == "s1"
        assert temp_storage.get_tls_verify() is False
        assert temp_storage.get_tls_ca_cert() == "/etc/ca.pem"


# ============================================================================
# KeyringCredentialStorage
# ============================================================================


@pytest.fixture
def mock_keyring_module():
    """Fixture that returns a mock ``keyring`` module with an in-memory backend."""
    mock_kr = MagicMock()
    store: dict = {}

    def set_pw(service, username, password):
        store[(service, username)] = password

    def get_pw(service, username):
        return store.get((service, username))

    def del_pw(service, username):
        store.pop((service, username), None)

    mock_kr.set_password.side_effect = set_pw
    mock_kr.get_password.side_effect = get_pw
    mock_kr.delete_password.side_effect = del_pw

    class FakeErrors:
        class PasswordDeleteError(Exception):
            pass

    mock_kr.errors = FakeErrors

    with patch.dict("sys.modules", {"keyring": mock_kr}):
        yield mock_kr


class TestKeyringCredentialStorage:
    """Tests for the OS keyring credential storage."""

    def test_requires_keyring_package(self):
        """Require keyring package; raises ImportError when absent."""
        with patch.dict("sys.modules", {"keyring": None}):
            with pytest.raises(ImportError):
                KeyringCredentialStorage()

    def test_save_and_get_api_key(self, mock_keyring_module):
        """Save an API key and verify it can be retrieved from the mock keyring."""
        storage = KeyringCredentialStorage()
        storage.save({"api_key": "sk-keyring-1", "device_id": "dev-kr-1"})
        assert storage.get_api_key() == "sk-keyring-1"

    def test_save_and_get_device_id(self, mock_keyring_module):
        """Save a device ID and verify it can be retrieved."""
        storage = KeyringCredentialStorage()
        storage.save({"device_id": "dev-kr-42"})
        assert storage.get_device_id() == "dev-kr-42"

    def test_get_metadata(self, mock_keyring_module):
        """Save metadata and verify it can be retrieved by key."""
        storage = KeyringCredentialStorage()
        storage.save({"device_name": "Keyring POS", "site_id": "site-kr"})
        assert storage.get_metadata("device_name") == "Keyring POS"
        assert storage.get_metadata("site_id") == "site-kr"

    def test_get_api_key_before_save(self, mock_keyring_module):
        """get_api_key returns None before any credentials are saved."""
        storage = KeyringCredentialStorage()
        assert storage.get_api_key() is None

    def test_is_provisioned_true(self, mock_keyring_module):
        """is_provisioned returns True after a device_id is saved."""
        storage = KeyringCredentialStorage()
        storage.save({"device_id": "d1"})
        assert storage.is_provisioned() is True

    def test_is_provisioned_false(self, mock_keyring_module):
        """is_provisioned returns False when no credentials exist."""
        storage = KeyringCredentialStorage()
        assert storage.is_provisioned() is False

    def test_clear_removes_all(self, mock_keyring_module):
        """Remove all stored credentials and reset provisioned state."""
        storage = KeyringCredentialStorage()
        storage.save({"api_key": "sk-test", "device_id": "d1", "site_id": "s1"})
        storage.clear()
        assert storage.get_api_key() is None
        assert storage.get_device_id() is None
        assert storage.is_provisioned() is False

    def test_save_merges_existing(self, mock_keyring_module):
        """Save merges new fields into existing credentials."""
        storage = KeyringCredentialStorage()
        storage.save({"device_id": "d1", "device_name": "Old"})
        storage.save({"device_name": "New", "site_id": "s1"})
        assert storage.get_device_id() == "d1"
        assert storage.get_metadata("device_name") == "New"
        assert storage.get_metadata("site_id") == "s1"

    def test_set_and_get_backend_url(self, mock_keyring_module):
        """Backend URL is stored and retrievable via the keyring."""
        storage = KeyringCredentialStorage()
        storage.set_backend_url("https://keyring.example.com")
        assert storage.get_backend_url() == "https://keyring.example.com"

    def test_set_tls_config(self, mock_keyring_module):
        """TLS configuration is stored correctly in the keyring."""
        storage = KeyringCredentialStorage()
        storage.set_tls_config(verify=False, ca_cert="/etc/ca.pem")
        assert storage.get_tls_verify() is False
        assert storage.get_tls_ca_cert() == "/etc/ca.pem"

    def test_clear_on_empty_storage(self, mock_keyring_module):
        """Clear on an empty storage does not raise."""
        storage = KeyringCredentialStorage()
        storage.clear()
        assert storage.is_provisioned() is False


# ============================================================================
# Factory function
# ============================================================================


class TestCreateCredentialStorage:
    """Tests for the create_credential_storage factory."""

    def test_returns_file_storage_when_keyring_unavailable(self):
        """Factory falls back to platform file storage when keyring is absent."""
        with patch.dict("sys.modules", {"keyring": None}):
            storage = create_credential_storage()
            if os.name == "posix" and sys.platform != "darwin":
                assert isinstance(storage, LinuxFileStorage)
            elif sys.platform == "win32":
                assert isinstance(storage, WindowsFileStorage)
            else:
                assert isinstance(storage, SimulationStorage)

    def test_accepts_custom_path(self):
        """Factory accepts an optional storage_path argument."""
        with patch.dict("sys.modules", {"keyring": None}):
            with tempfile.TemporaryDirectory() as tmpdir:
                path = Path(tmpdir) / "custom" / "creds.json"
                storage = create_credential_storage(storage_path=path)
                if os.name == "posix" and sys.platform != "darwin":
                    assert isinstance(storage, LinuxFileStorage)
                elif sys.platform == "win32":
                    assert isinstance(storage, WindowsFileStorage)
                else:
                    assert isinstance(storage, SimulationStorage)
                storage.save({"device_id": "d1"})
                assert storage.get_device_id() == "d1"

    def test_returns_keyring_when_available(self):
        """Factory returns KeyringCredentialStorage when keyring is available."""
        mock_kr = MagicMock()
        with patch.dict("sys.modules", {"keyring": mock_kr}):
            storage = create_credential_storage()
            if os.name == "posix" and sys.platform != "darwin":
                assert isinstance(storage, KeyringCredentialStorage)
            elif sys.platform == "win32":
                assert isinstance(storage, WindowsCredManager)
            else:
                assert isinstance(storage, SimulationStorage)

    def test_returns_windows_file_storage_on_win32_without_keyring(self):
        """Factory returns WindowsFileStorage on Windows when keyring is absent."""
        with patch("sys.platform", "win32"):
            with patch.dict("sys.modules", {"keyring": None}):
                with tempfile.TemporaryDirectory() as tmpdir:
                    path = Path(tmpdir) / "creds.json"
                    storage = create_credential_storage(storage_path=path)
                    assert isinstance(storage, WindowsFileStorage)
                    storage.save({"device_id": "d1"})
                    assert storage.get_device_id() == "d1"

    def test_returns_windows_cred_manager_on_win32_with_keyring(self):
        """Factory returns WindowsCredManager on Windows when keyring is available."""
        mock_kr = MagicMock()
        with patch("sys.platform", "win32"):
            with patch.dict("sys.modules", {"keyring": mock_kr}):
                storage = create_credential_storage()
                assert isinstance(storage, WindowsCredManager)


# ============================================================================
# WindowsCredManager
# ============================================================================


class TestWindowsCredManager:
    """Tests for the Windows Credential Manager storage."""

    def test_requires_keyring_package(self):
        """Require keyring package; raises ImportError when absent."""
        with patch.dict("sys.modules", {"keyring": None}):
            with pytest.raises(ImportError):
                WindowsCredManager()

    def test_save_and_get_api_key(self, mock_keyring_module):
        """Save an API key and verify it can be retrieved."""
        storage = WindowsCredManager()
        storage.save({"api_key": "sk-wcm-1", "device_id": "dev-wcm-1"})
        assert storage.get_api_key() == "sk-wcm-1"

    def test_save_and_get_device_id(self, mock_keyring_module):
        """Save a device ID and verify it can be retrieved."""
        storage = WindowsCredManager()
        storage.save({"device_id": "dev-wcm-42"})
        assert storage.get_device_id() == "dev-wcm-42"

    def test_get_metadata(self, mock_keyring_module):
        """Save metadata and verify it can be retrieved by key."""
        storage = WindowsCredManager()
        storage.save({"device_name": "WCM POS", "site_id": "site-wcm"})
        assert storage.get_metadata("device_name") == "WCM POS"
        assert storage.get_metadata("site_id") == "site-wcm"

    def test_get_api_key_before_save(self, mock_keyring_module):
        """get_api_key returns None before any credentials are saved."""
        storage = WindowsCredManager()
        assert storage.get_api_key() is None

    def test_is_provisioned_true(self, mock_keyring_module):
        """is_provisioned returns True after a device_id is saved."""
        storage = WindowsCredManager()
        storage.save({"device_id": "d1"})
        assert storage.is_provisioned() is True

    def test_is_provisioned_false(self, mock_keyring_module):
        """is_provisioned returns False when no credentials exist."""
        storage = WindowsCredManager()
        assert storage.is_provisioned() is False

    def test_clear_removes_all(self, mock_keyring_module):
        """Remove all stored credentials and reset provisioned state."""
        storage = WindowsCredManager()
        storage.save({"api_key": "sk-test", "device_id": "d1", "site_id": "s1"})
        storage.clear()
        assert storage.get_api_key() is None
        assert storage.get_device_id() is None
        assert storage.is_provisioned() is False

    def test_save_merges_existing(self, mock_keyring_module):
        """Save merges new fields into existing credentials."""
        storage = WindowsCredManager()
        storage.save({"device_id": "d1", "device_name": "Old"})
        storage.save({"device_name": "New", "site_id": "s1"})
        assert storage.get_device_id() == "d1"
        assert storage.get_metadata("device_name") == "New"
        assert storage.get_metadata("site_id") == "s1"

    def test_set_and_get_backend_url(self, mock_keyring_module):
        """Backend URL is stored and retrievable."""
        storage = WindowsCredManager()
        storage.set_backend_url("https://wcm.example.com")
        assert storage.get_backend_url() == "https://wcm.example.com"

    def test_set_tls_config(self, mock_keyring_module):
        """TLS configuration is stored correctly."""
        storage = WindowsCredManager()
        storage.set_tls_config(verify=False, ca_cert="C:\\certs\\ca.pem")
        assert storage.get_tls_verify() is False
        assert storage.get_tls_ca_cert() == "C:\\certs\\ca.pem"

    def test_clear_on_empty_storage(self, mock_keyring_module):
        """Clear on an empty storage does not raise."""
        storage = WindowsCredManager()
        storage.clear()
        assert storage.is_provisioned() is False


# ============================================================================
# WindowsFileStorage
# ============================================================================


class TestWindowsFileStorage:
    """Tests for the Windows file-based credential storage."""

    @pytest.fixture
    def temp_storage(self):
        """Create a WindowsFileStorage backed by a temp directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "Homepot" / "credentials"
            storage = WindowsFileStorage(file_path=file_path)
            yield storage

    def test_save_and_get_api_key(self, temp_storage):
        """Save an API key and verify it can be retrieved from disk."""
        temp_storage.save({"api_key": "sk-win-1", "device_id": "dev-win-1"})
        assert temp_storage.get_api_key() == "sk-win-1"

    def test_save_and_get_device_id(self, temp_storage):
        """Save a device ID and verify it can be retrieved from disk."""
        temp_storage.save({"device_id": "dev-win-42"})
        assert temp_storage.get_device_id() == "dev-win-42"

    def test_get_metadata(self, temp_storage):
        """Save metadata and verify it can be retrieved by key."""
        temp_storage.save({"device_name": "Win POS", "site_id": "site-win"})
        assert temp_storage.get_metadata("device_name") == "Win POS"
        assert temp_storage.get_metadata("site_id") == "site-win"

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
        """Two instances pointing to the same file see the same data."""
        temp_storage.save({"device_id": "dev-1", "api_key": "sk-1"})
        storage2 = WindowsFileStorage(file_path=temp_storage._file_path)
        assert storage2.get_device_id() == "dev-1"
        assert storage2.get_api_key() == "sk-1"

    def test_directory_created_automatically(self):
        """Parent directories are created automatically when saving."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = Path(tmpdir) / "a" / "b" / "c" / "creds.json"
            storage = WindowsFileStorage(file_path=nested)
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

    def test_get_backend_url_returns_none_by_default(self, temp_storage):
        """get_backend_url returns None before a URL is set."""
        assert temp_storage.get_backend_url() is None

    def test_set_and_get_backend_url(self, temp_storage):
        """set_backend_url persists the URL and get_backend_url retrieves it."""
        temp_storage.set_backend_url("https://win.example.com")
        assert temp_storage.get_backend_url() == "https://win.example.com"

    def test_backend_url_survives_reload(self, temp_storage):
        """Backend URL persists across instances."""
        temp_storage.set_backend_url("https://persist.test")
        storage2 = WindowsFileStorage(file_path=temp_storage._file_path)
        assert storage2.get_backend_url() == "https://persist.test"

    def test_tls_verify_defaults_to_true(self, temp_storage):
        """get_tls_verify returns True when no TLS config is set."""
        assert temp_storage.get_tls_verify() is True

    def test_set_tls_verify_false(self, temp_storage):
        """set_tls_config with verify=False makes get_tls_verify return False."""
        temp_storage.set_tls_config(verify=False)
        assert temp_storage.get_tls_verify() is False

    def test_set_tls_config_with_all_options(self, temp_storage):
        """set_tls_config stores all TLS options correctly."""
        temp_storage.set_tls_config(
            verify=True,
            ca_cert="C:\\certs\\ca.pem",
            client_cert="C:\\certs\\client.pem",
            client_key="C:\\certs\\client.key",
        )
        assert temp_storage.get_tls_verify() is True
        assert temp_storage.get_tls_ca_cert() == "C:\\certs\\ca.pem"
        assert temp_storage.get_tls_client_cert() == "C:\\certs\\client.pem"
        assert temp_storage.get_tls_client_key() == "C:\\certs\\client.key"

    def test_tls_config_merge_preserves_credentials(self, temp_storage):
        """set_tls_config merges into existing credentials without clearing them."""
        temp_storage.save({"device_id": "d1", "site_id": "s1"})
        temp_storage.set_tls_config(verify=False, ca_cert="C:\\ca.pem")
        assert temp_storage.get_device_id() == "d1"
        assert temp_storage.get_metadata("site_id") == "s1"
        assert temp_storage.get_tls_verify() is False
        assert temp_storage.get_tls_ca_cert() == "C:\\ca.pem"
