"""Credential-storage abstraction for device credentials.

Mirrors the TypeScript CredentialStorage interface from
user_app/src/services/credentialStorage.ts.

The plaintext API key is returned **only** at issuance or rotation.
This abstraction ensures the same higher-level workflow works across
development simulations and production platforms.

Implementations:
- ``SimulationStorage`` — in-memory dict / temp file (for dev/testing)
- ``LinuxFileStorage`` — file on disk with strict permissions (0o600)
- ``KeyringCredentialStorage`` — OS keyring via the ``keyring`` library
- ``WindowsCredManager`` — Windows Credential Manager via ``keyring``
- ``WindowsFileStorage`` — file fallback on Windows (``%PROGRAMDATA%``)
- ``AndroidKeystore`` — placeholder for Android Keystore
"""

from abc import ABC, abstractmethod
import json
import logging
import os
from pathlib import Path
import sys
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

DeviceCredentials = Dict[str, str]


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class CredentialStorage(ABC):
    """Abstract interface for persisting device credentials."""

    @abstractmethod
    def save(self, creds: DeviceCredentials) -> None:
        """Persist credentials after a successful provision or claim."""

    @abstractmethod
    def get_api_key(self) -> Optional[str]:
        """Retrieve the stored API key.  Returns ``None`` if not provisioned."""

    @abstractmethod
    def get_device_id(self) -> Optional[str]:
        """Retrieve the stored device ID.  Returns ``None`` if not provisioned."""

    @abstractmethod
    def get_metadata(self, key: str) -> Optional[str]:
        """Retrieve a metadata field by key."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all stored credentials (unpair / factory-reset)."""

    @abstractmethod
    def is_provisioned(self) -> bool:
        """Return True if credentials are present."""

    # ------------------------------------------------------------------
    # Concrete convenience helpers (reuse the abstract interface above)
    # ------------------------------------------------------------------

    def get_backend_url(self) -> Optional[str]:
        """Return the configured backend URL or None."""
        return self.get_metadata("backend_url")

    def set_backend_url(self, url: str) -> None:
        """Persist the backend URL so the agent knows where to connect."""
        self.save({"backend_url": url})

    def get_tls_verify(self) -> bool:
        """Return whether TLS certificate verification is enabled.

        Defaults to ``True``.  Once explicitly set to ``"false"`` via
        ``set_tls_config`` it returns ``False``.
        """
        val = self.get_metadata("tls_verify")
        return val != "false" if val else True

    def get_tls_ca_cert(self) -> Optional[str]:
        """Return the path (or PEM content) of the TLS CA certificate."""
        return self.get_metadata("tls_ca_cert")

    def get_tls_client_cert(self) -> Optional[str]:
        """Return the path (or PEM content) of the TLS client cert."""
        return self.get_metadata("tls_client_cert")

    def get_tls_client_key(self) -> Optional[str]:
        """Return the path (or PEM content) of the TLS client key."""
        return self.get_metadata("tls_client_key")

    def set_tls_config(
        self,
        verify: bool = True,
        ca_cert: Optional[str] = None,
        client_cert: Optional[str] = None,
        client_key: Optional[str] = None,
    ) -> None:
        """Persist TLS configuration alongside credentials.

        Parameters
        ----------
        verify:
            Whether to verify the server's TLS certificate.
        ca_cert:
            Path to a CA certificate file or PEM-encoded content.
        client_cert:
            Path to a client certificate file or PEM-encoded content
            (mutual TLS).
        client_key:
            Path to the client private key file or PEM-encoded content.
        """
        data: Dict[str, str] = {"tls_verify": str(verify).lower()}
        if ca_cert is not None:
            data["tls_ca_cert"] = ca_cert
        if client_cert is not None:
            data["tls_client_cert"] = client_cert
        if client_key is not None:
            data["tls_client_key"] = client_key
        self.save(data)


# ---------------------------------------------------------------------------
# Simulation storage (in-memory)
# ---------------------------------------------------------------------------


