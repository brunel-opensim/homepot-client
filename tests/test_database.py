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

from src.homepot_client.models import Base, Site, Device, Job, JobStatus, User
from src.homepot_client.config import get_settings


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    # Create temporary database file
    temp_dir = tempfile.mkdtemp()
    temp_db_path = Path(temp_dir) / "test_homepot.db"

    # Create engine and tables
    engine = create_engine(f"sqlite:///{temp_db_path}")
    Base.metadata.create_all(engine)

    # Create session factory
    SessionLocal = sessionmaker(bind=engine)

    yield SessionLocal

    # Cleanup
    temp_db_path.unlink(missing_ok=True)


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
        username="testuser", email="test@example.com", hashed_password="hashed123"
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
    """Test that required database tables exist in the demo database."""
    settings = get_settings()

    # Skip if not using SQLite (production might use PostgreSQL)
    if "sqlite" not in settings.database.url:
        pytest.skip("Test only runs with SQLite database")

    # Extract database path from URL
    db_path = settings.database.url.replace("sqlite:///", "")
    if not db_path.startswith("/"):
        db_path = f"./{db_path}"

    # Check if database file exists
    if not os.path.exists(db_path):
        pytest.skip(f"Database file not found: {db_path}")

    # Connect and check tables
    engine = create_engine(settings.database.url)

    with engine.connect() as conn:
        # Check that main tables exist
        tables_query = text(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """
        )

        result = conn.execute(tables_query)
        table_names = [row[0] for row in result]

        # Verify core tables exist
        expected_tables = ["sites", "devices", "jobs", "users"]
        for table in expected_tables:
            assert table in table_names, f"Table '{table}' not found in database"


def test_demo_data_exists():
    """Test that demo data exists in the database."""
    settings = get_settings()

    # Skip if not using SQLite
    if "sqlite" not in settings.database.url:
        pytest.skip("Test only runs with SQLite database")

    db_path = settings.database.url.replace("sqlite:///", "")
    if not db_path.startswith("/"):
        db_path = f"./{db_path}"

    if not os.path.exists(db_path):
        pytest.skip(f"Database file not found: {db_path}")

    engine = create_engine(settings.database.url)

    with engine.connect() as conn:
        # Check that we have demo sites
        sites_query = text("SELECT COUNT(*) FROM sites")
        site_count = conn.execute(sites_query).scalar()

        assert site_count > 0, "No demo sites found in database"
        assert site_count >= 10, f"Expected at least 10 demo sites, found {site_count}"

        # Check that we have demo devices
        devices_query = text("SELECT COUNT(*) FROM devices")
        device_count = conn.execute(devices_query).scalar()

        assert device_count > 0, "No demo devices found in database"
        assert (
            device_count >= 20
        ), f"Expected at least 20 demo devices, found {device_count}"
