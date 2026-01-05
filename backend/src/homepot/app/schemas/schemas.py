"""Pydantic schemas for user registration, authentication, and device metrics."""

from typing import Any, Dict, Optional, TypedDict

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Schema for creating a new user."""

    email: EmailStr
    password: str
    username: Optional[str] = None
    role: Optional[str] = "User"  # Default role


class UserLogin(BaseModel):
    """Schema for user login."""

    email: EmailStr
    password: str


class UserOut(BaseModel):
    """Schema for user output (response)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: Optional[str] = None
    role: str


class Token(BaseModel):
    """Schema for JWT token response."""

    access_token: str
    token_type: str


class SystemPulseResponse(BaseModel):
    """Schema for system pulse/load metrics."""

    status: str  # "idle", "working", "busy"
    load_score: int  # 0-100
    active_jobs: int
    queue_depth: int
    active_agents: int
    total_agents: int
    requests_per_minute: int
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None


class UserDict(TypedDict):
    """TypedDict for user information extracted from JWT token."""

    email: Optional[str]
    role: Optional[str]


# Device Metrics Schemas


class SystemMetrics(BaseModel):
    """System-level metrics for device health monitoring."""

    cpu_percent: Optional[float] = Field(
        None, ge=0, le=100, description="CPU usage percentage"
    )
    memory_percent: Optional[float] = Field(
        None, ge=0, le=100, description="Memory usage percentage"
    )
    memory_used_mb: Optional[int] = Field(
        None, ge=0, description="Memory used in megabytes"
    )
    memory_total_mb: Optional[int] = Field(
        None, ge=0, description="Total memory in megabytes"
    )
    disk_percent: Optional[float] = Field(
        None, ge=0, le=100, description="Disk usage percentage"
    )
    disk_used_gb: Optional[float] = Field(
        None, ge=0, description="Disk used in gigabytes"
    )
    disk_total_gb: Optional[float] = Field(
        None, ge=0, description="Total disk in gigabytes"
    )
    uptime_seconds: Optional[int] = Field(
        None, ge=0, description="System uptime in seconds"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cpu_percent": 65.5,
                "memory_percent": 80.0,
                "memory_used_mb": 1024,
                "memory_total_mb": 2048,
                "disk_percent": 60.0,
                "disk_used_gb": 120.5,
                "disk_total_gb": 200.0,
                "uptime_seconds": 86400,
            }
        }
    )


class ApplicationMetrics(BaseModel):
    """Application-level metrics for business monitoring."""

    app_version: Optional[str] = Field(None, description="Application version")
    transactions_count: Optional[int] = Field(
        None, ge=0, description="Number of transactions processed"
    )
    errors_count: Optional[int] = Field(
        None, ge=0, description="Number of errors encountered"
    )
    warnings_count: Optional[int] = Field(
        None, ge=0, description="Number of warnings encountered"
    )
    avg_response_time_ms: Optional[float] = Field(
        None, ge=0, description="Average response time in milliseconds"
    )
    active_connections: Optional[int] = Field(
        None, ge=0, description="Number of active connections"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "app_version": "1.2.3",
                "transactions_count": 150,
                "errors_count": 2,
                "warnings_count": 5,
                "avg_response_time_ms": 350.5,
                "active_connections": 3,
            }
        }
    )


class NetworkMetrics(BaseModel):
    """Network-level metrics for connectivity monitoring."""

    latency_ms: Optional[float] = Field(
        None, ge=0, description="Network latency in milliseconds"
    )
    rx_bytes: Optional[int] = Field(
        None, ge=0, description="Bytes received since last report"
    )
    tx_bytes: Optional[int] = Field(
        None, ge=0, description="Bytes transmitted since last report"
    )
    connection_quality: Optional[str] = Field(
        None, description="Connection quality: good, fair, poor"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "latency_ms": 45.5,
                "rx_bytes": 1024000,
                "tx_bytes": 512000,
                "connection_quality": "good",
            }
        }
    )


class EnvironmentalMetrics(BaseModel):
    """Environmental metrics for physical monitoring (optional)."""

    temperature_celsius: Optional[float] = Field(
        None, description="Ambient temperature in Celsius"
    )
    humidity_percent: Optional[float] = Field(
        None, ge=0, le=100, description="Relative humidity percentage"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"temperature_celsius": 28.5, "humidity_percent": 65.0}
        }
    )


class EnhancedHealthCheckData(BaseModel):
    """Enhanced health check data structure with comprehensive metrics.

    This schema extends the existing health check response_data JSON field
    to support system, application, network, and environmental metrics.
    All fields are optional to support gradual adoption by devices.
    """

    status: str = Field(..., description="Health status: healthy, degraded, unhealthy")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    system: Optional[SystemMetrics] = Field(
        None, description="System-level metrics (CPU, memory, disk)"
    )
    app_metrics: Optional[ApplicationMetrics] = Field(
        None, description="Application-level metrics (transactions, errors)"
    )
    network: Optional[NetworkMetrics] = Field(
        None, description="Network connectivity metrics"
    )
    environmental: Optional[EnvironmentalMetrics] = Field(
        None, description="Environmental conditions (temperature, humidity)"
    )
    custom: Optional[Dict[str, Any]] = Field(
        None, description="Custom device-specific metrics"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "timestamp": "2025-11-19T10:00:00Z",
                "system": {
                    "cpu_percent": 65.5,
                    "memory_percent": 80.0,
                    "memory_used_mb": 1024,
                    "memory_total_mb": 2048,
                    "disk_percent": 60.0,
                    "uptime_seconds": 86400,
                },
                "app_metrics": {
                    "app_version": "1.2.3",
                    "transactions_count": 150,
                    "errors_count": 2,
                    "avg_response_time_ms": 350.5,
                },
                "network": {"latency_ms": 45.5, "connection_quality": "good"},
            }
        }
    )


class HealthCheckRequest(BaseModel):
    """Request schema for device health check submission."""

    is_healthy: bool = Field(..., description="Overall health status")
    response_time_ms: Optional[int] = Field(
        None, ge=0, description="Response time in milliseconds"
    )
    status_code: Optional[int] = Field(
        None, ge=100, le=599, description="HTTP status code"
    )
    endpoint: str = Field(default="/health", description="Health check endpoint")
    response_data: Optional[Dict[str, Any]] = Field(
        None, description="Enhanced health check data with metrics (flexible format)"
    )
    error_message: Optional[str] = Field(None, description="Error message if unhealthy")
    system: Optional[SystemMetrics] = Field(None, description="System metrics")
    app_metrics: Optional[ApplicationMetrics] = Field(
        None, description="Application metrics"
    )
    network: Optional[NetworkMetrics] = Field(None, description="Network metrics")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "is_healthy": True,
                "response_time_ms": 150,
                "status_code": 200,
                "endpoint": "/health",
                "response_data": {
                    "status": "healthy",
                    "timestamp": "2025-11-19T10:00:00Z",
                    "system": {
                        "cpu_percent": 65.5,
                        "memory_percent": 80.0,
                        "disk_percent": 60.0,
                    },
                    "app_metrics": {"transactions_count": 150, "errors_count": 2},
                },
            }
        }
    )


# Alias for backward compatibility
DeviceHealthCheckRequest = HealthCheckRequest
AppMetrics = ApplicationMetrics