class SimulationStorage(CredentialStorage):
    """In-memory credential storage for testing and development."""

    def __init__(self) -> None:
        """Initialize an empty in-memory credential store."""
        self._data: Dict[str, str] = {}

    def save(self, creds: DeviceCredentials) -> None:
        """Save credentials to the in-memory store."""
        self._data.update(creds)

    def get_api_key(self) -> Optional[str]:
        """Return the stored API key or None."""
        return self._data.get("api_key")

    def get_device_id(self) -> Optional[str]:
        """Return the stored device ID or None."""
        return self._data.get("device_id")

    def get_metadata(self, key: str) -> Optional[str]:
        """Return a metadata field by key or None."""
        return self._data.get(key)

    def clear(self) -> None:
        """Remove all stored credentials."""
        self._data.clear()

    def is_provisioned(self) -> bool:
        """Return True if device_id is present in the store."""
        return "device_id" in self._data


# ---------------------------------------------------------------------------
# Linux file storage (file on disk with strict permissions)
# ---------------------------------------------------------------------------


class LinuxFileStorage(CredentialStorage):
    """Stores credentials in a JSON file with ``0o600`` permissions.

    Default location: ``~/.homepot/credentials``
    """

    def __init__(self, file_path: Optional[Path] = None) -> None:
        """Initialize Linux file storage at the given path."""
        self._file_path = file_path or Path.home() / ".homepot" / "credentials"

    def _read(self) -> Dict[str, str]:
        """Read credentials from the JSON file. Returns empty dict on error."""
        if not self._file_path.exists():
            return {}
        try:
            raw = self._file_path.read_text("utf-8")
            return dict(json.loads(raw))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read credentials file: %s", exc)
            return {}

    def _write(self, data: Dict[str, str]) -> None:
        """Write credentials to the JSON file with 0o600 permissions."""
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._file_path.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )
        self._file_path.chmod(0o600)

    def save(self, creds: DeviceCredentials) -> None:
        """Save credentials to the JSON file."""
        data = self._read()
        data.update(creds)
        self._write(data)

    def get_api_key(self) -> Optional[str]:
        """Return the stored API key or None."""
        return self._read().get("api_key")

    def get_device_id(self) -> Optional[str]:
        """Return the stored device ID or None."""
        return self._read().get("device_id")

    def get_metadata(self, key: str) -> Optional[str]:
        """Return a metadata field by key or None."""
        return self._read().get(key)

    def clear(self) -> None:
        """Remove the credentials file."""
        if self._file_path.exists():
            self._file_path.unlink()

    def is_provisioned(self) -> bool:
        """Return True if the file contains a device_id."""
        return self._file_path.exists() and "device_id" in self._read()


# ---------------------------------------------------------------------------
# Keyring storage (OS keyring via the ``keyring`` library)
# ---------------------------------------------------------------------------


class KeyringCredentialStorage(CredentialStorage):
    """Stores credentials in the OS keyring via the ``keyring`` library.

    The entire credentials dict is serialised as JSON and stored under
    *service* ``"homepot-agent"`` / *username* ``"credentials"``.

    Requires the ``keyring`` package (install with ``pip install homepot-client[agent]``).
    When the keyring backend is unavailable (e.g. headless server without a
    keyring daemon) the factory falls back to ``LinuxFileStorage``.
    """

    _SERVICE = "homepot-agent"
    _USERNAME = "credentials"

    def __init__(self) -> None:
        """Initialize keyring storage (lazy import of ``keyring``)."""
        try:
            import keyring as _kr

            self._kr = _kr
        except ImportError:
            raise ImportError(
                "keyring package is required. Install with: pip install homepot-client[agent]"
            )

    def _read(self) -> Dict[str, str]:
        """Retrieve credentials from the OS keyring."""
        try:
            raw = self._kr.get_password(self._SERVICE, self._USERNAME)
            if raw is None:
                return {}
            return dict(json.loads(raw))
        except Exception as exc:
            logger.warning("Failed to read credentials from keyring: %s", exc)
            return {}

    def _write(self, data: Dict[str, str]) -> None:
        """Store credentials in the OS keyring."""
        try:
            self._kr.set_password(
                self._SERVICE,
                self._USERNAME,
                json.dumps(data, indent=2),
            )
        except Exception as exc:
            logger.error("Failed to write credentials to keyring: %s", exc)
            raise

    def save(self, creds: DeviceCredentials) -> None:
        """Merge and persist credentials in the OS keyring."""
        data = self._read()
        data.update(creds)
        self._write(data)

    def get_api_key(self) -> Optional[str]:
        """Return the stored API key or None."""
        return self._read().get("api_key")

    def get_device_id(self) -> Optional[str]:
        """Return the stored device ID or None."""
        return self._read().get("device_id")

    def get_metadata(self, key: str) -> Optional[str]:
        """Return a metadata field by key or None."""
        return self._read().get(key)

    def clear(self) -> None:
        """Remove all stored credentials from the OS keyring."""
        try:
            self._kr.delete_password(self._SERVICE, self._USERNAME)
        except self._kr.errors.PasswordDeleteError:
            pass
        except Exception as exc:
            logger.warning("Failed to clear credentials from keyring: %s", exc)

    def is_provisioned(self) -> bool:
        """Return True if the keyring contains a device_id."""
        return self._read().get("device_id") is not None


