"""Tests for device command management."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import homepot.database
from homepot.config import reload_settings
from homepot.models import Base


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
        # We can't await close() here easily in a sync fixture, but we can just clear the reference
        # The file cleanup will handle the old DB file
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

    1. Create Site
    2. Create Device (get API Key)
    3. Queue Command
    4. Retrieve Pending Commands (as Device)
    """
    # 1. Create Site
    site_id = "test-site-cmd-flow"
    site_data = {
        "site_id": site_id,
        "name": "Command Flow Test Site",
        "location": "Test Lab",
    }
    response = client.post("/api/v1/sites/", json=site_data)
    # Handle case where site might already exist from previous runs (though DB should be fresh in tests)
    if response.status_code != 409:
        assert response.status_code == 200

    # 2. Create Device
    device_id = "test-device-cmd-flow"
    device_data = {
        "device_id": device_id,
        "name": "Command Flow Device",
        "device_type": "pos_terminal",
    }
    response = client.post(f"/api/v1/devices/sites/{site_id}/devices", json=device_data)
    assert response.status_code == 200
    data = response.json()
    assert "api_key" in data
    api_key = data["api_key"]

    # 3. Queue Command
    command_payload = {
        "command_type": "REBOOT",
        "payload": {"reason": "integration_test"},
    }
    response = client.post(
        f"/api/v1/devices/{device_id}/commands", json=command_payload
    )
    assert response.status_code == 201
    cmd_data = response.json()
    command_id = cmd_data["command_id"]
    assert cmd_data["status"] == "pending"

    # 4. Get Pending Commands (As Device)
    headers = {"X-Device-ID": device_id, "X-API-Key": api_key}
    response = client.get("/api/v1/devices/pending", headers=headers)
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
