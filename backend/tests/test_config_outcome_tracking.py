"""Tests for configuration outcome and rollback tracking.

Covers the agent-reported push-history endpoint persisting before/after
performance, success, rollback outcome, and evidence provenance, so MW-03 to
MW-05 evidence is reproducible.
"""

import asyncio
from datetime import datetime, timezone
import os
import secrets
import tempfile

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from homepot.app.auth_utils import hash_password
from homepot.app.models.AnalyticsModel import ConfigurationHistory
from homepot.config import reload_settings
import homepot.database
from homepot.models import Base, Device, LifecycleState, Site, User

CONFIG_HISTORY_URL = "/api/v1/agent/config-history"


@pytest.fixture(autouse=True)
def mock_db_url(monkeypatch):
    """Use a temporary database for these tests to avoid file locking issues."""
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
    NewSessionLocal = sessionmaker(bind=new_engine, autocommit=False, autoflush=False)

    monkeypatch.setattr(homepot.database, "sync_engine", new_engine)
    monkeypatch.setattr(homepot.database, "SessionLocal", NewSessionLocal)

    yield

    new_engine.dispose()
    if os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


def _create_device(device_id: str, config: dict) -> str:
    """Create an admin, site, and device; return the device API key."""
    db = homepot.database.SessionLocal()
    try:
        admin = User(
            email=f"admin-{device_id}@test.local",
            username=f"admin_{device_id}",
            hashed_password=hash_password("pass"),
            is_admin=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(admin)
        db.commit()

        site = Site(site_id=f"site-{device_id}", name=f"Site {device_id}")
        db.add(site)
        db.commit()

        api_key = secrets.token_urlsafe(32)
        device = Device(
            device_id=device_id,
            name=f"Device {device_id}",
            device_type="pos_terminal",
            site_id=site.id,
            api_key_hash=hash_password(api_key),
            is_active=True,
            lifecycle_state=LifecycleState.ACTIVE.value,
            config=config,
        )
        db.add(device)
        db.commit()
        return api_key
    finally:
        db.close()


def _device_headers(device_id: str, api_key: str) -> dict:
    return {"X-Device-ID": device_id, "X-API-Key": api_key}


def _latest_history(session) -> ConfigurationHistory:
    result = session.execute(
        select(ConfigurationHistory).order_by(ConfigurationHistory.id.desc()).limit(1)
    )
    return result.scalar_one()


def test_config_history_persists_outcome_and_rollback(client: TestClient) -> None:
    """A full report stores before/after performance, success and rollback."""
    api_key = _create_device("real-pos-outcome", {"device_source": "physical"})
    headers = _device_headers("real-pos-outcome", api_key)

    rolled_back_at = datetime.now(timezone.utc)
    resp = client.post(
        CONFIG_HISTORY_URL,
        json={
            "device_id": "real-pos-outcome",
            "action": "update_pos_payment_config",
            "parameter_name": "push_command:APPLY_CONFIG",
            "old_value": {"version": "2.0.0"},
            "new_value": {"version": "2.1.0"},
            "success": False,
            "performance_before": {"status": "healthy", "response_time_ms": 48},
            "performance_after": {"status": "degraded", "response_time_ms": 210},
            "was_rolled_back": True,
            "rollback_reason": "Performance regression after change",
            "rollback_success": True,
            "rollback_performance": {"status": "healthy", "response_time_ms": 47},
            "rolled_back_at": rolled_back_at.isoformat(),
            "change_reason": "Push command APPLY_CONFIG executed",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    db = homepot.database.SessionLocal()
    try:
        entry = _latest_history(db)
        assert entry.entity_id == "real-pos-outcome"
        assert entry.parameter_name == "push_command:APPLY_CONFIG"
        assert entry.was_successful is False
        assert entry.performance_before == {
            "status": "healthy",
            "response_time_ms": 48,
        }
        assert entry.performance_after == {
            "status": "degraded",
            "response_time_ms": 210,
        }
        assert entry.was_rolled_back is True
        assert entry.rollback_reason == "Performance regression after change"
        assert entry.rollback_success is True
        assert entry.rollback_performance == {
            "status": "healthy",
            "response_time_ms": 47,
        }
        assert entry.rolled_back_at is not None
        assert entry.provenance == "real"
    finally:
        db.close()


def test_config_history_derives_simulated_provenance(client: TestClient) -> None:
    """Simulated devices are labelled simulated in the persisted row."""
    api_key = _create_device("sim-pos-outcome", {"device_source": "simulation"})
    headers = _device_headers("sim-pos-outcome", api_key)

    resp = client.post(
        CONFIG_HISTORY_URL,
        json={
            "device_id": "sim-pos-outcome",
            "action": "update_pos_payment_config",
            "parameter_name": "push_command:APPLY_CONFIG",
            "new_value": {"version": "9.9.9"},
            "success": True,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    db = homepot.database.SessionLocal()
    try:
        entry = _latest_history(db)
        assert entry.entity_id == "sim-pos-outcome"
        assert entry.provenance == "simulated"
        assert entry.was_successful is True
        assert entry.was_rolled_back is False
    finally:
        db.close()


def test_config_history_rejects_mismatched_device(client: TestClient) -> None:
    """A device cannot report history for a different device_id."""
    api_key = _create_device("real-pos-match", {"device_source": "physical"})
    headers = _device_headers("real-pos-match", api_key)

    resp = client.post(
        CONFIG_HISTORY_URL,
        json={
            "device_id": "some-other-device",
            "action": "update_pos_payment_config",
            "parameter_name": "push_command:APPLY_CONFIG",
            "new_value": {"version": "1.0.0"},
            "success": True,
        },
        headers=headers,
    )
    assert resp.status_code == 403
