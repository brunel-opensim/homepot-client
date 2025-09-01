"""Database models for HOMEPOT Client.

This module defines SQLAlchemy models for the HOMEPOT system including
devices, jobs, users, and audit logs.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

# Create declarative base for SQLAlchemy models
Base = declarative_base()  # type: ignore[misc]


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
    """Device status enumeration."""

    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    ERROR = "error"
    UNKNOWN = "unknown"


class User(Base):
    """User model for authentication."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    api_key = Column(String(255), unique=True, index=True, nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    jobs = relationship("Job", back_populates="created_by_user")


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
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    devices = relationship("Device", back_populates="site")
    jobs = relationship("Job", back_populates="site")


class Device(Base):
    """Device model representing end-points and OT devices."""

    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    device_type = Column(String(50), nullable=False)  # DeviceType enum
    status = Column(String(20), default=DeviceStatus.UNKNOWN)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)

    # Device specifications
    ip_address = Column(String(45), nullable=True)  # IPv4/IPv6
    mac_address = Column(String(17), nullable=True)
    firmware_version = Column(String(50), nullable=True)
    last_seen = Column(DateTime, nullable=True)

    # Configuration
    config = Column(JSON, nullable=True)  # Device-specific configuration

    # Metadata
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    site = relationship("Site", back_populates="devices")
    jobs = relationship("Job", back_populates="target_device")
    health_checks = relationship("HealthCheck", back_populates="device")


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
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Result
    result = Column(JSON, nullable=True)  # Job execution result
    error_message = Column(Text, nullable=True)

    # Audit
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    site = relationship("Site", back_populates="jobs")
    target_device = relationship("Device", back_populates="jobs")
    created_by_user = relationship("User", back_populates="jobs")
    logs = relationship("AuditLog", back_populates="job")


class HealthCheck(Base):
    """Health check model for device monitoring."""

    __tablename__ = "health_checks"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)

    # Health status
    is_healthy = Column(Boolean, nullable=False)
    response_time_ms = Column(Integer, nullable=True)
    status_code = Column(Integer, nullable=True)
    endpoint = Column(String(200), nullable=True)  # Health check endpoint

    # Results
    response_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timing
    checked_at = Column(DateTime, default=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    job = relationship("Job", back_populates="logs")


# Database engine and session configuration
def create_database_engine(database_url: str = "sqlite:///./homepot.db"):
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


def create_tables(engine):
    """Create all tables in the database."""
    Base.metadata.create_all(bind=engine)


def get_session_maker(engine):
    """Create session maker for database operations."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)
