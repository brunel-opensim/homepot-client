"""Analytics models for tracking system metrics and user behavior."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
)

from .UserModel import Base


class APIRequestLog(Base):
    """Track API requests for performance analysis."""

    __tablename__ = "api_request_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True, default=datetime.utcnow)
    endpoint = Column(String(255), nullable=False, index=True)
    method = Column(String(10), nullable=False)  # GET, POST, PUT, DELETE
    status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Float, nullable=False)
    user_id = Column(String(255), nullable=True, index=True)
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
    timestamp = Column(DateTime, nullable=False, index=True, default=datetime.utcnow)
    device_id = Column(String(255), nullable=False, index=True)
    previous_state = Column(String(50), nullable=True)
    new_state = Column(String(50), nullable=False)
    changed_by = Column(String(255), nullable=True)  # user_id or system
    reason = Column(String(500), nullable=True)
    extra_data = Column(JSON, nullable=True)

    __table_args__ = (Index("idx_device_timestamp", "device_id", "timestamp"),)


class JobOutcome(Base):
    """Track job execution outcomes for pattern analysis."""

    __tablename__ = "job_outcomes"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True, default=datetime.utcnow)
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
    timestamp = Column(DateTime, nullable=False, index=True, default=datetime.utcnow)
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
    device_id = Column(String(255), nullable=True)
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
    timestamp = Column(DateTime, nullable=False, index=True, default=datetime.utcnow)
    user_id = Column(String(255), nullable=False, index=True)
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
