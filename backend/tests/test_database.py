"""Simple database tests for HOMEPOT Client.

This module provides basic tests for database connectivity,
model creation, and basic operations.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
from typing import Any, Dict

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from homepot.config import get_settings
from homepot.database import DatabaseService
from homepot.models import Base, Device, DeviceType, Job, JobStatus, Site, User


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    import platform
    import time

    # Create temporary database file
    temp_dir = tempfile.mkdtemp()
    temp_db_path = Path(temp_dir) / "test_homepot.db"

    # Create engine and tables
    engine = create_engine(f"sqlite:///{temp_db_path}")
    Base.metadata.create_all(engine)

    # Create session factory
    SessionLocal = sessionmaker(bind=engine)

    yield SessionLocal

    # Cleanup with proper connection disposal
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
                    import warnings

                    warnings.warn(f"Could not cleanup temp database: {temp_db_path}")
                    break
    except Exception as e:
        # Don't fail tests due to cleanup issues
        import warnings

        warnings.warn(f"Database cleanup error: {e}")
    finally:
        # Remove temp directory if empty
        try:
            temp_dir_path = Path(temp_dir)
            if temp_dir_path.exists() and not any(temp_dir_path.iterdir()):
                temp_dir_path.rmdir()
        except Exception:
            pass


def test_database_connection():
    """Test basic database connection."""
    settings = get_settings()
    # This should not raise an exception
    assert settings.database.url is not None
    assert "sqlite" in settings.database.url or "postgresql" in settings.database.url


def test_site_creation(temp_db):
    """Test creating a site in the database."""
    db = temp_db()

    # Create a test site with required site_id
    site = Site(
        site_id="test-site-001",
        name="test-restaurant",
        location="Test City, Test State",
    )

    db.add(site)
    db.commit()

    # Verify the site was created
    assert site.id is not None
    assert site.site_id == "test-site-001"
    assert site.name == "test-restaurant"
    assert site.location == "Test City, Test State"
    assert site.created_at is not None

    db.close()


def test_device_creation(temp_db):
    """Test creating a device linked to a site."""
    db = temp_db()

    # Create a site first
    site = Site(site_id="test-site-001", name="test-site", location="Test Location")
    db.add(site)
    db.commit()

    # Create a device with required device_id
    device = Device(
        device_id="pos-terminal-test-001",
        name="pos-terminal-test",
        device_type="pos_terminal",
        site_id=site.id,
    )

    db.add(device)
    db.commit()

    # Verify the device was created
    assert device.id is not None
    assert device.device_id == "pos-terminal-test-001"
    assert device.name == "pos-terminal-test"
    assert device.site_id == site.id
    assert device.created_at is not None

    db.close()


def test_job_creation(temp_db):
    """Test creating a job."""
    db = temp_db()

    # Create a site and user first (required for job)
    site = Site(site_id="test-site-001", name="test-site", location="Test Location")
    db.add(site)
    db.commit()

    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashed123",  # noqa: S106
    )
    db.add(user)
    db.commit()

    # Create a job with required fields
    job = Job(
        job_id="test-job-001",
        action="test-action",
        description="Test job description",
        status=JobStatus.PENDING,
        site_id=site.id,
        created_by=user.id,
    )

    db.add(job)
    db.commit()

    # Verify the job was created
    assert job.id is not None
    assert job.job_id == "test-job-001"
    assert job.action == "test-action"
    assert job.status == JobStatus.PENDING
    assert job.created_at is not None

    db.close()


def test_site_device_relationship(temp_db):
    """Test the relationship between sites and devices."""
    db = temp_db()

    # Create a site
    site = Site(
        site_id="restaurant-chain-001",
        name="restaurant-chain",
        location="Main Location",
    )
    db.add(site)
    db.commit()

    # Create multiple devices for the site
    device1 = Device(
        device_id="pos-1",
        name="pos-1",
        device_type="pos_terminal",
        site_id=site.id,
    )
    device2 = Device(
        device_id="pos-2",
        name="pos-2",
        device_type="pos_terminal",
        site_id=site.id,
    )

    db.add_all([device1, device2])
    db.commit()

    # Test the relationship
    db.refresh(site)  # Refresh to load relationships
    site_with_devices = db.query(Site).filter_by(site_id=site.site_id).first()

    assert site_with_devices is not None
    assert len(site_with_devices.devices) == 2
    assert device1 in site_with_devices.devices
    assert device2 in site_with_devices.devices

    db.close()


def test_database_query(temp_db):
    """Test basic database queries."""
    db = temp_db()

    # Create test data
    site1 = Site(site_id="site-1", name="site-1", location="Location 1")
    site2 = Site(site_id="site-2", name="site-2", location="Location 2")

    db.add_all([site1, site2])
    db.commit()

    # Test queries
    all_sites = db.query(Site).all()
    assert len(all_sites) == 2

    # Test filtering
    found_site = db.query(Site).filter_by(name="site-1").first()
    assert found_site is not None
    assert found_site.name == "site-1"

    # Test count
    site_count = db.query(Site).count()
    assert site_count == 2

    db.close()


def test_database_tables_exist(temp_db):
    """Test that required database tables exist in the test database."""
    # Get a session from the fixture
    db = temp_db()

    # Create a test query to verify tables exist by trying to query them
    # If tables don't exist, these queries will fail
    try:
        # Check sites table
        db.execute(text("SELECT COUNT(*) FROM sites")).scalar()

        # Check devices table
        db.execute(text("SELECT COUNT(*) FROM devices")).scalar()

        # Check jobs table
        db.execute(text("SELECT COUNT(*) FROM jobs")).scalar()

        # Check users table
        db.execute(text("SELECT COUNT(*) FROM users")).scalar()

        # If we get here, all tables exist
        assert True
    except Exception as e:
        pytest.fail(f"Database table check failed: {e}")


def test_demo_data_exists(temp_db):
    """Test that data can be created in the test database.

    This test verifies that the database schema is properly set up
    by creating test data and verifying relationships work correctly.
    """
    db = temp_db()

    # Create a test site
    site = Site(site_id="test-demo-site", name="Demo Restaurant", location="Demo City")
    db.add(site)
    db.commit()
    db.refresh(site)

    # Create a test device linked to the site
    device = Device(
        device_id="demo-device-001",
        name="Demo POS Terminal",
        device_type=DeviceType.POS_TERMINAL.value,
        site_id=site.id,
    )
    db.add(device)
    db.commit()

    # Verify the data exists and relationships work
    sites_count = db.query(Site).count()
    devices_count = db.query(Device).count()

    assert sites_count > 0, "No sites found in test database"
    assert devices_count > 0, "No devices found in test database"

    # Verify the device is properly linked to the site
    test_device = db.query(Device).filter_by(device_id="demo-device-001").first()
    assert test_device is not None, "Test device not found"
    assert test_device.site_id == site.id, "Device not properly linked to site"


class _FakeSettings:
    """Minimal settings stand-in exposing only ``database.url/echo_sql``."""

    class _DB:
        def __init__(self, url: str) -> None:
            self.url = url
            self.echo_sql = False

    def __init__(self, url: str) -> None:
        self.database = self._DB(url)


def _concurrent_schema_race_error() -> OperationalError:
    """Build an OperationalError matching a SQLite create_all collision."""
    return OperationalError(
        "CREATE TABLE users ...",
        {},
        sqlite3.OperationalError("table users already exists"),
    )


async def test_initialize_retries_on_concurrent_create_race(tmp_path, monkeypatch):
    """Retry schema init once when a parallel worker creates the tables first."""
    url = f"sqlite:///{tmp_path}/race.db"
    monkeypatch.setattr("homepot.database.get_settings", lambda: _FakeSettings(url))

    real_create_all = Base.metadata.create_all
    calls = {"n": 0}

    def flaky_create_all(bind, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _concurrent_schema_race_error()
        return real_create_all(bind, *args, **kwargs)

    monkeypatch.setattr(Base.metadata, "create_all", flaky_create_all)

    service = DatabaseService()
    await service.initialize()

    assert service._initialized is True
    assert calls["n"] == 2


async def test_initialize_does_not_retry_non_race_errors(tmp_path, monkeypatch):
    """Do not swallow genuine schema errors — raise immediately."""
    url = f"sqlite:///{tmp_path}/real.db"
    monkeypatch.setattr("homepot.database.get_settings", lambda: _FakeSettings(url))

    def failing_create_all(bind, *args, **kwargs):
        raise OperationalError("CREATE TABLE users ...", {}, Exception("syntax error"))

    monkeypatch.setattr(Base.metadata, "create_all", failing_create_all)

    service = DatabaseService()
    with pytest.raises(OperationalError):
        await service.initialize()

    assert service._initialized is False


class _FakeJobResult:
    """Minimal stand-in for ``Result`` with a rowcount attribute."""

    rowcount: int = 1


async def test_update_job_status_writes_tz_aware_timestamps(
    monkeypatch,
) -> None:
    """Assert job timing columns are sent to SQL as tz-aware UTC, not naive.

    Postgres round-trips tzinfo but SQLite strips it during storage, so the
    value bound to the generated ``UPDATE`` statement is asserted here rather
    than the DB round-trip — this is what fixes the hour-shifted agnostic
    ``completed_at`` rendered by the Dashboard.
    """
    captured: Dict[str, Any] = {}

    class _FakeSession:
        async def execute(self, stmt, *args, **kwargs):  # noqa: ANN001
            captured["stmt"] = stmt
            return _FakeJobResult()

    @asynccontextmanager
    async def fake_get_session(self_):  # noqa: ANN001
        yield _FakeSession()

    monkeypatch.setattr(DatabaseService, "get_session", fake_get_session)
    service = DatabaseService.__new__(DatabaseService)

    now = datetime.now(timezone.utc)
    assert (
        await service.update_job_status(
            "j-1", JobStatus.COMPLETED, result={"exit_code": 0}
        )
        is True
    )

    values = {k.name: v for k, v in captured["stmt"]._values.items()}
    assert values["completed_at"].value.tzinfo is not None
    assert values["updated_at"].value.tzinfo is not None
    assert abs((values["completed_at"].value - now).total_seconds()) < 5

    assert (
        await service.update_job_status("j-2", JobStatus.FAILED, error_message="boom")
        is True
    )
    values = {k.name: v for k, v in captured["stmt"]._values.items()}
    assert values["completed_at"].value.tzinfo is not None
