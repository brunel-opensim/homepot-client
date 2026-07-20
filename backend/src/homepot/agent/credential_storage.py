"""Credential-storage abstraction for device credentials.

Mirrors the TypeScript CredentialStorage interface from
user_app/src/services/credentialStorage.ts.

The plaintext API key is returned **only** at issuance or rotation.
This abstraction ensures the same higher-level workflow works across
development simulations and production platforms.

Implementations:
- ``SimulationStorage`` — in-memory dict / temp file (for dev/testing)
- ``LinuxFileStorage`` — file on disk with strict permissions (0o600)
- ``WindowsCredManager`` — placeholder for Windows Credential Manager / DPAPI
- ``AndroidKeystore`` — placeholder for Android Keystore
"""

import json
import logging
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
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
        """``True`` if credentials are present (device is provisioned)."""


# ---------------------------------------------------------------------------
# Simulation storage (in-memory)
# ---------------------------------------------------------------------------

class SimulationStorage(CredentialStorage):
    """In-memory credential storage for testing and development."""

    def __init__(self) -> None:
        self._data: Dict[str, str] = {}

    def save(self, creds: DeviceCredentials) -> None:
        self._data.update(creds)

    def get_api_key(self) -> Optional[str]:
        return self._data.get("api_key")

    def get_device_id(self) -> Optional[str]:
        return self._data.get("device_id")

    def get_metadata(self, key: str) -> Optional[str]:
        return self._data.get(key)

    def clear(self) -> None:
        self._data.clear()

    def is_provisioned(self) -> bool:
        return "device_id" in self._data


# ---------------------------------------------------------------------------
# Linux file storage (file on disk with strict permissions)
# ---------------------------------------------------------------------------

class LinuxFileStorage(CredentialStorage):
    """Stores credentials in a JSON file with ``0o600`` permissions.

    Default location: ``~/.homepot/credentials``
    """

    def __init__(self, file_path: Optional[Path] = None) -> None:
        self._file_path = file_path or Path.home() / ".homepot" / "credentials"

    def _read(self) -> Dict[str, str]:
        if not self._file_path.exists():
            return {}
        try:
            raw = self._file_path.read_text("utf-8")
            return dict(json.loads(raw))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read credentials file: %s", exc)
            return {}

    def _write(self, data: Dict[str, str]) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._file_path.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )
        self._file_path.chmod(0o600)

    def save(self, creds: DeviceCredentials) -> None:
        data = self._read()
        data.update(creds)
        self._write(data)

    def get_api_key(self) -> Optional[str]:
        return self._read().get("api_key")

    def get_device_id(self) -> Optional[str]:
        return self._read().get("device_id")

    def get_metadata(self, key: str) -> Optional[str]:
        return self._read().get(key)

    def clear(self) -> None:
        if self._file_path.exists():
            self._file_path.unlink()

    def is_provisioned(self) -> bool:
        return self._file_path.exists() and "device_id" in self._read()


# ---------------------------------------------------------------------------
# Platform-aware factory
# ---------------------------------------------------------------------------

def create_credential_storage(
    storage_path: Optional[Path] = None,
) -> CredentialStorage:
    """Return the appropriate ``CredentialStorage`` for the current platform.

    - **Linux** → ``LinuxFileStorage``
    - **Other** → ``SimulationStorage`` (dev/test fallback)
    """
    if os.name == "posix" and sys.platform != "darwin":
        return LinuxFileStorage(file_path=storage_path)
    logger.info(
        "No platform-specific credential storage for %s; using SimulationStorage",
        sys.platform,
    )
    return SimulationStorage()