# ---------------------------------------------------------------------------
# Windows Credential Manager (via the ``keyring`` library)
# ---------------------------------------------------------------------------


class WindowsCredManager(CredentialStorage):
    """Stores credentials in Windows Credential Manager via the ``keyring`` library.

    The entire credentials dict is serialised as JSON and stored under
    *service* ``"homepot-agent-windows"`` / *username* ``"credentials"``.

    Requires the ``keyring`` package (install with ``pip install homepot-client[agent]``).
    When the keyring backend is unavailable (e.g. headless or CI without
    Credential Manager service) the factory falls back to ``WindowsFileStorage``.
    """

    _SERVICE = "homepot-agent-windows"
    _USERNAME = "credentials"

    def __init__(self) -> None:
        """Initialize Windows Credential Manager storage."""
        try:
            import keyring as _kr

            self._kr = _kr
        except ImportError:
            raise ImportError(
                "keyring package is required. Install with: pip install homepot-client[agent]"
            )

    def _read(self) -> Dict[str, str]:
        """Retrieve credentials from Windows Credential Manager."""
        try:
            raw = self._kr.get_password(self._SERVICE, self._USERNAME)
            if raw is None:
                return {}
            return dict(json.loads(raw))
        except Exception as exc:
            logger.warning("Failed to read credentials from keyring: %s", exc)
            return {}

    def _write(self, data: Dict[str, str]) -> None:
        """Store credentials in Windows Credential Manager."""
        try:
            self._kr.set_password(
                self._SERVICE,
                self._USERNAME,
                json.dumps(data, indent=2),
            )
        except Exception as exc:
            logger.error("Failed to write credentials to keyring: %s", exc)
            raise

    def save(self, creds: DeviceCredentials) -> None:
        """Merge and persist credentials in Windows Credential Manager."""
        data = self._read()
        data.update(creds)
        self._write(data)

    def get_api_key(self) -> Optional[str]:
        """Return the stored API key or None."""
        return self._read().get("api_key")

    def get_device_id(self) -> Optional[str]:
        """Return the stored device ID or None."""
        return self._read().get("device_id")

    def get_metadata(self, key: str) -> Optional[str]:
        """Return a metadata field by key or None."""
        return self._read().get(key)

    def clear(self) -> None:
        """Remove all stored credentials from Windows Credential Manager."""
        try:
            self._kr.delete_password(self._SERVICE, self._USERNAME)
        except self._kr.errors.PasswordDeleteError:
            pass
        except Exception as exc:
            logger.warning("Failed to clear credentials from keyring: %s", exc)

    def is_provisioned(self) -> bool:
        """Return True if the keyring contains a device_id."""
        return self._read().get("device_id") is not None


# ---------------------------------------------------------------------------
# Windows file storage (JSON file under ``%PROGRAMDATA%``)
# ---------------------------------------------------------------------------


