r"""Persistent stable device identity for the HOMEPOT agent.

Generates and manages a stable device identity that survives restarts
and re-enrolment.  The identity is stored in:

**Linux:**
1. ``/var/lib/homepot/identity`` — preferred FHS-compliant path when
   writable (used by the installed daemon).
2. ``XDG_DATA_HOME/homepot/identity`` — fallback for unprivileged/dev runs.
3. ``/etc/machine-id`` (hashed with a salt) — fallback when neither is
   writable, providing a deterministic identity tied to the hardware.

**Windows:**
1. ``%PROGRAMDATA%\\Homepot\\identity`` — all-users identity storage
   (``C:\\ProgramData\\Homepot\\identity``).
2. ``%APPDATA%\\Homepot\\identity`` — per-user fallback.
3. ``Win32_ComputerSystemProduct.UUID`` (hashed with a salt) — fallback
   when neither is writable.
"""

import hashlib
import logging
import os
from pathlib import Path
import subprocess  # noqa: S404
import sys
import tempfile
from typing import Optional
import uuid

from platformdirs import user_data_dir

logger = logging.getLogger(__name__)

_IDENTITY_FILENAME = "identity"

# Linux paths
_VAR_LIB_PATH = Path("/var/lib/homepot")
_FALLBACK_DIR = Path(user_data_dir("homepot"))

# Windows paths
_WINDOWS_PROGRAMDATA = (
    Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData")) / "Homepot"
)
_WINDOWS_APPDATA = (
    Path(os.environ.get("APPDATA", "")) / "Homepot"
    if os.environ.get("APPDATA")
    else None
)


def _is_windows() -> bool:
    return sys.platform == "win32"


def _get_identity_dir() -> Path:
    r"""Return the best writable directory for the identity file.

    **Windows:** ``%PROGRAMDATA%\Homepot`` or ``%APPDATA%\Homepot``.
    **Linux:** ``/var/lib/homepot`` or XDG data dir.
    """
    if _is_windows():
        try:
            _WINDOWS_PROGRAMDATA.mkdir(parents=True, exist_ok=True)
            test_file = _WINDOWS_PROGRAMDATA / ".write_test"
            test_file.touch()
            test_file.unlink()
            return _WINDOWS_PROGRAMDATA
        except (OSError, PermissionError):
            pass
        if _WINDOWS_APPDATA:
            try:
                _WINDOWS_APPDATA.mkdir(parents=True, exist_ok=True)
                return _WINDOWS_APPDATA
            except (OSError, PermissionError):
                pass
        tmp_dir = Path(tempfile.gettempdir()) / "homepot"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        return tmp_dir

    try:
        _VAR_LIB_PATH.mkdir(parents=True, exist_ok=True)
        test_file = _VAR_LIB_PATH / ".write_test"
        test_file.touch()
        test_file.unlink()
        return _VAR_LIB_PATH
    except (OSError, PermissionError):
        pass
    try:
        _FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
        return _FALLBACK_DIR
    except (OSError, PermissionError):
        tmp_dir = Path(tempfile.gettempdir()) / "homepot"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        return tmp_dir


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
        salted = hashlib.sha256(f"homepot-device-identity:{raw}".encode()).hexdigest()[
            :32
        ]
        return f"device-{salted}"
    except (OSError, PermissionError) as exc:
        logger.warning("Cannot read machine-id: %s", exc)
        return None


def _windows_machine_id_identity() -> Optional[str]:
    """Derive a deterministic identity from the Windows system UUID.

    Uses PowerShell to retrieve ``Win32_ComputerSystemProduct.UUID``,
    which is stable across reboots and tied to the motherboard.
    Returns ``None`` if the command fails or the UUID is empty.
    """
    try:
        result = subprocess.run(  # noqa: S603, S607  # hardcoded command, no user input
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_ComputerSystemProduct | Select-Object -ExpandProperty UUID",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        raw = result.stdout.strip() if result.stdout else ""
        if result.returncode != 0 or not raw:
            return None
        salted = hashlib.sha256(f"homepot-device-identity:{raw}".encode()).hexdigest()[
            :32
        ]
        return f"device-{salted}"
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("Cannot read Windows machine UUID: %s", exc)
        return None


def _platform_machine_id() -> Optional[str]:
    """Return a deterministic hardware-bound identity for the current platform."""
    if _is_windows():
        return _windows_machine_id_identity()
    return _machine_id_identity()


def get_or_create_device_id() -> str:
    """Return the persistent device identity, creating one if needed.

    Resolution order:
    1. Read existing identity file.
    2. If absent, generate a UUID and persist it.
    3. If the identity directory is unwritable, derive from a platform
       hardware identifier (``/etc/machine-id`` on Linux,
       ``Win32_ComputerSystemProduct.UUID`` on Windows).
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
        if not _is_windows():
            identity_path.chmod(0o644)
        logger.info("Generated new device identity: %s", new_id)
        return new_id
    except (OSError, PermissionError):
        machine_id = _platform_machine_id()
        if machine_id:
            logger.info("Derived device identity from hardware: %s", machine_id)
            return machine_id
        logger.warning("Cannot persist identity file; using ephemeral UUID: %s", new_id)
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
    return _platform_machine_id()


def reset_device_id() -> None:
    """Remove the persisted identity file so a new one is generated next time.

    Does **not** affect the hardware identifier on either platform.
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
