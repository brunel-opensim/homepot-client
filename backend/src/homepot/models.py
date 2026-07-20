"""Database models for HOMEPOT Client.

This module defines SQLAlchemy models for the HOMEPOT system including
devices, jobs, users, and audit logs.
"""

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Engine,
    Float,
    ForeignKey,
    Integer,
    Sequence,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker


def utc_now() -> datetime:
    """Return current UTC time using timezone-aware datetime.

    Replaces deprecated datetime.utcnow() with datetime.now(timezone.utc).
    """
    return datetime.now(timezone.utc)


# Create declarative base for SQLAlchemy models using modern approach
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class JobStatus(str, Enum):
    """Job status enumeration."""

    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(str, Enum):
    """Job priority enumeration."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class DeviceType(str, Enum):
    """Device type enumeration."""

    POS_TERMINAL = "pos_terminal"
    IOT_SENSOR = "iot_sensor"
    INDUSTRIAL_CONTROLLER = "industrial_controller"
    GATEWAY = "gateway"
    UNKNOWN = "unknown"


class DeviceStatus(str, Enum):
    """Device status enumeration.

    Deprecated: Use LifecycleState, ConnectivityState, and HealthState instead.
    """

    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    ERROR = "error"
    UNPAIRED = "unpaired"
    UNKNOWN = "unknown"


class LifecycleState(str, Enum):
    """Device lifecycle state — the administrative management phase."""

    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    UNPAIRED = "unpaired"
    RETIRED = "retired"


class ConnectivityState(str, Enum):
    """Device connectivity — computed from authenticated heartbeat recency."""

    UNKNOWN = "unknown"
    ONLINE = "online"
    OFFLINE = "offline"


class HealthState(str, Enum):
    """Device health — aggregated from health checks, metrics and errors."""

    HEALTHY = "healthy"
    WARNING = "warning"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class EnrollmentMethod(str, Enum):
    """Enrollment method enumeration for devices."""

    PRE_PROVISIONED = "pre-provisioned"
    SELF_ENROLLED = "self-enrolled"


class EnrolmentIntentStatus(str, Enum):
    """Status of an enrolment intent."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    REVOKED = "revoked"


class CommandStatus(str, Enum):
    """Command status enumeration."""

    PENDING = "pending"
    SENT = "sent"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class Tenant(Base):
    """Tenant/Organisation model for multi-tenancy support."""

    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), unique=True, index=True, nullable=False)
    settings = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    sites = relationship("Site", back_populates="tenant")
    memberships = relationship("TenantMembership", back_populates="tenant")
    enrolment_intents = relationship(
        "EnrolmentIntent",
        back_populates="tenant",
        foreign_keys="EnrolmentIntent.tenant_id",
    )


class TenantMembership(Base):
    """User membership in a tenant with a role."""

    __tablename__ = "tenant_memberships"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    role = Column(String(50), default="member")  # admin, operator, installer, member
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    user = relationship("User", back_populates="tenant_memberships")
    tenant = relationship("Tenant", back_populates="memberships")


class SiteMembership(Base):
    """User membership in a site with a role."""

    __tablename__ = "site_memberships"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    role = Column(String(50), default="viewer")  # admin, operator, installer, viewer
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    user = relationship("User", back_populates="site_memberships")
    site = relationship("Site", back_populates="memberships")


