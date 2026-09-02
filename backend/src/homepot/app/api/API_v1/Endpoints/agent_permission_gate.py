"""Permission gates for device-authenticated read endpoints.

These helpers enforce the Monitor-vs-Manage model on device-data collection:

* ``Monitor`` — read-only diagnostics (metrics, logs, audit, alerts). Granted
  when the device owner has enabled at least one of the monitor keys.
* ``Manage`` — elevated ``root_access`` used by modifying operations (command
  history). Granted only when the owner has enabled ``root_access``.
"""

from typing import Any, Dict

from fastapi import HTTPException

from homepot.models import Device

# Mirrors the owner-facing tier groups in the User App
# (user_app/src/services/permissionsEvents.ts).
MANAGE_KEY = "root_access"
MONITOR_KEYS = [
    "command_execution",
    "filesystem_access",
    "process_monitoring",
    "network_monitoring",
]


def normalise_permissions(raw: Any) -> Dict[str, bool]:
    """Return a safe permissions dict, filling in any missing keys."""
    if not raw or not isinstance(raw, dict):
        return {}
    return {key: bool(value) for key, value in raw.items()}


def _has_monitor(permissions: Dict[str, bool]) -> bool:
    """Return True when the device owner has granted the Monitor tier."""
    return any(permissions.get(key, False) for key in MONITOR_KEYS)


def require_monitor(device: Device) -> None:
    """Raise ``403`` unless the device owner granted the Monitor tier."""
    permissions = normalise_permissions(device.device_permissions)
    if not _has_monitor(permissions):
        raise HTTPException(
            status_code=403,
            detail="Monitor permission is required to view this device data",
        )


def require_manage(device: Device) -> None:
    """Raise ``403`` unless the device owner granted the Manage tier."""
    permissions = normalise_permissions(device.device_permissions)
    if not permissions.get(MANAGE_KEY, False):
        raise HTTPException(
            status_code=403,
            detail="Manage (root_access) permission is required to view command history",
        )
