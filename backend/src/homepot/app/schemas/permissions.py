"""Pydantic schemas for device permission APIs.

OS-family classification and capability / push-channel derivation live in the
canonical stdlib-only helper module :mod:`homepot.app.schemas.os_capabilities`
and are re-exported here for backward compatibility.
"""

from pydantic import BaseModel, ConfigDict, Field

from homepot.app.schemas.os_capabilities import (
    ALL_PERMISSION_KEYS,
    DEFAULT_CAPABILITIES,
    derive_capabilities,
    derive_push_channel,
    os_family,
)

__all__ = [
    "ALL_PERMISSION_KEYS",
    "DEFAULT_CAPABILITIES",
    "DeviceCapabilities",
    "DevicePermissions",
    "DevicePermissionsResponse",
    "DevicePermissionsUpdate",
    "derive_capabilities",
    "derive_push_channel",
    "os_family",
]


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
