"""Homepot agent package initialization."""

from homepot.agent.credential_storage import (
    CredentialStorage,
    KeyringCredentialStorage,
    LinuxFileStorage,
    MacOSFileStorage,
    SimulationStorage,
    WindowsCredManager,
    WindowsFileStorage,
    create_credential_storage,
)
from homepot.agent.identity import (
    get_device_id,
    get_or_create_device_id,
    identity_dir,
    identity_path,
    reset_device_id,
)


def __getattr__(name: str):
    """Lazily export ``router`` so the agent runtime does not eagerly pull in
    the backend API stack (sqlalchemy/passlib/SECRET_KEY) on import."""
    if name == "router":
        from homepot.agent.agent_api import router

        return router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "router",
    "CredentialStorage",
    "KeyringCredentialStorage",
    "LinuxFileStorage",
    "MacOSFileStorage",
    "SimulationStorage",
    "WindowsCredManager",
    "WindowsFileStorage",
    "create_credential_storage",
    "get_device_id",
    "get_or_create_device_id",
    "identity_dir",
    "identity_path",
    "reset_device_id",
]
