"""Tests for device command management."""

import asyncio
from datetime import datetime, timezone
import os
import secrets
import tempfile

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from homepot.app.auth_utils import create_access_token, hash_password
from homepot.config import reload_settings
import homepot.database
from homepot.models import Base, Device, LifecycleState, Site, User


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
