"""Database models for HOMEPOT Client.

This module defines SQLAlchemy models for the HOMEPOT system including
devices, jobs, users, and audit logs.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .UserModel import Base


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
