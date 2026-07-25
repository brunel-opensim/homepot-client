"""Pydantic schemas for device permission APIs."""

from pydantic import BaseModel, ConfigDict, Field


class DevicePermissions(BaseModel):
    """Device permission grants schema."""

    root_access: bool = Field(default=False, description="Can execute commands as root")
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
    message: str
