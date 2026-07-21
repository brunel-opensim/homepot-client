"""Tests for device command management."""

import asyncio
from datetime import datetime, timedelta, timezone
import os
import secrets
import tempfile
from typing import Any, Dict

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from homepot.app.auth_utils import create_access_token, hash_password
from homepot.config import reload_settings
import homepot.database
from homepot.models import (
    Base,
    CommandStatus,
    Device,
    DeviceCommand,
    LifecycleState,
    Site,
    User,
)


@pytest.fixture(autouse=True)
def mock_db_url(monkeypatch):
    """Use a temporary database for these tests to avoid file locking issues."""
    # Create a temp file
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Set env var
    db_url = f"sqlite:///{path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DATABASE__URL", db_url)

    # Reload settings to pick up new env var
    reload_settings()

    # Reset the database service singleton so it picks up the new settings
    if homepot.database._db_service is not None:
        try:
            # Properly close the previous async engine to clean up threads/loops
            asyncio.run(homepot.database._db_service.close())
        except Exception:
            # If loop is already closed or other error, just proceed
            pass
        homepot.database._db_service = None

    # Create new sync engine for the temp DB (for create_all)
    new_engine = create_engine(
        db_url, connect_args={"check_same_thread": False}, pool_pre_ping=True
    )

    # Create tables
    Base.metadata.create_all(bind=new_engine)

    # Create new sessionmaker
    NewSessionLocal = sessionmaker(bind=new_engine, autocommit=False, autoflush=False)

    # Patch the database module globals
    monkeypatch.setattr(homepot.database, "sync_engine", new_engine)
    monkeypatch.setattr(homepot.database, "SessionLocal", NewSessionLocal)

    yield

    # Cleanup
    new_engine.dispose()
    if os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


