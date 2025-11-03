"""Databse connection and session management for the HomePot Client application."""

import logging
import os
from typing import Any, Generator, Optional, cast

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Build PostgreSQL connection URL
DataBaseUrl = (
    f"postgresql+psycopg2://{os.getenv('PGUSER')}:{os.getenv('PGPASSWORD')}"
    f"@{os.getenv('PGHOST')}/{os.getenv('PGDATABASE')}"
    f"?sslmode={os.getenv('PGSSLMODE', 'require')}"
)

try:
    engine = create_engine(DataBaseUrl, pool_pre_ping=True)
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
