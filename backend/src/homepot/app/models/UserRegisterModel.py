"""Database models for HOMEPOT Client.

This module defines SQLAlchemy models for the HOMEPOT system including
devices, jobs, users, and audit logs.
"""

from sqlalchemy import Column, DateTime, Integer, String, func

from homepot.app.db.database import Base

# from sqlalchemy.orm import relationship


class User(Base):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255))
    name = Column(String(255), nullable=True)
    # google_id = Column(String(255), unique=True, nullable=True)
    role = Column(String(50), nullable=False, default="User")  # New field
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    updated_date = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