# Use the client fixture from conftest.py
def test_device_command_flow(client: TestClient):
    """Test the full flow of device management.

    1. Create Site (as admin)
    2. Create Device (in DB, get API Key)
    3. Queue Command (as admin)
    4. Retrieve Pending Commands (as Device)
    """
    # Create admin user for auth
    db = homepot.database.SessionLocal()
    try:
        admin = User(
            email="admin@cmd.test",
            username="admin_cmd",
            hashed_password=hash_password("pass"),
            is_admin=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
    finally:
        db.close()

    token = create_access_token({"sub": "admin@cmd.test"})
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 1. Create Site
    site_id = "test-site-cmd-flow"
    site_data = {
        "site_id": site_id,
        "name": "Command Flow Test Site",
        "location": "Test Lab",
    }
    response = client.post("/api/v1/sites/", json=site_data, headers=auth_headers)
    if response.status_code != 409:
        assert response.status_code == 200

    # 2. Create Device directly in DB
    device_id = "test-device-cmd-flow"
    api_key = secrets.token_urlsafe(32)
    api_key_hash = hash_password(api_key)

    db = homepot.database.SessionLocal()
    try:
        site = db.query(Site).filter(Site.site_id == site_id).first()
        assert site is not None, "Site must exist"
        device = Device(
            device_id=device_id,
            name="Command Flow Device",
            device_type="pos_terminal",
            site_id=site.id,
            api_key_hash=api_key_hash,
            is_active=True,
            lifecycle_state=LifecycleState.ACTIVE.value,
        )
        db.add(device)
        db.commit()
    finally:
        db.close()

    # 3. Queue Command (as authenticated admin)
    command_payload = {
        "command_type": "REBOOT",
        "payload": {"reason": "integration_test"},
    }
    response = client.post(
        f"/api/v1/devices/{device_id}/commands",
        json=command_payload,
        headers=auth_headers,
    )
    assert response.status_code == 201
    cmd_data = response.json()
    command_id = cmd_data["command_id"]
    assert cmd_data["status"] == "pending"

    # 4. Get Pending Commands (As Device)
    device_headers = {"X-Device-ID": device_id, "X-API-Key": api_key}
    response = client.get("/api/v1/devices/pending", headers=device_headers)
    assert response.status_code == 200
    pending_cmds = response.json()

    # Verify our command is in the list
    found = False
    for cmd in pending_cmds:
        if cmd["command_id"] == command_id:
            found = True
            assert cmd["command_type"] == "REBOOT"
            break
    assert found, "Queued command not found in pending list"


def test_device_auth_failure(client: TestClient):
    """Test that invalid credentials are rejected."""
    headers = {"X-Device-ID": "non-existent-device", "X-API-Key": "invalid-key"}
    response = client.get("/api/v1/devices/pending", headers=headers)
    assert response.status_code == 401


# -- Helpers for command history tests --

TEST_ADMIN_EMAIL = "admin.history@test.local"


def _setup_site_and_device(client: TestClient) -> Dict[str, Any]:
    """Create a site and device, returning IDs and auth headers."""
    db = homepot.database.SessionLocal()
    try:
        existing = db.query(User).filter(User.email == TEST_ADMIN_EMAIL).first()
        if not existing:
            admin = User(
                email=TEST_ADMIN_EMAIL,
                username="admin_history",
                hashed_password=hash_password("pass"),
                is_admin=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()

    token = create_access_token({"sub": TEST_ADMIN_EMAIL})
    auth_headers = {"Authorization": f"Bearer {token}"}

    site_id = "test-site-history"
    resp = client.post(
        "/api/v1/sites",
        json={
            "site_id": site_id,
            "name": "History Test Site",
        },
        headers=auth_headers,
    )
    if resp.status_code not in (200, 409):
        assert False, f"Failed to create site: {resp.text}"

    device_id = "test-device-history"
    api_key = secrets.token_urlsafe(32)
    api_key_hash = hash_password(api_key)

    db = homepot.database.SessionLocal()
    try:
        site = db.query(Site).filter(Site.site_id == site_id).first()
        assert site is not None
        existing_dev = db.query(Device).filter(Device.device_id == device_id).first()
        if not existing_dev:
            device = Device(
                device_id=device_id,
                name="History Device",
                device_type="pos_terminal",
                site_id=site.id,
                api_key_hash=api_key_hash,
                is_active=True,
                lifecycle_state=LifecycleState.ACTIVE.value,
            )
            db.add(device)
            db.commit()
            db.refresh(device)
    finally:
        db.close()

    return {
        "site_id": site_id,
        "device_id": device_id,
        "auth_headers": auth_headers,
    }


def _queue_command(
    client: TestClient,
    device_id: str,
    headers: Dict[str, str],
    command_type: str = "REBOOT",
) -> str:
    """Queue a command and return its command_id."""
    resp = client.post(
        f"/api/v1/devices/{device_id}/commands",
        json={"command_type": command_type, "payload": {"test": True}},
        headers=headers,
    )
    assert resp.status_code == 201, f"Failed to queue command: {resp.text}"
    return resp.json()["command_id"]


def test_command_history_endpoint(client: TestClient) -> None:
    """GET /devices/device/{device_id}/commands returns command history."""
    ctx = _setup_site_and_device(client)
    h = ctx["auth_headers"]
    device_id = ctx["device_id"]

    cmd1 = _queue_command(client, device_id, h, "REBOOT")
    cmd2 = _queue_command(client, device_id, h, "UPDATE_CONFIG")

    resp = client.get(f"/api/v1/devices/device/{device_id}/commands", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2

    # Most recent command first (desc by created_at)
    assert data[0]["command_type"] == "UPDATE_CONFIG"
    assert data[1]["command_type"] == "REBOOT"
    assert data[0]["command_id"] == cmd2
    assert data[1]["command_id"] == cmd1

    # Verify all expected fields
    cmd = data[0]
    assert "command_id" in cmd
    assert "command_type" in cmd
    assert "status" in cmd
    assert cmd["status"] == "pending"
    assert "payload" in cmd
    assert "created_at" in cmd
    assert "executed_at" in cmd  # None for pending


def test_command_history_unauthorized(client: TestClient) -> None:
    """Command history endpoint returns 401 without auth."""
    resp = client.get("/api/v1/devices/device/unknown/commands")
    assert resp.status_code == 401


def test_expire_stale_commands(client: TestClient) -> None:
    """expire_stale_commands marks old PENDING commands as EXPIRED."""
    ctx = _setup_site_and_device(client)
    h = ctx["auth_headers"]
    device_id = ctx["device_id"]

    cmd_id = _queue_command(client, device_id, h, "PING")

    # Directly manipulate the command's created_at to be in the past
    db = homepot.database.SessionLocal()
    try:
        cmd = db.query(DeviceCommand).filter(DeviceCommand.command_id == cmd_id).first()
        assert cmd is not None
        cmd.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()
    finally:
        db.close()

    # Run expiry with a short TTL
    async def _expire():
        svc = await homepot.database.get_database_service()
        return await svc.expire_stale_commands(ttl_seconds=60)

    expired_count = asyncio.run(_expire())
    assert expired_count >= 1

    # Verify the command is now expired
    db = homepot.database.SessionLocal()
    try:
        cmd = db.query(DeviceCommand).filter(DeviceCommand.command_id == cmd_id).first()
        assert cmd is not None
        assert cmd.status == CommandStatus.EXPIRED
    finally:
        db.close()
