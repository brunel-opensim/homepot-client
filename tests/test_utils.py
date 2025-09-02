"""Test utilities for Windows-compatible database testing.

This module provides utilities for handling database fixtures that work
reliably across platforms, especially Windows where file locking can
cause issues with SQLite cleanup.
"""

import os
import platform
import tempfile
import time
import warnings
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from src.homepot_client.models import Base


def create_windows_safe_temp_db() -> Generator[sessionmaker, None, None]:
    """Create a temporary database that cleans up safely on Windows.

    This fixture handles the Windows-specific file locking issues that
    occur when SQLite files can't be deleted immediately after use.

    Yields:
        sessionmaker: A SQLAlchemy session factory for the temp database
    """
    # Create temporary database file
    temp_dir = tempfile.mkdtemp()
    temp_db_path = Path(temp_dir) / "test_homepot.db"

    # Create engine and tables
    engine = create_engine(f"sqlite:///{temp_db_path}")
    Base.metadata.create_all(engine)

    # Create session factory
    SessionLocal = sessionmaker(bind=engine)

    try:
        yield SessionLocal
    finally:
        _cleanup_temp_database(engine, temp_db_path, temp_dir)


def create_windows_safe_pos_dummy_db() -> Generator[str, None, None]:
    """Create a temporary database for POSDummy tests with Windows-safe cleanup.

    This is specifically designed for POSDummy tests that need to set
    environment variables and handle cleanup differently.

    Yields:
        str: Path to the temporary database file
    """
    # Create temporary database file
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    engine = None
    try:
        # Set up test database
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)

        # Set environment variable for test database
        os.environ["HOMEPOT_DATABASE_URL"] = f"sqlite:///{db_path}"

        yield db_path
    finally:
        _cleanup_pos_dummy_database(engine, db_path)


def _cleanup_temp_database(engine: Engine, temp_db_path: Path, temp_dir: str) -> None:
    """Clean up temporary database with Windows-safe handling.

    Args:
        engine: SQLAlchemy engine to dispose
        temp_db_path: Path to the temporary database file
        temp_dir: Path to the temporary directory
    """
    try:
        # Dispose engine to close all connections
        engine.dispose()

        # On Windows, add small delay for file handles to be released
        if platform.system() == "Windows":
            time.sleep(0.1)

        # Try to remove the file, with Windows-specific retry logic
        if temp_db_path.exists():
            max_retries = 3 if platform.system() == "Windows" else 1
            for attempt in range(max_retries):
                try:
                    temp_db_path.unlink()
                    break
                except PermissionError:
                    if attempt < max_retries - 1 and platform.system() == "Windows":
                        time.sleep(0.2)
                        continue
                    # If all retries failed, log but don't fail the test
                    warnings.warn(f"Could not cleanup temp database: {temp_db_path}")
                    break
    except Exception as e:
        # Don't fail tests due to cleanup issues
        warnings.warn(f"Database cleanup error: {e}")
    finally:
        # Remove temp directory if empty
        try:
            temp_dir_path = Path(temp_dir)
            if temp_dir_path.exists() and not any(temp_dir_path.iterdir()):
                temp_dir_path.rmdir()
        except Exception:
            pass


def _cleanup_pos_dummy_database(engine: Engine, db_path: str) -> None:
    """Clean up POSDummy database with Windows-safe handling.

    Args:
        engine: SQLAlchemy engine to dispose
        db_path: Path to the database file
    """
    try:
        # Dispose engine to close all connections
        if engine is not None:
            engine.dispose()

        # On Windows, add small delay for file handles to be released
        if platform.system() == "Windows":
            time.sleep(0.1)

        # Clean up environment variable
        if "HOMEPOT_DATABASE_URL" in os.environ:
            del os.environ["HOMEPOT_DATABASE_URL"]

        # Try to remove the file with Windows-specific retry logic
        if os.path.exists(db_path):
            max_retries = 3 if platform.system() == "Windows" else 1
            for attempt in range(max_retries):
                try:
                    os.unlink(db_path)
                    break
                except PermissionError:
                    if attempt < max_retries - 1 and platform.system() == "Windows":
                        time.sleep(0.2)
                        continue
                    # If all retries failed, log but don't fail the test
                    warnings.warn(f"Could not cleanup temp database: {db_path}")
                    break
    except Exception as e:
        # Don't fail tests due to cleanup issues
        warnings.warn(f"Database cleanup error: {e}")
