"""Homepot agent package initialization."""

from typing import Any

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


def __getattr__(name: str) -> Any:
    """Lazily export ``router`` on package access.

    The agent runtime imports this package at startup, so eagerly pulling
    in ``agent_api`` would drag the backend API stack (sqlalchemy/passlib/
    SECRET_KEY) into the frozen binary. ``router`` is only needed by the
    backend API server.
    """
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
