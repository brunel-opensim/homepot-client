"""Tests for agent registration, heartbeat, telemetry, provision, and status APIs."""

import asyncio
from datetime import datetime, timedelta, timezone
import os
import tempfile

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import homepot.database
from homepot.config import reload_settings
from homepot.models import Base, Device, Site
from homepot.app.models.AnalyticsModel import DeviceMetrics


@pytest.fixture(autouse=True)
def mock_db_url(monkeypatch):
    """Use a temporary SQLite DB so tests do not touch real data."""
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
    new_session_local = sessionmaker(
        bind=new_engine, autocommit=False, autoflush=False
    )

    monkeypatch.setattr(homepot.database, "sync_engine", new_engine)
    monkeypatch.setattr(homepot.database, "SessionLocal", new_session_local)

    yield

    new_engine.dispose()
    if os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


def _create_site(site_code: str = "site-agent-1") -> Site:
    """Create and return a site row for endpoint tests."""
    db = homepot.database.SessionLocal()
    try:
        site = Site(site_id=site_code, name="Agent Test Site", location="Lab")
        db.add(site)
        db.commit()
        db.refresh(site)
        return site
    finally:
        db.close()


def _create_device(device_id: str, site_pk: int) -> None:
    """Create a device row linked to a site primary key."""
    db = homepot.database.SessionLocal()
    try:
        device = Device(
            device_id=device_id,
            name="Agent Device",
            device_type="physical_terminal",
            site_id=site_pk,
            is_active=True,
        )
        db.add(device)
        db.commit()
    finally:
        db.close()


def test_register_creates_device(client: TestClient):
    """POST /api/v1/agent/device-dna should create a device if not present."""
    _create_site("site-agent-1")
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


def test_heartbeat_updates_last_heartbeat(client: TestClient):
    """POST /api/v1/agent/heartbeat should update last heartbeat timestamp."""
    site = _create_site("site-heartbeat")
    _create_device("heartbeat-device-1", int(site.id))

    now = datetime.now(timezone.utc).isoformat()
    response = client.post(
        "/api/v1/agent/heartbeat",
        json={"device_id": "heartbeat-device-1", "timestamp": now},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["device_id"] == "heartbeat-device-1"
    assert payload["data"]["last_heartbeat_at"] is not None


def test_telemetry_single_is_saved(client: TestClient):
    """POST /api/v1/agent/telemetry should persist a single telemetry record."""
    site = _create_site("site-telemetry-single")
    _create_device("telemetry-device-1", int(site.id))

    response = client.post(
        "/api/v1/agent/telemetry",
        json={
            "device_id": "telemetry-device-1",
            "cpu_usage": 20.1,
            "memory_usage": 55.4,
            "disk_usage": 44.8,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["saved_count"] == 1

    db = homepot.database.SessionLocal()
    try:
        metrics_count = db.execute(select(DeviceMetrics)).scalars().all()
        assert len(metrics_count) == 1
    finally:
        db.close()


def test_telemetry_bulk_is_saved(client: TestClient):
    """POST /api/v1/agent/telemetry should persist multiple telemetry records."""
    site = _create_site("site-telemetry-bulk")
    _create_device("telemetry-device-2", int(site.id))

    now = datetime.now(timezone.utc)
    response = client.post(
        "/api/v1/agent/telemetry",
        json=[
            {
                "device_id": "telemetry-device-2",
                "cpu_usage": 21.0,
                "memory_usage": 56.0,
                "disk_usage": 45.0,
                "timestamp": now.isoformat(),
            },
            {
                "device_id": "telemetry-device-2",
                "cpu_usage": 22.0,
                "memory_usage": 57.0,
                "disk_usage": 46.0,
                "timestamp": (now + timedelta(seconds=30)).isoformat(),
            },
        ],
    )

    assert response.status_code == 200
    assert response.json()["data"]["saved_count"] == 2


def test_provision_returns_credentials_and_hashes_key(client: TestClient):
    """POST /api/v1/devices/provision should return credentials and persist hash."""
    _create_site("site-provision")
    response = client.post(
        "/api/v1/devices/provision",
        json={
            "sso_token": "sample-sso-token",
            "site_id": "site-provision",
            "user_identity": "setup.user@dealdio.com",
            "device_name": "Provisioned POS",
            "device_type": "physical_terminal",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["device_id"]
    assert payload["data"]["api_key"]

    created_device_id = payload["data"]["device_id"]
    db = homepot.database.SessionLocal()
    try:
        device = db.execute(
            select(Device).where(Device.device_id == created_device_id)
        ).scalars().first()
        assert device is not None
        assert device.api_key_hash is not None
    finally:
        db.close()


def test_status_returns_online_when_recent_heartbeat_exists(client: TestClient):
    """GET /api/v1/agent/{device_id}/status should return ONLINE for fresh heartbeat."""
    site = _create_site("site-status")
    _create_device("status-device-1", int(site.id))

    recent = datetime.now(timezone.utc).isoformat()
    hb_response = client.post(
        "/api/v1/agent/heartbeat",
        json={"device_id": "status-device-1", "timestamp": recent},
    )
    assert hb_response.status_code == 200

    status_response = client.get("/api/v1/agent/status-device-1/status")
    assert status_response.status_code == 200
    assert status_response.json()["data"]["status"] == "ONLINE"
