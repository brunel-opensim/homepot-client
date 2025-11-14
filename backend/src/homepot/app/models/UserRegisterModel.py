"""Database models for HOMEPOT Client.

This module defines SQLAlchemy models for the HOMEPOT system including
devices, jobs, users, and audit logs.

Updated to match the main schema in homepot.models to ensure compatibility
with PostgreSQL migration.
"""

from sqlalchemy import Boolean, Column, DateTime, Integer, String, func

from homepot.app.db.database import Base


class User(Base):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    api_key = Column(String(255), unique=True, index=True, nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
