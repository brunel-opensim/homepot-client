"""Analytics models for tracking system metrics and user behavior."""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.orm import relationship

from .UserModel import Base


def utc_now() -> datetime:
    """Get current UTC time (timezone-naive for database compatibility).

    Note: Uses timezone-naive datetime for compatibility with existing
    database schema. For new projects, consider using timezone-aware datetimes.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class APIRequestLog(Base):
    """Track API requests for performance analysis."""

    __tablename__ = "api_request_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True, default=utc_now)
    endpoint = Column(String(255), nullable=False, index=True)
    method = Column(String(10), nullable=False)  # GET, POST, PUT, DELETE
    status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Float, nullable=False)
    user_id = Column(String(255), nullable=True, index=True)
    # device_id removed because it does not exist in the database schema yet
    ip_address = Column(String(45), nullable=True)  # IPv6 support
    user_agent = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    request_size_bytes = Column(Integer, nullable=True)
    response_size_bytes = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_timestamp_endpoint", "timestamp", "endpoint"),
        Index("idx_status_code", "status_code"),
    )


class DeviceStateHistory(Base):
    """Track device state changes over time."""

    __tablename__ = "device_state_history"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True, default=utc_now)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    previous_state = Column(String(50), nullable=True)
    new_state = Column(String(50), nullable=False)
    changed_by = Column(String(255), nullable=True)  # user_id or system
    reason = Column(String(500), nullable=True)
    extra_data = Column(JSON, nullable=True)

    # Relationships
    device = relationship(
        "Device",
        back_populates="state_history",
    )

    __table_args__ = (Index("idx_device_timestamp", "device_id", "timestamp"),)


class JobOutcome(Base):
    """Track job execution outcomes for pattern analysis."""

    __tablename__ = "job_outcomes"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True, default=utc_now)
    job_id = Column(String(255), nullable=False, index=True)
    job_type = Column(String(100), nullable=False, index=True)
    device_id = Column(String(255), nullable=True, index=True)
    status = Column(String(50), nullable=False)  # success, failed, timeout, cancelled
    duration_ms = Column(Integer, nullable=True)
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    initiated_by = Column(String(255), nullable=True)
    extra_data = Column(JSON, nullable=True)

    __table_args__ = (
        Index("idx_job_status", "job_type", "status"),
        Index("idx_timestamp_status", "timestamp", "status"),
    )


class ErrorLog(Base):
    """Categorized error tracking for system health monitoring."""

    __tablename__ = "error_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True, default=utc_now)
    category = Column(
        String(50), nullable=False, index=True
    )  # api, database, external_service, validation
    severity = Column(
        String(20), nullable=False, index=True
    )  # critical, error, warning, info
    error_code = Column(String(50), nullable=True, index=True)
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    endpoint = Column(String(255), nullable=True)
    user_id = Column(String(255), nullable=True, index=True)
    # device_id removed because it does not exist in the database schema yet
    # device_id = Column(String(255), nullable=True)
    context = Column(JSON, nullable=True)  # Additional context data
    resolved = Column(Boolean, default=False, index=True)
    resolved_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_category_severity", "category", "severity"),
        Index("idx_timestamp_category", "timestamp", "category"),
    )


class UserActivity(Base):
    """Track user activity for behavior analysis (populated by frontend)."""

    __tablename__ = "user_activities"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True, default=utc_now)
    user_id = Column(String(255), nullable=False, index=True)
    # device_id removed because it does not exist in the database schema yet
    # device_id = Column(String(255), nullable=True, index=True)
    session_id = Column(String(255), nullable=True, index=True)
    activity_type = Column(
        String(50), nullable=False, index=True
    )  # page_view, click, search, etc.
    page_url = Column(String(500), nullable=True)
    element_id = Column(String(255), nullable=True)
    search_query = Column(Text, nullable=True)
    extra_data = Column(JSON, nullable=True)
    duration_ms = Column(Integer, nullable=True)  # Time spent on page/activity

    __table_args__ = (
        Index("idx_user_timestamp", "user_id", "timestamp"),
        Index("idx_activity_type", "activity_type"),
    )


class DeviceMetrics(Base):
    """Track detailed device performance metrics over time for AI analysis."""

    __tablename__ = "device_metrics"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True, default=utc_now)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)

    # Performance metrics
    cpu_percent = Column(Float, nullable=True)
    memory_percent = Column(Float, nullable=True)
    disk_percent = Column(Float, nullable=True)
    network_latency_ms = Column(Float, nullable=True)

    # Business metrics
    transaction_count = Column(Integer, nullable=True)
    transaction_volume = Column(Float, nullable=True)  # Dollar amount
    error_rate = Column(Float, nullable=True)  # Percentage

    # Additional context
    active_connections = Column(Integer, nullable=True)
    queue_depth = Column(Integer, nullable=True)
    extra_metrics = Column(JSON, nullable=True)

    # Relationships
    device = relationship(
        "Device",
        back_populates="metrics",
    )

    __table_args__ = (
        Index("idx_device_metrics_device_timestamp", "device_id", "timestamp"),
        Index("idx_device_metrics_timestamp", "timestamp"),
    )


class ConfigurationHistory(Base):
    """Track configuration changes and their impact for AI learning."""

    __tablename__ = "configuration_history"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True, default=utc_now)

    # What was changed
    entity_type = Column(
        String(50), nullable=False, index=True
    )  # 'device', 'site', 'system'
    entity_id = Column(String(255), nullable=False, index=True)
    parameter_name = Column(String(255), nullable=False)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=False)

    # Change context
    changed_by = Column(String(255), nullable=False)
    change_reason = Column(Text, nullable=True)
    change_type = Column(
        String(50), nullable=True
    )  # 'manual', 'automated', 'ai_recommended'

    # Impact tracking for AI
    performance_before = Column(JSON, nullable=True)  # Metrics before
    performance_after = Column(JSON, nullable=True)  # Metrics after
    was_successful = Column(Boolean, nullable=True)
    was_rolled_back = Column(Boolean, default=False)
    rollback_reason = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_entity_timestamp", "entity_type", "entity_id", "timestamp"),
        Index("idx_change_type", "change_type"),
    )


class SiteOperatingSchedule(Base):
    """Define site operating hours for intelligent job scheduling."""

    __tablename__ = "site_operating_schedules"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False, index=True)

    # Schedule definition
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    open_time = Column(Time, nullable=True)
    close_time = Column(Time, nullable=True)
    is_closed = Column(Boolean, default=False)  # Holiday or special closure

    # Operational context
    is_maintenance_window = Column(Boolean, default=False)
    expected_transaction_volume = Column(Integer, nullable=True)
    peak_hours_start = Column(Time, nullable=True)
    peak_hours_end = Column(Time, nullable=True)

    # Additional context for AI
    notes = Column(Text, nullable=True)
    special_considerations = Column(JSON, nullable=True)

    __table_args__ = (Index("idx_site_day", "site_id", "day_of_week"),)


class PushNotificationLog(Base):
    """Track push notification delivery lifecycle."""

    __tablename__ = "push_notification_logs"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(100), unique=True, index=True, nullable=False)

    # Context
    # device_id removed because it does not exist in the database schema yet
    # device_id = Column(String(100), index=True, nullable=True)
    job_id = Column(String(100), index=True, nullable=True)
    provider = Column(String(20), nullable=False)  # fcm, apns, mqtt, wns, web_push

    # Timestamps
    sent_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    received_at = Column(DateTime, nullable=True)

    # Metrics
    latency_ms = Column(Integer, nullable=True)  # Calculated on ack
    status = Column(String(20), default="sent")  # sent, delivered, failed, expired

    # Error Tracking
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_push_message_id", "message_id"),
        # Index("idx_push_device", "device_id"),
        Index("idx_push_status", "status"),
    )


class Alert(Base):
    """Persistent system alerts for AI tracking and dashboard display."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True, default=utc_now)

    # Target
    device_id = Column(String(50), nullable=True, index=True)
    site_id = Column(Integer, nullable=True, index=True)

    # Alert Details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(20), nullable=False)  # critical, high, medium, low, info
    category = Column(
        String(50), nullable=False
    )  # hardware, network, software, security

    # Lifecycle
    status = Column(
        String(20), default="active", index=True
    )  # active, acknowledged, resolved, ignored
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(255), nullable=True)  # user_id or 'ai_auto_resolve'
    resolution_notes = Column(Text, nullable=True)

    # AI Integration
    ai_recommendation = Column(Text, nullable=True)
    ai_confidence = Column(Float, nullable=True)

    __table_args__ = (
        Index("idx_alert_status_severity", "status", "severity"),
        Index("idx_alert_device", "device_id"),
    )
