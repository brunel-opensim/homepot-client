"""Database connection and session management for the HomePot Client application.

This module provides synchronous database access using unified configuration.
Supports both SQLite (development/testing) and PostgreSQL (production).
"""

import logging
import sys
from pathlib import Path
from typing import Any, Generator, Optional, cast

from sqlalchemy import create_engine, text
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

# Add parent directory to path to import homepot.config
# This is necessary for the synchronous API layer to access main config
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from homepot.config import get_settings  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get database URL from unified config system
settings = get_settings()
database_url = settings.database.url

# Convert async URLs to sync for this synchronous layer
if database_url.startswith("sqlite+aiosqlite://"):
    database_url = database_url.replace("sqlite+aiosqlite://", "sqlite:///")
elif database_url.startswith("postgresql+asyncpg://"):
    database_url = database_url.replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://"
    )

# Log database connection (hide credentials)
db_display = (
    database_url.split("@")[0] if "@" in database_url else database_url.split("///")[0]
)
logger.info(f"Configuring database connection: {db_display}")

try:
    # Create engine with database-specific configuration
    if database_url.startswith("sqlite"):
        engine = create_engine(
            database_url, connect_args={"check_same_thread": False}, pool_pre_ping=True
        )
        logger.info("Using SQLite database (sync)")
    elif database_url.startswith("postgresql"):
        engine = create_engine(
            database_url, pool_pre_ping=True, pool_size=5, max_overflow=10
        )
        logger.info("Using PostgreSQL database (sync)")
    else:
        raise ValueError(f"Unsupported database URL: {database_url}")

    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base = declarative_base()
    logger.info("Database engine created successfully.")
except OperationalError as e:
    logger.error("Failed to connect to the database: %s", e)
    raise


def get_db() -> Generator[Session, None, None]:
    """Dependency for getting a database session (FastAPI style)."""
    db = None
    try:
        db = SessionLocal()
        yield db
    except Exception as e:
        logger.error("Database session error: %s", e)
        raise
    finally:
        if db is not None:
            db.close()


def create_tables() -> None:
    """Create all database tables."""
    try:
        # from db import models  # Ensure models are imported
        Base.metadata.create_all(bind=engine)
        logger.info("All tables created successfully.")
    except Exception as e:
        logger.error("Error creating tables: %s", e)
        raise


def execute_update(sql: str, params: Optional[dict[str, Any]] = None) -> bool:
    """Execute an UPDATE or DELETE statement."""
    params = params or {}
    with SessionLocal() as session:
        raw_result = session.execute(text(sql), params)
        session.commit()
        # Correct cast for mypy
        result: CursorResult = cast(CursorResult, raw_result)
        row_count: int = result.rowcount or 0
        return row_count > 0


def insert_row(sql: str, params: Optional[dict[str, Any]] = None) -> bool:
    """Execute an INSERT statement and return True if any rows were inserted."""
    params = params or {}
    with SessionLocal() as session:
        raw_result = session.execute(text(sql), params)
        session.commit()
        # Correct cast for mypy
        result: CursorResult = cast(CursorResult, raw_result)
        row_count: int = result.rowcount or 0
        return row_count > 0
