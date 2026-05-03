"""Pydantic schemas for agent registration, heartbeat, and telemetry APIs."""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return current UTC timestamp for default schema values."""
    return datetime.now(timezone.utc)


class AgentRegisterRequest(BaseModel):
    """Request schema for registering or updating a device agent."""

    device_id: str = Field(..., min_length=1, description="Unique device identifier")
    mac_address: Optional[str] = Field(
        None, description="MAC address of the primary network interface"
    )
    os_details: Optional[str] = Field(
        None, description="Operating system name and version"
    )
    local_ip: Optional[str] = Field(None, description="Local network IP address")
    wan_ip: Optional[str] = Field(None, description="Public/WAN IP address")
    site_id: Optional[str] = Field(
        None, description="Business site ID (required when creating a new device)"
    )
    device_name: Optional[str] = Field(
        None, description="Human-friendly device name for new records"
    )
    device_type: str = Field(
        default="physical_terminal", description="Device type for new records"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "physical-pos-001",
                "mac_address": "00:11:22:33:44:55",
                "os_details": "Windows 11 Pro",
                "local_ip": "192.168.1.20",
                "wan_ip": "203.0.113.10",
                "site_id": "site-001",
                "device_name": "Front Desk POS 1",
                "device_type": "physical_terminal",
            }
        }
    )


class AgentHeartbeatRequest(BaseModel):
    """Request schema for device heartbeat updates."""

    device_id: str = Field(..., min_length=1, description="Unique device identifier")
    timestamp: datetime = Field(
        default_factory=utc_now, description="Heartbeat timestamp in UTC"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "physical-pos-001",
                "timestamp": "2026-03-31T10:45:00Z",
            }
        }
    )


class AgentTelemetryRequest(BaseModel):
    """Request schema for device telemetry metrics."""

    device_id: str = Field(..., min_length=1, description="Unique device identifier")
    cpu_usage: float = Field(..., ge=0, le=100, description="CPU usage percentage")
    memory_usage: float = Field(
        ..., ge=0, le=100, description="Memory usage percentage"
    )
    disk_usage: float = Field(..., ge=0, le=100, description="Disk usage percentage")
    timestamp: datetime = Field(
        default_factory=utc_now, description="Telemetry timestamp in UTC"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "physical-pos-001",
                "cpu_usage": 23.5,
                "memory_usage": 61.0,
                "disk_usage": 48.3,
                "timestamp": "2026-03-31T10:50:00Z",
            }
        }
    )
