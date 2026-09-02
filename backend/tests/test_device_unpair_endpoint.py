"""Endpoint-level tests for the device self-unpair acknowledgement.

Verifies the enriched ``POST /device/{device_id}/unpair`` response the User App
relies on:
- ``lifecycle_state = unpaired`` and ``connectivity_state = offline`` are
  returned as the Dashboard's acknowledgement,
- ``disconnected_at`` is a server timestamp,
- a ``DeviceLifecycleEvent`` row is recorded (parity with suspend),
- the device's API key is cleared so it can no longer authenticate.
"""

import asyncio
import os
import tempfile
from typing import Any, Generator

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from homepot.app.auth_utils import hash_password
from homepot.config import reload_settings
import homepot.database
from homepot.models import (
    Base,
    Device,
    DeviceCredential,
    DeviceLifecycleEvent,
    LifecycleState,
)
from homepot.seed_factories import (
    create_device_credential_sync,
    create_device_sync,
    create_site_sync,
    create_tenant_sync,
)


@pytest.fixture(autouse=True)
def file_db(monkeypatch: Any) -> Generator[None, None, None]:
    """Use a temporary file-based SQLite DB so sync+async engines share data."""
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


@pytest.fixture
def seeded_client(client: TestClient) -> tuple[TestClient, str]:
    """Seed one viable device and return (client, device_id)."""
    db = homepot.database.SessionLocal()

    tenant = create_tenant_sync(db, name="Unpair Tenant", slug="unpair-tenant")
    site = create_site_sync(
        db, site_id="unpair-site-1", name="Unpair Site", tenant_id=tenant.id
    )
    device = create_device_sync(
        db,
        device_id="unpair-dev-1",
        name="Unpair Device",
        device_type="pos_terminal",
        site_id=site.id,
        is_active=True,
        lifecycle_state=LifecycleState.ACTIVE.value,
        api_key_hash=hash_password("device-key"),
    )
    create_device_credential_sync(
        db,
        credential_id="unpair-cred-1",
        device_id=device.id,
        key_hash=hash_password("device-key"),
        is_active=True,
    )
    device_id = device.device_id
    db.commit()
    db.close()
    return client, device_id


def _device_headers(device_id: str, api_key: str = "device-key") -> dict[str, str]:
    return {"X-Device-ID": device_id, "X-API-Key": api_key}


def test_unpair_returns_dashboard_ack(seeded_client: tuple[TestClient, str]) -> None:
    """Self-unpair returns an enriched acknowledgement of the final state."""
    client, device_id = seeded_client

    res = client.post(
        f"/api/v1/devices/device/{device_id}/unpair",
        headers=_device_headers(device_id),
        json={"reason": "User-initiated unpair", "idempotency_key": "unpair-ack-1"},
    )
    assert res.status_code == 200

    body = res.json()
    assert body["status"] == "success"
    assert body["device_id"] == device_id
    assert body["lifecycle_state"] == "unpaired"
    assert body["connectivity_state"] == "offline"
    assert body["disconnected_at"]

    # Server-side state must match the acknowledgement.
    db = homepot.database.SessionLocal()
    fetched = (
        db.execute(select(Device).where(Device.device_id == device_id))
        .scalars()
        .first()
    )
    assert fetched is not None
    assert fetched.lifecycle_state == LifecycleState.UNPAIRED.value
    assert fetched.is_active is False
    assert fetched.api_key_hash is None
    db.close()


def test_unpair_records_lifecycle_event(seeded_client: tuple[TestClient, str]) -> None:
    """Self-unpair writes a DeviceLifecycleEvent row (parity with suspend)."""
    client, device_id = seeded_client

    res = client.post(
        f"/api/v1/devices/device/{device_id}/unpair",
        headers=_device_headers(device_id),
        json={"reason": "User-initiated unpair", "idempotency_key": "unpair-ev-1"},
    )
    assert res.status_code == 200

    db = homepot.database.SessionLocal()
    device_row = (
        db.execute(select(Device).where(Device.device_id == device_id))
        .scalars()
        .first()
    )
    events = (
        db.execute(
            select(DeviceLifecycleEvent).where(
                DeviceLifecycleEvent.device_id == device_row.id
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].from_state == "active"
    assert events[0].to_state == "unpaired"
    assert events[0].idempotency_key == "unpair-ev-1"
    db.close()


def test_unpair_revokes_device_credentials(
    seeded_client: tuple[TestClient, str],
) -> None:
    """Self-unpair must revoke the device's active credentials.

    Regression test: persist_device() merges a detached Device whose
    "credentials" collection was eagerly loaded with is_active=True. If the
    merge runs after credential revocation (as it did before), the cascade
    re-activates the revoked credentials, leaving is_active=t / revoked_at
    NULL despite the unpair.
    """
    client, device_id = seeded_client

    res = client.post(
        f"/api/v1/devices/device/{device_id}/unpair",
        headers=_device_headers(device_id),
        json={"reason": "User-initiated unpair", "idempotency_key": "unpair-cred-1"},
    )
    assert res.status_code == 200

    db = homepot.database.SessionLocal()
    try:
        device_row = (
            db.execute(select(Device).where(Device.device_id == device_id))
            .scalars()
            .first()
        )
        creds = (
            db.execute(
                select(DeviceCredential).where(
                    DeviceCredential.device_id == device_row.id
                )
            )
            .scalars()
            .all()
        )
        assert creds, "expected at least one DeviceCredential row"
        for cred in creds:
            assert (
                cred.is_active is False
            ), f"credential {cred.credential_id} must be revoked after unpair"
            assert (
                cred.revoked_at is not None
            ), f"credential {cred.credential_id} must have a revoked_at"
    finally:
        db.close()


def test_unpaired_device_cannot_authenticate_again(
    seeded_client: tuple[TestClient, str],
) -> None:
    """Credential revocation prevents a device from authenticating after unpair."""
    client, device_id = seeded_client

    res = client.post(
        f"/api/v1/devices/device/{device_id}/unpair",
        headers=_device_headers(device_id),
        json={"reason": "User-initiated unpair", "idempotency_key": "unpair-auth-1"},
    )
    assert res.status_code == 200

    # After unpair the API key was cleared and the lifecycle is no longer
    # active, so the device can no longer authenticate (the one-shot self-unpair
    # must complete before any ack).
    retry = client.post(
        f"/api/v1/devices/device/{device_id}/unpair",
        headers=_device_headers(device_id),
        json={"reason": "retry", "idempotency_key": "unpair-auth-1"},
    )
    assert retry.status_code == 403
