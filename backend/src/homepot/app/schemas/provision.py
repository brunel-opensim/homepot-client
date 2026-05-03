"""Pydantic schemas for device provisioning APIs."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DeviceProvisionRequest(BaseModel):
    """Request schema for dynamic device provisioning."""

    sso_token: Optional[str] = Field(
        None, description="Optional SSO token used by setup wizard"
    )
    site_id: str = Field(..., min_length=1, description="Business site ID")
    user_identity: str = Field(
        ..., min_length=1, description="SSO user identity or email"
    )
    device_name: Optional[str] = Field(
        None, description="Optional display name for the new device"
    )
    device_type: str = Field(
        default="physical_terminal", description="Device type for provisioning"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sso_token": "eyJhbGciOi...",
                "site_id": "site-001",
                "user_identity": "agent.setup@dealdio.com",
                "device_name": "Kitchen POS A",
                "device_type": "physical_terminal",
            }
        }
    )


class DeviceProvisionResponse(BaseModel):
    """Response schema containing provisioned device credentials."""

    device_id: str
    api_key: str
    # Backward-compatible aliases for existing consumers.
    secret_key: Optional[str] = None
    device_token: Optional[str] = None
    site_id: str
    created_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "physical-terminal-a1b2c3d4",
                "api_key": "mM2....",
                "secret_key": "mM2....",
                "device_token": "XQw2....",
                "site_id": "site-001",
                "created_at": "2026-03-31T11:00:00Z",
            }
        }
    )
