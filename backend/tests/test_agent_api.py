"""Tests for the agent device DNA registration API."""

import asyncio
import os
import tempfile

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from homepot.app.auth_utils import hash_password
from homepot.config import reload_settings
import homepot.database
from homepot.models import Base, Device, Job, LifecycleState, Site


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


def _device_headers(device_id: str, api_key: str) -> dict[str, str]:
    return {"X-Device-ID": device_id, "X-API-Key": api_key}


def _create_device(
    device_id: str, site_pk: int, api_key: str = "test-api-key"
) -> str:
    """Create a device row linked to a site primary key."""
    db = homepot.database.SessionLocal()
    try:
        db.add(
            Device(
                device_id=device_id,
                name="Agent Device",
                device_type="pos_terminal",
                site_id=site_pk,
                api_key_hash=hash_password(api_key),
                is_active=True,
                lifecycle_state=LifecycleState.ACTIVE.value,
            )
        )
        db.commit()
    finally:
        db.close()
    return api_key


def _set_device_permissions(
    device_id: str, permissions: dict[str, bool]
) -> None:
    """Set the device_permissions JSON column for a device row."""
    db = homepot.database.SessionLocal()
    try:
        device = db.query(Device).filter(Device.device_id == device_id).first()
        assert device is not None
        device.device_permissions = permissions
        db.commit()
    finally:
        db.close()


def _grant_monitor(device_id: str) -> None:
    """Grant the Monitor (read-only diagnostics) tier to a device row."""
    _set_device_permissions(
        device_id,
        {
            "command_execution": True,
            "process_monitoring": True,
            "filesystem_access": True,
            "network_monitoring": True,
        },
    )


def _create_job_for_device(
    device_id: str, job_id: str, action: str, status: str = "completed"
) -> None:
    """Insert a Job row linked to a device."""
    db = homepot.database.SessionLocal()
    try:
        device = db.query(Device).filter(Device.device_id == device_id).first()
        assert device is not None
        db.add(
            Job(
                job_id=job_id,
                action=action,
                status=status,
                priority="low",
                site_id=int(device.site_id),
                device_id=int(device.id),
                created_by=1,
            )
        )
        db.commit()
    finally:
        db.close()


def test_device_dna_requires_device_credentials(client: TestClient):
    """Device DNA updates require credentials issued during provisioning."""
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

    assert response.status_code == 401


def test_device_dna_updates_provisioned_device(client: TestClient):
    """Device DNA endpoint should update a device created during provisioning."""
    site = _seed_site("site-agent-1")
    api_key = "test-api-key"
    db = homepot.database.SessionLocal()
    try:
        db.add(
            Device(
                device_id="agent-device-1",
                name="Front POS",
                device_type="pos_terminal",
                site_id=int(site.id),
                api_key_hash=hash_password(api_key),
                is_active=True,
                lifecycle_state=LifecycleState.ACTIVE.value,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/v1/agent/device-dna",
        json={
            "device_id": "agent-device-1",
            "site_id": "site-agent-1",
            "device_name": "Front POS",
            "device_type": "pos_terminal",
            "mac_address": "00:11:22:33:44:55",
            "os_details": "Windows 11",
            "local_ip": "192.168.1.20",
            "wan_ip": "203.0.113.10",
        },
        headers=_device_headers("agent-device-1", api_key),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["device_id"] == "agent-device-1"
    assert payload["data"]["created"] is False


def test_device_dna_updates_existing_device(client: TestClient):
    """Device DNA endpoint should update DNA fields for existing device records."""
    site = _seed_site("site-agent-2")

    db = homepot.database.SessionLocal()
    try:
        device = Device(
            device_id="agent-device-2",
            name="Agent Device",
            device_type="pos_terminal",
            site_id=int(site.id),
            api_key_hash=hash_password("test-api-key"),
            is_active=True,
            lifecycle_state=LifecycleState.ACTIVE.value,
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
        headers=_device_headers("agent-device-2", "test-api-key"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["device_id"] == "agent-device-2"
    assert payload["data"]["created"] is False


def test_job_history_returns_device_jobs(client: TestClient):
    """GET /api/v1/agent/{device_id}/jobs returns the device's job history."""
    site = _seed_site("site-jobs-1")
    api_key = _create_device("jobs-device-1", int(site.id))
    _grant_monitor("jobs-device-1")
    _create_job_for_device(
        "jobs-device-1", "job-1", action="Log Rotation", status="completed"
    )
    _create_job_for_device(
        "jobs-device-1", "job-2", action="Security Scan", status="failed"
    )

    response = client.get(
        "/api/v1/agent/jobs-device-1/jobs?limit=10",
        headers=_device_headers("jobs-device-1", api_key),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    jobs = payload["data"]
    assert [j["action"] for j in jobs] == ["Security Scan", "Log Rotation"]
    assert jobs[0]["status"] == "failed"
    assert jobs[0]["priority"] == "low"
    assert jobs[0]["job_id"] == "job-2"
    assert jobs[1]["status"] == "completed"
    assert jobs[1]["job_id"] == "job-1"


def test_job_history_requires_monitor_permission(client: TestClient):
    """Job history reads are gated behind the Monitor permission tier."""
    site = _seed_site("site-jobs-2")
    api_key = _create_device("jobs-device-2", int(site.id))

    response = client.get(
        "/api/v1/agent/jobs-device-2/jobs",
        headers=_device_headers("jobs-device-2", api_key),
    )

    assert response.status_code == 403


def test_job_history_rejects_other_devices(client: TestClient):
    """A device can only read its own job history."""
    site = _seed_site("site-jobs-3")
    _create_device("jobs-device-3", int(site.id))
    api_key = _create_device("jobs-device-4", int(site.id))
    _grant_monitor("jobs-device-4")

    response = client.get(
        "/api/v1/agent/jobs-device-3/jobs",
        headers=_device_headers("jobs-device-4", api_key),
    )

    assert response.status_code == 403
