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
    firmware_version: Optional[str] = Field(
        None, description="Device firmware version string"
    )
    peripherals: Optional[dict] = Field(
        None, description="Detailed dictionary of attached peripherals like printers"
    )
    site_id: Optional[str] = Field(
        None, description="Business site ID (required when creating a new device)"
    )
    device_name: Optional[str] = Field(
        None, description="Human-friendly device name for new records"
    )
    device_type: str = Field(
        default="pos_terminal", description="Device type for new records"
    )
    device_source: Optional[str] = Field(
        None,
        description="Source identifier for the device — 'physical', 'emulator', or 'simulation'",
    )

    device_token: Optional[str] = Field(
        None,
        description=(
            "Push-registration token (FCM/APNs/WNS) reported during DNA "
            "registration. Distinct from the legacy provisioning alias."
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "physical-pos-001",
                "mac_address": "00:11:22:33:44:55",
                "os_details": "Windows 11 Pro",
                "local_ip": "192.168.1.20",
                "wan_ip": "203.0.113.10",
                "firmware_version": "2.4.1",
                "site_id": "site-001",
                "device_name": "Front Desk POS 1",
                "device_type": "pos_terminal",
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
    network_latency_ms: Optional[float] = Field(
        default=None, ge=0, description="Network latency in milliseconds"
    )
    uptime_seconds: Optional[int] = Field(
        default=None, ge=0, description="System uptime in seconds"
    )
    collection_interval_seconds: Optional[int] = Field(
        default=None,
        ge=1,
        description="Configured collection interval between telemetry samples",
    )
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
                "network_latency_ms": 8.4,
                "uptime_seconds": 3600,
                "collection_interval_seconds": 5,
                "timestamp": "2026-03-31T10:50:00Z",
            }
        }
    )


class AgentLogRequest(BaseModel):
    """Request schema for device log reporting."""

    device_id: str = Field(..., min_length=1, description="Unique device identifier")
    level: str = Field(
        default="info",
        description="Log level: info, warning, error, critical",
    )
    message: str = Field(..., min_length=1, description="Human-readable log message")
    category: str = Field(
        default="device", description="Log category (e.g. device, payment, network)"
    )
    timestamp: datetime = Field(
        default_factory=utc_now, description="Log timestamp in UTC"
    )
    context: Optional[dict] = Field(
        default=None, description="Additional structured context data"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "physical-pos-001",
                "level": "info",
                "message": "Heartbeat acknowledged by HOMEPOT backend",
                "category": "device",
                "timestamp": "2026-03-31T10:45:00Z",
            }
        }
    )


class AgentAuditRequest(BaseModel):
    """Request schema for device audit event reporting."""

    device_id: str = Field(..., min_length=1, description="Unique device identifier")
    event_type: str = Field(
        ..., min_length=1, description="Audit event type (e.g. agent_started)"
    )
    description: str = Field(
        ..., min_length=1, description="Human-readable event description"
    )
    timestamp: datetime = Field(
        default_factory=utc_now, description="Event timestamp in UTC"
    )
    metadata: Optional[dict] = Field(
        default=None, description="Additional structured event context"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "physical-pos-001",
                "event_type": "health_check_performed",
                "description": "Routine health check completed (cpu, memory, disk, network)",
                "timestamp": "2026-03-31T10:50:00Z",
            }
        }
    )


class AgentAlertRequest(BaseModel):
    """Request schema for device alert reporting."""

    device_id: str = Field(..., min_length=1, description="Unique device identifier")
    title: str = Field(..., min_length=1, description="Short alert title")
    description: Optional[str] = Field(
        default=None, description="Detailed alert description"
    )
    severity: str = Field(
        default="warning",
        description="Alert severity: critical, high, medium, low, info, warning, error",
    )
    category: str = Field(
        default="network",
        description="Alert category: hardware, network, software, security",
    )
    timestamp: datetime = Field(
        default_factory=utc_now, description="Alert timestamp in UTC"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "physical-pos-001",
                "title": "High Latency: 612ms",
                "description": "Network latency exceeded 200ms threshold",
                "severity": "critical",
                "category": "network",
                "timestamp": "2026-03-31T10:55:00Z",
            }
        }
    )


class AgentJobRequest(BaseModel):
    """Request schema for device job reporting."""

    device_id: str = Field(..., min_length=1, description="Unique device identifier")
    action: str = Field(
        ...,
        min_length=1,
        description="Job action name (e.g. Update POS payment config)",
    )
    description: Optional[str] = Field(
        default=None, description="Human-readable job description"
    )
    priority: str = Field(
        default="normal", description="Job priority: low, normal, high, critical"
    )
    payload: Optional[dict] = Field(
        default=None, description="Job-specific payload data"
    )
    timestamp: datetime = Field(
        default_factory=utc_now, description="Event timestamp in UTC"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "physical-pos-001",
                "action": "Update POS payment config",
                "description": "Automated background task: Update POS payment config",
                "priority": "normal",
                "timestamp": "2026-03-31T10:55:00Z",
            }
        }
    )


class AgentJobUpdateRequest(BaseModel):
    """Request schema for updating a device job's status."""

    device_id: str = Field(..., min_length=1, description="Unique device identifier")
    status: str = Field(
        ...,
        min_length=1,
        description="New job status: completed, failed, running",
    )
    result: Optional[dict] = Field(
        default=None, description="Execution result for completed jobs"
    )
    error_message: Optional[str] = Field(
        default=None, description="Error message for failed jobs"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "physical-pos-001",
                "status": "completed",
                "result": {"message": "Job executed successfully", "exit_code": 0},
            }
        }
    )


class AgentConfigHistoryRequest(BaseModel):
    """Request schema for recording a completed push command in Push History."""

    device_id: str = Field(..., min_length=1, description="Unique device identifier")
    action: str = Field(
        ..., min_length=1, description="Executed action (device command type)"
    )
    parameter_name: str = Field(
        ..., min_length=1, description="Configuration parameter or command label"
    )
    old_value: Optional[dict] = Field(
        default=None, description="Previous configuration value"
    )
    new_value: Optional[dict] = Field(
        default=None, description="Applied configuration / execution result"
    )
    success: bool = Field(
        default=True, description="Whether the push command completed successfully"
    )
    change_reason: Optional[str] = Field(
        default=None, description="Human-readable reason for the change"
    )
    timestamp: datetime = Field(
        default_factory=utc_now, description="Event timestamp in UTC"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "physical-pos-001",
                "action": "update_pos_payment_config",
                "parameter_name": "push_command:APPLY_CONFIG",
                "new_value": {"command": "APPLY_CONFIG", "version": "2.1.0"},
                "success": True,
                "change_reason": "Push command APPLY_CONFIG executed",
            }
        }
    )
