"""Pydantic schemas for enrolment intent APIs."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class EnrolmentIntentCreate(BaseModel):
    """Request schema for creating an enrolment intent."""

    site_id: str = Field(..., min_length=1, description="Business site ID")
    enrolment_method: str = Field(
        default="pre-provisioned",
        description="Enrolment method (pre-provisioned or self-enrolled)",
    )
    expected_device_identity: Optional[str] = Field(
        None, description="Expected device identity (e.g. serial number)"
    )
    expires_in_hours: int = Field(
        default=48, ge=1, le=8760, description="Hours until the intent expires"
    )
    idempotency_key: Optional[str] = Field(
        None, max_length=100, description="Optional idempotency key"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "site_id": "site-001",
                "enrolment_method": "pre-provisioned",
                "expected_device_identity": "SN-12345",
                "expires_in_hours": 72,
                "idempotency_key": "req-abc-123",
            }
        }
    )


class EnrolmentIntentApprove(BaseModel):
    """Request schema for approving or rejecting an enrolment intent."""

    status: str = Field(
        ...,
        pattern="^(approved|rejected)$",
        description="New status: approved or rejected",
    )


class EnrolmentIntentClaim(BaseModel):
    """Request schema for claiming a device via an enrolment intent."""

    claim_token: str = Field(..., min_length=1, description="One-time claim token")
    device_name: Optional[str] = Field(None, description="Optional display name")
    device_type: str = Field(default="pos_terminal", description="Device type")
    os_details: Optional[str] = Field(
        None, description="Operating system info reported by the device"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "claim_token": "abc123def456",
                "device_name": "Kitchen POS A",
                "device_type": "pos_terminal",
                "os_details": "Android 13",
            }
        }
    )


class EnrolmentIntentOut(BaseModel):
    """Response schema for an enrolment intent."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    intent_id: str
    site_id: str
    tenant_id: Optional[int] = None
    enrolment_method: str
    expected_device_identity: Optional[str] = None
    expires_at: datetime
    consumed_at: Optional[datetime] = None
    creator_id: int
    status: str
    idempotency_key: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class EnrolmentIntentListOut(BaseModel):
    """Response schema for listing enrolment intents."""

    intents: List[EnrolmentIntentOut]
    total: int


class EnrolmentIntentClaimResponse(BaseModel):
    """Response schema after successfully claiming an enrolment intent."""

    message: str
    device_id: str
    api_key: str
    site_id: str
