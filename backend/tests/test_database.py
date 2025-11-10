"""Simple database tests for HOMEPOT Client.

This module provides basic tests for database connectivity,
model creation, and basic operations.
"""

import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from homepot.config import get_settings
from homepot.models import Base, Device, Job, JobStatus, Site, User


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
        device_id="pos-1", name="pos-1", device_type="pos_terminal", site_id=site.id
    )
    device2 = Device(
        device_id="pos-2", name="pos-2", device_type="pos_terminal", site_id=site.id
    )

    db.add_all([device1, device2])
    db.commit()

    # Test the relationship
    db.refresh(site)  # Refresh to load relationships
    site_with_devices = db.query(Site).filter_by(id=site.id).first()

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


def test_database_tables_exist():
    """Test that required database tables exist in the database."""
    settings = get_settings()

    # Connect and check tables
    engine = create_engine(settings.database.url)

    with engine.connect() as conn:
        # Check that main tables exist using database-agnostic query
        if "sqlite" in settings.database.url:
            # SQLite-specific query
            tables_query = text(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """
            )
        else:
            # PostgreSQL query (also works with most SQL databases)
            tables_query = text(
                """
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
            """
            )

        result = conn.execute(tables_query)
        table_names = [row[0] for row in result]

        # Verify core tables exist
        expected_tables = ["sites", "devices", "jobs", "users"]
        for table in expected_tables:
            assert table in table_names, f"Table '{table}' not found in database"


def test_demo_data_exists():
    """Test that demo data exists in the database.

    This test verifies that the database contains at least some initial data,
    whether from init-database.sh seed data (2 sites, 8 devices) or from
    POSDummy test data (1 site, 1 device).
    
    Works with both SQLite and PostgreSQL databases.
    """
    settings = get_settings()

    engine = create_engine(settings.database.url)

    with engine.connect() as conn:
        # Check that we have at least one site
        sites_query = text("SELECT COUNT(*) FROM sites")
        site_count = conn.execute(sites_query).scalar()

        # Skip if database is empty (expected for fresh installs)
        if site_count == 0:
            pytest.skip("No sites found - database appears to be empty (expected for fresh installs)")

        # If we have sites, verify we also have devices
        devices_query = text("SELECT COUNT(*) FROM devices")
        device_count = conn.execute(devices_query).scalar()

        assert (
            device_count > 0
        ), "No devices found but sites exist - database may not be fully initialized"

        # Verify data consistency - devices should be linked to sites
        assert (
            device_count >= site_count
        ), f"Data inconsistency: found {device_count} devices but {site_count} sites"
