"""Simple model tests for HOMEPOT Client.

This module provides tests for SQLAlchemy model definitions,
relationships, and model-specific functionality.
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from homepot.models import (
    Base,
    Device,
    DeviceStatus,
    DeviceType,
    Job,
    JobPriority,
    JobStatus,
    Site,
    User,
)


@pytest.fixture
def memory_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    yield SessionLocal

    # Cleanup is automatic with in-memory database


def test_site_model_creation(memory_db):
    """Test Site model creation and basic attributes."""
    db = memory_db()

    site = Site(
        site_id="test-site-001",
        name="Test Restaurant",
        description="A test restaurant location",
        location="123 Test Street, Test City",
    )

    db.add(site)
    db.commit()

    # Test attributes
    assert site.id is not None
    assert site.site_id == "test-site-001"
    assert site.name == "Test Restaurant"
    assert site.description == "A test restaurant location"
    assert site.location == "123 Test Street, Test City"
    assert site.is_active is True  # Default value
    assert isinstance(site.created_at, datetime)
    assert isinstance(site.updated_at, datetime)

    db.close()


def test_device_model_creation(memory_db):
    """Test Device model creation and relationships."""
    db = memory_db()

    # Create a site first
    site = Site(site_id="site-001", name="Test Site", location="Test Location")
    db.add(site)
    db.commit()

    # Create a device
    device = Device(
        device_id="pos-terminal-001",
        name="Main POS Terminal",
        device_type=DeviceType.POS_TERMINAL,
        status=DeviceStatus.ONLINE,
        site_id=site.site_id,
        ip_address="192.168.1.100",
        mac_address="00:11:22:33:44:55",
        firmware_version="v2.1.0",
    )

    db.add(device)
    db.commit()

    # Test attributes
    assert device.id is not None
    assert device.device_id == "pos-terminal-001"
    assert device.name == "Main POS Terminal"
    assert device.device_type == DeviceType.POS_TERMINAL
    assert device.status == DeviceStatus.ONLINE
    assert device.site_id == site.site_id
    assert device.ip_address == "192.168.1.100"
    assert device.mac_address == "00:11:22:33:44:55"
    assert device.firmware_version == "v2.1.0"
    assert device.is_active is True

    db.close()


def test_user_model_creation(memory_db):
    """Test User model creation."""
    db = memory_db()

    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashed_password_123",  # noqa: S106
        api_key="test-api-key-123",
        is_admin=True,
    )

    db.add(user)
    db.commit()

    # Test attributes
    assert user.id is not None
    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.hashed_password == "hashed_password_123"
    assert user.api_key == "test-api-key-123"
    assert user.is_active is True  # Default
    assert user.is_admin is True

    db.close()


def test_job_model_creation(memory_db):
    """Test Job model creation with relationships."""
    db = memory_db()

    # Create dependencies
    site = Site(site_id="site-001", name="Test Site", location="Test Location")
    user = User(
        username="jobcreator",
        email="creator@example.com",
        hashed_password="hashed123",  # noqa: S106
    )

    db.add_all([site, user])
    db.commit()

    # Create job
    job = Job(
        job_id="job-001",
        action="Update POS configuration",
        description="Update payment processing settings",
        priority=JobPriority.HIGH,
        status=JobStatus.PENDING,
        site_id=site.id,
        created_by=user.id,
        payload={"config_type": "payment", "version": "2.1"},
        ttl_seconds=600,
    )

    db.add(job)
    db.commit()

    # Test attributes
    assert job.id is not None
    assert job.job_id == "job-001"
    assert job.action == "Update POS configuration"
    assert job.priority == JobPriority.HIGH
    assert job.status == JobStatus.PENDING
    assert job.site_id == site.id
    assert job.created_by == user.id
    assert job.payload == {"config_type": "payment", "version": "2.1"}
    assert job.ttl_seconds == 600

    db.close()


def test_site_device_relationship(memory_db):
    """Test the relationship between Site and Device models."""
    db = memory_db()

    # Create a site
    site = Site(
        site_id="restaurant-001", name="Main Restaurant", location="Downtown Location"
    )
    db.add(site)
    db.commit()

    # Create multiple devices for the site
    device1 = Device(
        device_id="pos-001",
        name="Register 1",
        device_type=DeviceType.POS_TERMINAL,
        site_id=site.id,
    )
    device2 = Device(
        device_id="pos-002",
        name="Register 2",
        device_type=DeviceType.POS_TERMINAL,
        site_id=site.id,
    )
    device3 = Device(
        device_id="sensor-001",
        name="Temperature Sensor",
        device_type=DeviceType.IOT_SENSOR,
        site_id=site.id,
    )

    db.add_all([device1, device2, device3])
    db.commit()

    # Test relationship from site to devices
    db.refresh(site)
    assert len(site.devices) == 3

    device_names = [device.name for device in site.devices]
    assert "Register 1" in device_names
    assert "Register 2" in device_names
    assert "Temperature Sensor" in device_names

    # Test relationship from device to site
    db.refresh(device1)
    assert device1.site.name == "Main Restaurant"
    assert device1.site.site_id == "restaurant-001"

    db.close()


def test_job_relationships(memory_db):
    """Test Job model relationships with Site and User."""
    db = memory_db()

    # Create dependencies
    site = Site(site_id="site-001", name="Test Site", location="Test Location")
    device = Device(
        device_id="device-001",
        name="Test Device",
        device_type=DeviceType.POS_TERMINAL,
        site_id=1,
    )
    user = User(
        username="admin",
        email="admin@example.com",
        hashed_password="hashed123",  # noqa: S106
    )

    db.add_all([site, device, user])
    db.commit()

    # Update device with correct site_id after commit
    device.site_id = site.id
    db.commit()

    # Create jobs
    job1 = Job(
        job_id="job-001", action="Site maintenance", site_id=site.id, created_by=user.id
    )
    job2 = Job(
        job_id="job-002",
        action="Device update",
        site_id=site.id,
        device_id=device.id,
        created_by=user.id,
    )

    db.add_all([job1, job2])
    db.commit()

    # Test site -> jobs relationship
    db.refresh(site)
    assert len(site.jobs) == 2

    # Test device -> jobs relationship
    db.refresh(device)
    assert len(device.jobs) == 1
    assert device.jobs[0].action == "Device update"

    # Test user -> jobs relationship
    db.refresh(user)
    assert len(user.jobs) == 2

    # Test job -> relationships
    db.refresh(job1)
    assert job1.site.name == "Test Site"
    assert job1.created_by_user.username == "admin"

    db.refresh(job2)
    assert job2.target_device.name == "Test Device"

    db.close()


def test_enum_values():
    """Test that enum values are correctly defined."""
    # Test JobStatus enum
    assert JobStatus.PENDING == "pending"
    assert JobStatus.QUEUED == "queued"
    assert JobStatus.COMPLETED == "completed"
    assert JobStatus.FAILED == "failed"

    # Test JobPriority enum
    assert JobPriority.LOW == "low"
    assert JobPriority.NORMAL == "normal"
    assert JobPriority.HIGH == "high"
    assert JobPriority.CRITICAL == "critical"

    # Test DeviceType enum
    assert DeviceType.POS_TERMINAL == "pos_terminal"
    assert DeviceType.IOT_SENSOR == "iot_sensor"
    assert DeviceType.INDUSTRIAL_CONTROLLER == "industrial_controller"
    assert DeviceType.GATEWAY == "gateway"

    # Test DeviceStatus enum
    assert DeviceStatus.ONLINE == "online"
    assert DeviceStatus.OFFLINE == "offline"
    assert DeviceStatus.MAINTENANCE == "maintenance"
    assert DeviceStatus.ERROR == "error"


def test_model_string_representations(memory_db):
    """Test model string representations if defined."""
    db = memory_db()

    site = Site(site_id="site-001", name="Test Site", location="Test Location")
    db.add(site)
    db.commit()

    # Test that model instances can be created and have basic attributes
    assert hasattr(site, "id")
    assert hasattr(site, "site_id")
    assert hasattr(site, "name")
    assert hasattr(site, "created_at")

    db.close()


def test_model_defaults(memory_db):
    """Test that model default values are set correctly."""
    db = memory_db()

    # Test Site defaults
    site = Site(site_id="site-001", name="Test Site")
    db.add(site)
    db.commit()

    assert site.is_active is True
    assert site.created_at is not None
    assert site.updated_at is not None

    # Test User defaults
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashed123",  # noqa: S106
    )
    db.add(user)
    db.commit()

    assert user.is_active is True
    assert user.is_admin is False

    # Test Device defaults
    device = Device(
        device_id="device-001",
        name="Test Device",
        device_type=DeviceType.POS_TERMINAL,
        site_id=site.id,
    )
    db.add(device)
    db.commit()

    assert device.status == DeviceStatus.UNKNOWN
    assert device.is_active is True

    db.close()


def test_required_fields(memory_db):
    """Test that required fields are enforced."""
    db = memory_db()

    # Test Site required fields - site_id is required
    with pytest.raises(Exception):  # Should fail without site_id
        site = Site(name="Test Site")
        db.add(site)
        db.commit()

    # Rollback after failed transaction
    db.rollback()

    # Test Device required fields - device_id is required
    site = Site(site_id="site-001", name="Valid Site", location="Test")
    db.add(site)
    db.commit()

    with pytest.raises(Exception):  # Should fail without device_id
        device = Device(
            name="Test Device", device_type=DeviceType.POS_TERMINAL, site_id=site.id
        )
        db.add(device)
        db.commit()

    db.close()