def _get_windows_credential_dir() -> Path:
    r"""Return the Windows directory for credential storage.

    Uses ``%PROGRAMDATA%\Homepot`` (all-users) or ``%APPDATA%\Homepot``
    (per-user) as a fallback.
    """
    program_data = os.environ.get("PROGRAMDATA")
    if program_data:
        path = Path(program_data) / "Homepot"
        try:
            path.mkdir(parents=True, exist_ok=True)
            return path
        except (OSError, PermissionError):
            pass
    app_data = os.environ.get("APPDATA")
    if app_data:
        path = Path(app_data) / "Homepot"
        try:
            path.mkdir(parents=True, exist_ok=True)
            return path
        except (OSError, PermissionError):
            pass
    from tempfile import gettempdir

    tmp_path = Path(gettempdir()) / "homepot"
    tmp_path.mkdir(parents=True, exist_ok=True)
    return tmp_path


class WindowsFileStorage(CredentialStorage):
    r"""Stores credentials in a JSON file under ``%PROGRAMDATA%``.

    Default location: ``%PROGRAMDATA%\Homepot\credentials``
    Fallback: ``%APPDATA%\Homepot\credentials``
    """

    def __init__(self, file_path: Optional[Path] = None) -> None:
        """Initialize Windows file storage at the given path."""
        self._file_path = file_path or _get_windows_credential_dir() / "credentials"

    def _read(self) -> Dict[str, str]:
        """Read credentials from the JSON file. Returns empty dict on error."""
        if not self._file_path.exists():
            return {}
        try:
            raw = self._file_path.read_text("utf-8")
            return dict(json.loads(raw))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read credentials file: %s", exc)
            return {}

    def _write(self, data: Dict[str, str]) -> None:
        """Write credentials to the JSON file."""
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._file_path.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )

    def save(self, creds: DeviceCredentials) -> None:
        """Save credentials to the JSON file."""
        data = self._read()
        data.update(creds)
        self._write(data)

    def get_api_key(self) -> Optional[str]:
        """Return the stored API key or None."""
        return self._read().get("api_key")

    def get_device_id(self) -> Optional[str]:
        """Return the stored device ID or None."""
        return self._read().get("device_id")

    def get_metadata(self, key: str) -> Optional[str]:
        """Return a metadata field by key or None."""
        return self._read().get(key)

    def clear(self) -> None:
        """Remove the credentials file."""
        if self._file_path.exists():
            self._file_path.unlink()

    def is_provisioned(self) -> bool:
        """Return True if the file contains a device_id."""
        return self._file_path.exists() and "device_id" in self._read()


# ---------------------------------------------------------------------------
# Platform-aware factory
# ---------------------------------------------------------------------------


def create_credential_storage(
    storage_path: Optional[Path] = None,
) -> CredentialStorage:
    """Return the most appropriate ``CredentialStorage`` for the current platform.

    Priority:
    **Windows:**
    1. **WindowsCredManager** — Windows Credential Manager via ``keyring``
    2. **WindowsFileStorage** — JSON file under ``%PROGRAMDATA%``
    3. **SimulationStorage** — in-memory fallback (dev / testing)

    **Linux:**
    1. **KeyringCredentialStorage** — OS keyring via the ``keyring`` library
    2. **LinuxFileStorage** — file on disk with ``0o600`` permissions
    3. **SimulationStorage** — in-memory fallback (dev / testing)
    """
    if sys.platform == "win32":
        try:
            from importlib import import_module

            import_module("keyring")
            return WindowsCredManager()
        except (ImportError, Exception) as exc:
            logger.debug(
                "Windows Credential Manager unavailable (%s); falling back to "
                "WindowsFileStorage",
                exc,
            )
        return WindowsFileStorage(file_path=storage_path)

    if os.name == "posix" and sys.platform != "darwin":
        try:
            from importlib import import_module

            import_module("keyring")
            return KeyringCredentialStorage()
        except (ImportError, Exception) as exc:
            logger.debug(
                "Keyring unavailable (%s); falling back to LinuxFileStorage", exc
            )
        return LinuxFileStorage(file_path=storage_path)

    logger.info(
        "No platform-specific credential storage for %s; using SimulationStorage",
        sys.platform,
    )
    return SimulationStorage()
