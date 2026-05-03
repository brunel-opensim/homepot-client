"""Tests for the agent device DNA registration API."""

import asyncio
import os
import tempfile

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from homepot.config import reload_settings
import homepot.database
from homepot.models import Base, Device, Site


@pytest.fixture(autouse=True)
def mock_db_url(monkeypatch):
    """Use a temporary database for agent API tests."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    db_url = f"sqlite:///{path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DATABASE__URL", db_url)
    reload_settings()

    if homepot.database._db_service is not None:
        try:
            asyncio.run(homepot.database._db_service.close())
        except Exception:
            pass
        homepot.database._db_service = None

    new_engine = create_engine(
        db_url, connect_args={"check_same_thread": False}, pool_pre_ping=True
    )
    Base.metadata.create_all(bind=new_engine)
    new_session_local = sessionmaker(bind=new_engine, autocommit=False, autoflush=False)

    monkeypatch.setattr(homepot.database, "sync_engine", new_engine)
    monkeypatch.setattr(homepot.database, "SessionLocal", new_session_local)

    yield

    new_engine.dispose()
    if os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


def _seed_site(site_code: str = "site-agent-1") -> Site:
    """Seed a site record for registration tests."""
    db = homepot.database.SessionLocal()
    try:
        site = Site(site_id=site_code, name="Agent Test Site", location="Lab")
        db.add(site)
        db.commit()
        db.refresh(site)
        return site
    finally:
        db.close()


def test_device_dna_requires_site_for_new_device(client: TestClient):
    """Creating a new device without site_id should fail validation."""
    response = client.post(
        "/api/v1/agent/device-dna",
        json={
            "device_id": "agent-device-1",
            "mac_address": "00:11:22:33:44:55",
            "os_details": "Windows 11",
            "local_ip": "192.168.1.20",
            "wan_ip": "203.0.113.10",
        },
    )

    assert response.status_code == 400
    assert "site_id" in response.json()["detail"]


def test_device_dna_creates_new_device(client: TestClient):
    """Device DNA endpoint should create new records when device does not exist."""
    _seed_site("site-agent-1")

    response = client.post(
        "/api/v1/agent/device-dna",
        json={
            "device_id": "agent-device-1",
            "site_id": "site-agent-1",
            "device_name": "Front POS",
            "device_type": "physical_terminal",
            "mac_address": "00:11:22:33:44:55",
            "os_details": "Windows 11",
            "local_ip": "192.168.1.20",
            "wan_ip": "203.0.113.10",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["device_id"] == "agent-device-1"
    assert payload["data"]["created"] is True


def test_device_dna_updates_existing_device(client: TestClient):
    """Device DNA endpoint should update DNA fields for existing device records."""
    site = _seed_site("site-agent-2")

    db = homepot.database.SessionLocal()
    try:
        device = Device(
            device_id="agent-device-2",
            name="Agent Device",
            device_type="physical_terminal",
            site_id=int(site.id),
            is_active=True,
        )
        db.add(device)
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/v1/agent/device-dna",
        json={
            "device_id": "agent-device-2",
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "os_details": "Ubuntu 22.04",
            "local_ip": "10.0.0.20",
            "wan_ip": "198.51.100.20",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["device_id"] == "agent-device-2"
    assert payload["data"]["created"] is False
