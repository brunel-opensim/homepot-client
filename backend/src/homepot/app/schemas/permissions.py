"""Pydantic schemas for device permission APIs."""

from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

ALL_PERMISSION_KEYS = [
    "root_access",
    "command_execution",
    "process_monitoring",
    "filesystem_access",
    "network_monitoring",
]

DEFAULT_CAPABILITIES: Dict[str, bool] = {k: True for k in ALL_PERMISSION_KEYS}


def os_family(os_details: Optional[str]) -> Optional[str]:
    """Map an OS details string to a canonical OS family key.

    Returns one of ``"windows"``, ``"android"``, ``"ios"``, ``"linux"`` or
    ``"macos"``, or ``None`` for missing / unrecognised OS info. This is the
    single source of truth for OS classification, shared by the capability,
    push-channel and OS-icon derivation paths. Recognises both short tokens
    (``"linux"``) and versioned strings (``"Android 14"``, ``"macOS 14"``,
    ``"Windows 11"``) so emulators and simulated devices classify identically.
    """
    if not os_details:
        return None

    os_lower = os_details.lower()

    if any(kw in os_lower for kw in ("windows", "win32", "win64")):
        return "windows"
    if "android" in os_lower:
        return "android"
    if any(kw in os_lower for kw in ("ios", "ipados", "iphone os", "ipad")):
        return "ios"
    if any(
        kw in os_lower
        for kw in ("linux", "ubuntu", "debian", "fedora", "centos", "raspberry pi")
    ):
        return "linux"
    if any(kw in os_lower for kw in ("macos", "mac os", "darwin", "os x")):
        return "macos"
    return None


def derive_capabilities(os_details: Optional[str]) -> Dict[str, bool]:
    """Derive device capabilities from the OS details string.

    Maps known OS identifiers to the capabilities the OS can support.
    Returns all-``False`` for unrecognised or missing OS info.
    """
    family = os_family(os_details)

    if family in ("linux", "macos"):
        return dict(DEFAULT_CAPABILITIES)

    if family in ("android", "windows"):
        return {
            "root_access": False,
            "command_execution": True,
            "process_monitoring": True,
            "filesystem_access": True,
            "network_monitoring": True,
        }

    if family == "ios":
        return {
            "root_access": False,
            "command_execution": False,
            "process_monitoring": False,
            "filesystem_access": False,
            "network_monitoring": True,
        }

    return {k: False for k in ALL_PERMISSION_KEYS}


def derive_push_channel(os_details: Optional[str]) -> Optional[str]:
    """Derive the push-notification channel from the OS details string.

    Mirrors ``derive_push_channel`` in ``emulators/pos_engine.py``. Mobile and
    push-capable OSes receive commands over a push transport (FCM on Android,
    WNS on Windows, APNs on iOS); all non-push OSes fall back to plain HTTP
    polling (``None``).
    """
    family = os_family(os_details)

    if family == "android":
        return "fcm"
    if family == "windows":
        return "wns"
    if family == "ios":
        return "apns"
    return None


class DeviceCapabilities(BaseModel):
    """Which permission flags a device's OS can support."""

    root_access: bool = Field(default=False)
    command_execution: bool = Field(default=False)
    process_monitoring: bool = Field(default=False)
    filesystem_access: bool = Field(default=False)
    network_monitoring: bool = Field(default=False)


class DevicePermissions(BaseModel):
    """Device permission grants schema."""

    root_access: bool = Field(default=False, description="Can execute commands as root")
    command_execution: bool = Field(
        default=False, description="Can execute technician commands and scripts"
    )
    process_monitoring: bool = Field(
        default=False, description="Can monitor running processes"
    )
    filesystem_access: bool = Field(
        default=False, description="Can read and write files"
    )
    network_monitoring: bool = Field(
        default=False, description="Can monitor network traffic"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "root_access": False,
                "command_execution": False,
                "process_monitoring": True,
                "filesystem_access": False,
                "network_monitoring": True,
            }
        }
    )


class DevicePermissionsUpdate(BaseModel):
    """Request schema for updating device permissions."""

    permissions: DevicePermissions

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "permissions": {
                    "root_access": False,
                    "command_execution": False,
                    "process_monitoring": True,
                    "filesystem_access": False,
                    "network_monitoring": True,
                }
            }
        }
    )


class DevicePermissionsResponse(BaseModel):
    """Response schema for device permissions."""

    device_id: str
    permissions: DevicePermissions
    capabilities: DeviceCapabilities
    message: str
