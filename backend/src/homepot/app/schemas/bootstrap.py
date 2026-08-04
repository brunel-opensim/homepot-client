"""Pydantic schemas for device bootstrap provisioning."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BootstrapProvisionRequest(BaseModel):
    """Request schema for provisioning a device via bootstrap key."""

    site_id: str = Field(..., min_length=1, description="Business site ID")
    bootstrap_key: str = Field(..., min_length=1, description="Site bootstrap key")
    device_name: Optional[str] = Field(
        None, description="Optional display name for the new device"
    )
    device_type: str = Field(
        default="pos_terminal", description="Device type for provisioning"
    )
    os_details: Optional[str] = Field(
        None, description="Operating system name and version reported by the device"
    )
    provisioning_source: Optional[str] = Field(
        "physical",
        description="Source of the device: 'physical' for real hardware, 'emulator' for emulated devices",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "site_id": "site-001",
                "bootstrap_key": "abc123def456",
                "device_name": "Kitchen POS A",
                "device_type": "pos_terminal",
                "os_details": "Android 13",
            }
        }
    )


class BootstrapProvisionResponse(BaseModel):
    """Response schema containing provisioned device credentials."""

    device_id: str
    api_key: str
    site_id: str
    created_at: datetime
    epoch_id: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "pos-terminal-a1b2c3d4",
                "api_key": "mM2....",
                "site_id": "site-001",
                "created_at": "2026-03-31T11:00:00Z",
            }
        }
    )


class BootstrapKeyResponse(BaseModel):
    """Response schema after generating a site bootstrap key."""

    bootstrap_key: str
    message: str


class DeviceNameCheckRequest(BaseModel):
    """Request schema for checking device-name availability in a site."""

    site_id: str = Field(..., min_length=1, description="Business site ID")
    bootstrap_key: str = Field(..., min_length=1, description="Site bootstrap key")
    device_name: str = Field(..., min_length=1, description="Candidate device name")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "site_id": "site-001",
                "bootstrap_key": "abc123def456",
                "device_name": "Kitchen POS A",
            }
        }
    )


class DeviceNameCheckResponse(BaseModel):
    """Response schema for a device-name availability check."""

    available: bool