class User(Base):
    """User model for authentication."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    api_key = Column(String(255), unique=True, index=True, nullable=True)
    role = Column(String(50), default="Client")
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    jobs = relationship("Job", back_populates="created_by_user")
    tenant = relationship("Tenant", foreign_keys=[tenant_id])
    tenant_memberships = relationship("TenantMembership", back_populates="user")
    site_memberships = relationship("SiteMembership", back_populates="user")
    enrolment_intents = relationship(
        "EnrolmentIntent",
        back_populates="creator",
        foreign_keys="EnrolmentIntent.creator_id",
    )


class Site(Base):
    """Site model representing physical locations."""

    __tablename__ = "sites"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(
        String(50), unique=True, index=True, nullable=False
    )  # e.g., "site-123"
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(200), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    is_monitored = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    tenant = relationship("Tenant", back_populates="sites")
    devices = relationship("Device", back_populates="site")
    jobs = relationship("Job", back_populates="site")
    memberships = relationship("SiteMembership", back_populates="site")
    enrolment_intents = relationship("EnrolmentIntent", back_populates="site")


class EnrolmentIntent(Base):
    """A durable enrolment-intent record representing a pending device enrolment."""

    __tablename__ = "enrolment_intents"

    id = Column(Integer, primary_key=True, index=True)
    intent_id = Column(String(36), unique=True, index=True, nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    enrolment_method = Column(String(50), nullable=False)  # EnrollmentMethod enum
    expected_device_identity = Column(String(100), nullable=True)
    claim_token_hash = Column(String(255), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), default=EnrolmentIntentStatus.PENDING, nullable=False)
    idempotency_key = Column(String(100), unique=True, index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    site = relationship("Site", back_populates="enrolment_intents")
    tenant = relationship("Tenant")
    creator = relationship("User", foreign_keys=[creator_id])


class LifecycleEpoch(Base):
    """A lifecycle epoch tracks a period in a device's operational life.

    An epoch begins when a device is claimed (pre-provisioned flow) and
    ends when the device is unpaired or retired.  Each claim creates a
    new epoch; subsequent state transitions (active, suspended, etc.)
    update the current epoch without ending it.
    """

    __tablename__ = "lifecycle_epochs"

    id = Column(Integer, primary_key=True, index=True)
    epoch_id = Column(String(36), unique=True, index=True, nullable=False)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    claim_token_hash = Column(String(255), nullable=True)
    enrolment_method = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    device = relationship(
        "Device",
        foreign_keys=[device_id],
        back_populates="lifecycle_epochs",
    )


class DeviceCredential(Base):
    """A single device API-credential version.

    Each time a device is issued a new API key a ``DeviceCredential``
    record is created.  The plaintext key is returned **only** at
    issuance or rotation; only the hash is persisted.
    """

    __tablename__ = "device_credentials"

    id = Column(Integer, primary_key=True, index=True)
    credential_id = Column(String(36), unique=True, index=True, nullable=False)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    key_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    rotated_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    device = relationship("Device", back_populates="credentials")


class Device(Base):
    """Device model representing end-points and OT devices."""

    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    device_type = Column(String(50), nullable=False)  # DeviceType enum
    status = Column(
        String(20), default=DeviceStatus.UNKNOWN
    )  # DEPRECATED: use lifecycle_state, connectivity_state, health_state
    lifecycle_state = Column(String(20), default=LifecycleState.PENDING, nullable=False)
    health_state = Column(String(20), default=HealthState.UNKNOWN, nullable=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    enrollment_method = Column(String(50), nullable=True)  # EnrollmentMethod enum
    enrollment_token = Column(String(255), nullable=True)

    # Current lifecycle epoch (set at claim time)
    lifecycle_epoch_id = Column(
        Integer, ForeignKey("lifecycle_epochs.id"), nullable=True
    )

    # Device specifications
    ip_address = Column(String(45), nullable=True)  # IPv4/IPv6
    mac_address = Column(String(17), nullable=True)
    os_details = Column(String(255), nullable=True)
    local_ip = Column(String(45), nullable=True)
    wan_ip = Column(String(45), nullable=True)
    firmware_version = Column(String(50), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    peripherals = Column(JSON, nullable=True)  # Attached device hardware

    # Configuration
    config = Column(JSON, nullable=True)  # Device-specific configuration

    # Authentication
    api_key_hash = Column(
        String(255), nullable=True
    )  # Hashed API key for device authentication

    # Metadata
    # DEPRECATED: use lifecycle_state — active/pending/suspended → True, unpaired/retired → False
    is_active = Column(Boolean, default=True)
    is_monitored = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    site = relationship("Site", back_populates="devices")
    jobs = relationship("Job", back_populates="target_device")
    health_checks = relationship("HealthCheck", back_populates="device")
    commands = relationship("DeviceCommand", back_populates="device")
    audit_logs = relationship("AuditLog", back_populates="device")

    # Smart Relationship for Polymorphic Configuration History
    # Joins on string device_id and filters by entity_type='device'
    config_history = relationship(
        "ConfigurationHistory",
        primaryjoin="and_("
        "foreign(ConfigurationHistory.entity_id) == Device.device_id, "
        "ConfigurationHistory.entity_type == 'device'"
        ")",
        viewonly=True,
        uselist=True,
    )

    # Smart Relationship for Error Logs (String ID Match)
    # Commented out because ErrorLog.device_id does not exist in DB yet
    # error_logs = relationship(
    #     "ErrorLog",
    #     primaryjoin="foreign(ErrorLog.device_id) == Device.device_id",
    #     viewonly=True,
    #     uselist=True,
    # )

    # Smart Relationship for Job Outcomes (String ID Match)
    job_outcomes = relationship(
        "JobOutcome",
        primaryjoin="foreign(JobOutcome.device_id) == Device.device_id",
        viewonly=True,
        uselist=True,
    )

    # Smart Relationship for API Request Logs (String ID Match)
    # Commented out because APIRequestLog.device_id does not exist in DB yet
    # api_request_logs = relationship(
    #     "APIRequestLog",
    #     primaryjoin="foreign(APIRequestLog.device_id) == Device.device_id",
    #     viewonly=True,
    #     uselist=True,
    # )

    # Smart Relationship for Push Notification Logs (String ID Match)
    # Commented out because PushNotificationLog.device_id does not exist in DB yet
    # push_logs = relationship(
    #     "PushNotificationLog",
    #     primaryjoin="foreign(PushNotificationLog.device_id) == Device.device_id",
    #     viewonly=True,
    #     uselist=True,
    # )

    # Smart Relationship for User Activities (String ID Match)
    # Commented out because UserActivity.device_id does not exist in DB yet
    # user_activities = relationship(
    #     "UserActivity",
    #     primaryjoin="foreign(UserActivity.device_id) == Device.device_id",
    #     viewonly=True,
    #     uselist=True,
    # )

    # Smart Relationship for Alerts (String ID Match)
    alerts = relationship(
        "Alert",
        primaryjoin="foreign(Alert.device_id) == Device.device_id",
        viewonly=True,
        uselist=True,
        lazy="select",
    )

    # Analytics Relationships
    metrics = relationship(
        "DeviceMetrics",
        back_populates="device",
        lazy="select",
        cascade="all, delete-orphan",
    )

    state_history = relationship(
        "DeviceStateHistory",
        back_populates="device",
        lazy="select",
        cascade="all, delete-orphan",
    )

    lifecycle_epochs = relationship(
        "LifecycleEpoch",
        foreign_keys="LifecycleEpoch.device_id",
        back_populates="device",
        lazy="select",
        cascade="all, delete-orphan",
    )

    credentials = relationship(
        "DeviceCredential",
        back_populates="device",
        lazy="select",
        cascade="all, delete-orphan",
    )

    assignments = relationship(
        "DeviceAssignment",
        back_populates="device",
        lazy="select",
        cascade="all, delete-orphan",
    )

    lifecycle_events = relationship(
        "DeviceLifecycleEvent",
        foreign_keys="DeviceLifecycleEvent.device_id",
        back_populates="device",
        lazy="select",
        cascade="all, delete-orphan",
    )


class DeviceCommand(Base):
    """Command queue for specific devices."""

    __tablename__ = "device_commands"

    id = Column(Integer, primary_key=True, index=True)
    command_id = Column(String(50), unique=True, index=True, nullable=False)  # UUID
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)

    command_type = Column(
        String(50), nullable=False
    )  # e.g. "restart", "update_config", "ping"
    payload = Column(JSON, nullable=True)

    status = Column(String(20), default=CommandStatus.PENDING)
    result = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now)
    executed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    device = relationship("Device", back_populates="commands")


class Job(Base):
    """Job model for tracking device management tasks."""

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(100), unique=True, index=True, nullable=False)

    # Job details
    action = Column(String(100), nullable=False)  # e.g., "Update POS payment config"
    description = Column(Text, nullable=True)
    priority = Column(String(20), default=JobPriority.NORMAL)
    status = Column(String(20), default=JobStatus.PENDING)

    # Targeting
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    device_id = Column(
        Integer, ForeignKey("devices.id"), nullable=True
    )  # Null for site-wide jobs
    segment = Column(String(100), nullable=True)  # e.g., "pos-terminals"

    # Payload and configuration
    payload = Column(JSON, nullable=True)  # Job-specific data
    config_url = Column(String(500), nullable=True)
    config_version = Column(String(50), nullable=True)
    ttl_seconds = Column(Integer, default=300)  # Time to live
    collapse_key = Column(String(100), nullable=True)  # For push notification grouping

    # Timing
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Result
    result = Column(JSON, nullable=True)  # Job execution result
    error_message = Column(Text, nullable=True)

    # Audit
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    site = relationship("Site", back_populates="jobs")
    target_device = relationship("Device", back_populates="jobs")
    created_by_user = relationship("User", back_populates="jobs")
    logs = relationship("AuditLog", back_populates="job")


class HealthCheck(Base):
    """Health check model for device monitoring.

    Note: Uses composite primary key (id, timestamp) for TimescaleDB
    hypertable support. SQLite compatibility: autoincrement removed as
    it's not supported for composite primary keys.
    """

    __tablename__ = "health_checks"

    id = Column(Integer, Sequence("health_checks_id_seq"), primary_key=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)

    # Health status
    is_healthy = Column(Boolean, nullable=False)
    response_time_ms = Column(Integer, nullable=True)
    status_code = Column(Integer, nullable=True)
    endpoint = Column(String(200), nullable=True)  # Health check endpoint

    # Results
    response_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timing - primary key component for TimescaleDB partitioning
    timestamp = Column(
        DateTime(timezone=True),
        primary_key=True,
        default=utc_now,
        nullable=False,
    )

    # Relationships
    device = relationship("Device", back_populates="health_checks")


class AuditLog(Base):
    """Audit log model for tracking system events."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Event details
    event_type = Column(
        String(50), nullable=False
    )  # e.g., "job_created", "device_updated"
    description = Column(Text, nullable=False)

    # Context
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)

    # Data
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    event_metadata = Column(
        JSON, nullable=True
    )  # Renamed from 'metadata' to avoid SQLAlchemy conflict

    # Request context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Timing
    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    job = relationship("Job", back_populates="logs")
    device = relationship("Device", back_populates="audit_logs")


