"""Persistent stable device identity for the HOMEPOT agent.

Generates and manages a stable device identity that survives restarts
and re-enrolment.  The identity is stored in:

1. ``/var/lib/homepot/identity`` — preferred FHS-compliant path when
   writable (used by the installed daemon).
2. ``XDG_DATA_HOME/homepot/identity`` — fallback for unprivileged/dev runs.
3. ``/etc/machine-id`` (hashed with a salt) — fallback when neither is
   writable, providing a deterministic identity tied to the hardware.
"""

import hashlib
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from platformdirs import user_data_dir

logger = logging.getLogger(__name__)

_IDENTITY_FILENAME = "identity"
_VAR_LIB_PATH = Path("/var/lib/homepot")
_FALLBACK_DIR = Path(user_data_dir("homepot", ensure_exists=True))


def _get_identity_dir() -> Path:
    """Return the best writable directory for the identity file.

    Prefers ``/var/lib/homepot``; falls back to XDG data dir.
    """
    try:
        _VAR_LIB_PATH.mkdir(parents=True, exist_ok=True)
        test_file = _VAR_LIB_PATH / ".write_test"
        test_file.touch()
        test_file.unlink()
        return _VAR_LIB_PATH
    except (OSError, PermissionError):
        return _FALLBACK_DIR


def _identity_file_path() -> Path:
    return _get_identity_dir() / _IDENTITY_FILENAME


def _generate_uuid_identity() -> str:
    """Generate a new random UUID-based device identity."""
    return f"device-{uuid.uuid4().hex}"


def _machine_id_identity() -> Optional[str]:
    """Derive a deterministic identity from ``/etc/machine-id``.

    Returns ``None`` if the file is unavailable.
    """
    machine_id_path = Path("/etc/machine-id")
    if not machine_id_path.exists():
        machine_id_path = Path("/var/lib/dbus/machine-id")
    if not machine_id_path.exists():
        return None
    try:
        raw = machine_id_path.read_text("utf-8").strip()
        if not raw:
            return None
        salted = hashlib.sha256(f"homepot-device-identity:{raw}".encode()).hexdigest()[:32]
        return f"device-{salted}"
    except (OSError, PermissionError) as exc:
        logger.warning("Cannot read machine-id: %s", exc)
        return None


def get_or_create_device_id() -> str:
    """Return the persistent device identity, creating one if needed.

    Resolution order:
    1. Read existing identity file.
    2. If absent, generate a UUID and persist it.
    3. If the identity directory is unwritable, derive from ``/etc/machine-id``.
    """
    identity_path = _identity_file_path()
    if identity_path.exists():
        try:
            raw = identity_path.read_text("utf-8").strip()
            if raw:
                return raw
        except OSError as exc:
            logger.warning("Failed to read identity file %s: %s", identity_path, exc)

    new_id = _generate_uuid_identity()
    try:
        identity_path.parent.mkdir(parents=True, exist_ok=True)
        identity_path.write_text(new_id + "\n", encoding="utf-8")
        identity_path.chmod(0o644)
        logger.info("Generated new device identity: %s", new_id)
        return new_id
    except (OSError, PermissionError):
        machine_id = _machine_id_identity()
        if machine_id:
            logger.info("Derived device identity from machine-id: %s", machine_id)
            return machine_id
        logger.warning(
            "Cannot persist identity file; using ephemeral UUID: %s", new_id
        )
        return new_id


def get_device_id() -> Optional[str]:
    """Read the existing device identity without creating a new one.

    Returns ``None`` if no identity has been established.
    """
    identity_path = _identity_file_path()
    if identity_path.exists():
        try:
            raw = identity_path.read_text("utf-8").strip()
            if raw:
                return raw
        except OSError:
            pass
    return _machine_id_identity()


def reset_device_id() -> None:
    """Remove the persisted identity file so a new one is generated next time.

    Does **not** affect ``/etc/machine-id``.
    """
    identity_path = _identity_file_path()
    if identity_path.exists():
        identity_path.unlink()
        logger.info("Device identity file removed: %s", identity_path)


def identity_path() -> Path:
    """Return the path to the identity file."""
    return _identity_file_path()


def identity_dir() -> Path:
    """Return the directory containing the identity file."""
    return _get_identity_dir()
