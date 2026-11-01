"""Analytics models for tracking system metrics and user behavior."""

from datetime import datetime, timezone
from uuid import uuid4

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
    UniqueConstraint,
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

    # Evidence provenance (snapshotted at write time)
    provenance = Column(String(20), nullable=True, index=True)

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

    # Evidence provenance (snapshotted at write time)
    provenance = Column(String(20), nullable=True, index=True)

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

    # Evidence provenance (snapshotted at write time)
    provenance = Column(String(20), nullable=True, index=True)

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

    # Evidence provenance (snapshotted at write time so historical rows do
    # not silently inherit a later change to the device's classification)
    provenance = Column(String(20), nullable=True, index=True)
    collection_interval_seconds = Column(Integer, nullable=True)

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
    rollback_performance = Column(JSON, nullable=True)  # Metrics after rollback
    rollback_success = Column(Boolean, nullable=True)
    rolled_back_at = Column(DateTime, nullable=True)

    # Evidence provenance (snapshotted at write time so historical rows do
    # not silently inherit a later change to the device's classification)
    provenance = Column(String(20), nullable=True, index=True)

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
    device_id = Column(String(100), index=True, nullable=True)
    job_id = Column(String(100), index=True, nullable=True)
    provider = Column(String(20), nullable=False)  # fcm, apns, mqtt, wns, web_push

    # Payload snapshot so the recipient/consumer can render the notification
    payload = Column(JSON, nullable=True)

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
        Index("idx_push_device", "device_id"),
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


class AIActionPlan(Base):
    """A device-management action (or batch) proposed by the AI.

    A plan is *proposed*, never executed directly: a deterministic executor
    applies approved steps. This row is the durable record of what the AI
    proposed, why, and how trustworthy the underlying context was, so outcome
    tracking and later autonomy decisions have a stable anchor.

    Status lifecycle mirrors ``docs/ai-delegation-plan.md``:
    ``proposed`` -> ``blocked`` | ``pending_approval`` -> ``approved`` |
    ``rejected`` -> ``executing`` -> ``succeeded`` | ``failed`` |
    ``rolled_back`` | ``expired``.
    """

    __tablename__ = "ai_action_plan"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(String(36), nullable=False, default=lambda: str(uuid4()))
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    # Link back to the AI query / audit event that produced the proposal.
    source_query_id = Column(String(36), nullable=True)

    # Link to the investigation session/run/message that produced the proposal
    # (Stage 5). Nullable: proposals can exist without an investigation.
    investigation_session_id = Column(String(36), nullable=True, index=True)
    investigation_run_id = Column(String(36), nullable=True, index=True)
    investigation_message_id = Column(String(36), nullable=True, index=True)

    # Trust envelope snapshot (from EnvelopeResult in ai/gates/envelope.py).
    trust_mode = Column(String(50), nullable=True)
    trust_score = Column(Float, nullable=True)
    passed_gates = Column(JSON, nullable=True)
    failed_gate = Column(String(50), nullable=True)

    # Classification and lifecycle.
    risk_tier = Column(String(10), nullable=True)  # T1..T4
    status = Column(String(20), nullable=False, default="proposed")
    reversible = Column(Boolean, nullable=False, default=False)

    # Explainability.
    rationale = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=True)

    created_by = Column(String(255), nullable=True)
    provenance = Column(String(20), nullable=True)

    # Relationships
    steps = relationship(
        "AIActionStep",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="AIActionStep.seq",
    )
    approvals = relationship(
        "AIActionApproval",
        back_populates="plan",
        cascade="all, delete-orphan",
    )
    outcome = relationship(
        "AIActionOutcome",
        back_populates="plan",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("plan_id", name="uq_ai_action_plan_plan_id"),
        Index("idx_ai_action_plan_status", "status"),
        Index("idx_ai_action_plan_risk_tier", "risk_tier"),
        Index("idx_ai_action_plan_source_query", "source_query_id"),
        Index("idx_ai_action_plan_session", "investigation_session_id"),
        Index("idx_ai_action_plan_run", "investigation_run_id"),
    )


class AIActionStep(Base):
    """A single ordered operation within an :class:`AIActionPlan`."""

    __tablename__ = "ai_action_step"

    id = Column(Integer, primary_key=True, index=True)
    step_id = Column(String(36), nullable=False, default=lambda: str(uuid4()))
    plan_id = Column(
        String(36),
        ForeignKey("ai_action_plan.plan_id", ondelete="CASCADE"),
        nullable=False,
    )
    seq = Column(Integer, nullable=False, default=0)

    action = Column(String(50), nullable=False)  # e.g. "update_config"
    target_device_id = Column(String(50), nullable=True)
    params = Column(JSON, nullable=True)
    preconditions = Column(JSON, nullable=True)
    postconditions = Column(JSON, nullable=True)
    rollback_params = Column(JSON, nullable=True)

    status = Column(String(20), nullable=False, default="pending")
    command_id = Column(String(36), nullable=True)  # links to device_commands

    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    # Relationships
    plan = relationship("AIActionPlan", back_populates="steps")

    __table_args__ = (
        UniqueConstraint("step_id", name="uq_ai_action_step_step_id"),
        Index("idx_ai_action_step_plan_id", "plan_id"),
        Index("idx_ai_action_step_target_device", "target_device_id"),
        Index("idx_ai_action_step_status", "status"),
    )


class AIActionApproval(Base):
    """A technician's decision on an :class:`AIActionPlan`."""

    __tablename__ = "ai_approval"

    id = Column(Integer, primary_key=True, index=True)
    approval_id = Column(String(36), nullable=False, default=lambda: str(uuid4()))
    plan_id = Column(
        String(36),
        ForeignKey("ai_action_plan.plan_id", ondelete="CASCADE"),
        nullable=False,
    )

    actor = Column(String(255), nullable=False)
    decision = Column(String(20), nullable=False)  # approved | rejected
    reason = Column(Text, nullable=True)
    decided_at = Column(DateTime, nullable=False, default=utc_now)
    device_scope = Column(JSON, nullable=True)

    # Relationships
    plan = relationship("AIActionPlan", back_populates="approvals")

    __table_args__ = (
        UniqueConstraint("approval_id", name="uq_ai_approval_approval_id"),
        Index("idx_ai_approval_plan_id", "plan_id"),
    )


class AIActionOutcome(Base):
    """The verified real-world result of an :class:`AIActionPlan`.

    One outcome per plan: this is the evidence that turns "the AI was probably
    right" into measured reliability and confidence calibration.
    """

    __tablename__ = "ai_outcome"

    id = Column(Integer, primary_key=True, index=True)
    outcome_id = Column(String(36), nullable=False, default=lambda: str(uuid4()))
    plan_id = Column(
        String(36),
        ForeignKey("ai_action_plan.plan_id", ondelete="CASCADE"),
        nullable=False,
    )

    verified = Column(Boolean, nullable=False, default=False)
    metrics_before = Column(JSON, nullable=True)
    metrics_after = Column(JSON, nullable=True)
    rolled_back = Column(Boolean, nullable=False, default=False)
    rollback_success = Column(Boolean, nullable=True)
    error = Column(Text, nullable=True)
    recorded_at = Column(DateTime, nullable=False, default=utc_now)
    provenance = Column(String(20), nullable=True)

    # Relationships
    plan = relationship("AIActionPlan", back_populates="outcome")

    __table_args__ = (
        UniqueConstraint("outcome_id", name="uq_ai_outcome_outcome_id"),
        UniqueConstraint("plan_id", name="uq_ai_outcome_plan_id"),
    )