class DeviceAssignment(Base):
    """Assignment history: records which site a device belonged to.

    Each row represents one assignment period.  Only one row per device
    may have ``is_current = True`` at any time.  Historical rows are
    retained so that old telemetry retains its ownership scope.
    """

    __tablename__ = "device_assignments"

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(String(36), unique=True, index=True, nullable=False)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)

    assignment_reason = Column(
        String(100), nullable=True
    )  # e.g. "initial_enrolment", "transfer", "reassignment"
    assigned_at = Column(DateTime(timezone=True), nullable=False)
    unassigned_at = Column(DateTime(timezone=True), nullable=True)

    is_current = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    device = relationship("Device", back_populates="assignments")
    site = relationship("Site")
    tenant = relationship("Tenant")


class DeviceLifecycleEvent(Base):
    """A single lifecycle-state transition for a device.

    Every transition (pending → active, active → suspended,
    active → unpaired, etc.) produces one event.  This provides
    an auditable, ordered history independent of the AuditLog
    (which is broader in scope).
    """

    __tablename__ = "device_lifecycle_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(36), unique=True, index=True, nullable=False)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    epoch_id = Column(
        Integer, ForeignKey("lifecycle_epochs.id"), nullable=True, index=True
    )

    from_state = Column(String(20), nullable=True)  # previous lifecycle_state
    to_state = Column(String(20), nullable=True)  # new lifecycle_state

    triggered_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    triggered_by_device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)

    reason = Column(Text, nullable=True)
    idempotency_key = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    device = relationship(
        "Device",
        foreign_keys=[device_id],
        back_populates="lifecycle_events",
    )
    triggered_by_device = relationship(
        "Device",
        foreign_keys=[triggered_by_device_id],
    )
    triggered_by_user = relationship("User")
    epoch = relationship("LifecycleEpoch")


# Database engine and session configuration
def create_database_engine(database_url: str = "sqlite:///./homepot.db") -> Engine:
    """Create database engine with appropriate configuration."""
    if database_url.startswith("sqlite"):
        # SQLite specific configuration
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},  # Allow multiple threads
            echo=False,  # Set to True for SQL debugging
        )
    else:
        # PostgreSQL and other databases
        engine = create_engine(database_url, echo=False)

    return engine


def create_tables(engine: Engine) -> None:
    """Create all tables in the database."""
    Base.metadata.create_all(bind=engine)


def get_session_maker(engine: Engine) -> sessionmaker:
    """Create session maker for database operations."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)
