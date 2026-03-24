"""Tests for the agent registration API."""

import asyncio
import os
import secrets
import tempfile

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from homepot.app.auth_utils import hash_password
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


def _seed_device(
    api_key: str, *, site_code: str = "site-agent-1", active: bool = True
):
    """Seed a site and device record for registration tests."""
    db = homepot.database.SessionLocal()
    try:
        site = Site(site_id=site_code, name="Agent Test Site", location="Lab")
        db.add(site)
        db.commit()
        db.refresh(site)

        device = Device(
            device_id="agent-device-1",
            name="Agent Device",
            device_type="gateway",
            site_id=site.id,
            api_key_hash=hash_password(api_key),
            is_active=active,
        )
        db.add(device)
        db.commit()
    finally:
        db.close()


def test_register_requires_valid_api_key(client: TestClient):
    """Registration should reject devices with invalid credentials."""
    valid_key = secrets.token_urlsafe(32)
    _seed_device(valid_key)

    response = client.post(
        "/api/v1/agent/register",
        json={
            "device_id": "agent-device-1",
            "site_id": "site-agent-1",
            "backend_url": "https://backend.example.test",
            "api_key": "wrong-key",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API Key"


def test_register_rejects_site_mismatch(client: TestClient):
    """Registration should reject devices presented for the wrong site."""
    valid_key = secrets.token_urlsafe(32)
    _seed_device(valid_key)

    response = client.post(
        "/api/v1/agent/register",
        json={
            "device_id": "agent-device-1",
            "site_id": "other-site",
            "backend_url": "https://backend.example.test",
            "api_key": valid_key,
        },
    )

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Device is not authorized for the requested site"
    )


def test_register_returns_dna_for_authorized_device(client: TestClient, monkeypatch):
    """Registration should succeed for pre-authorized devices."""
    valid_key = secrets.token_urlsafe(32)
    _seed_device(valid_key)
    expected_dna = {
        "local_ip": "192.168.1.10",
        "wan_ip": "203.0.113.5",
        "mac_address": "00:11:22:33:44:55",
        "os_name": "TestOS",
        "os_version": "1.0",
    }
    monkeypatch.setattr(
        "homepot.agent.agent_api.collect_device_dna", lambda payload: expected_dna
    )

    response = client.post(
        "/api/v1/agent/register",
        json={
            "device_id": "agent-device-1",
            "site_id": "site-agent-1",
            "backend_url": "https://backend.example.test",
            "api_key": valid_key,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "device_id": "agent-device-1",
        "site_id": "site-agent-1",
        "dna_received": expected_dna,
    }
