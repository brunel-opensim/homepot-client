"""Tests for site/device archive and purge.

Archive (default) hides the entity and retains data; purge (with confirm=true)
permanently deletes the entity and all associated data. Applies regardless of
whether devices are simulated, emulated, or real.
"""

import asyncio
from datetime import datetime, timezone
import os
import tempfile
from typing import Any, Generator

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from homepot.app.auth_utils import create_access_token, hash_password
from homepot.app.main import app
from homepot.config import reload_settings
import homepot.database
from homepot.models import AuditLog, Base, Device, DeviceStatus, Site, User


@pytest.fixture
def file_db(monkeypatch: Any) -> Generator[None, None, None]:
    """Use a temp file-based SQLite DB so sync+async engines share data."""
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


def _seed_site_device_admin() -> tuple[str, str, int]:
    """Create a site + device + admin; return (site_id, device_id, site_pk)."""
    sync_db = homepot.database.SessionLocal()
    try:
        site = Site(site_id="test-arch-purge", name="Test Co", is_active=True)
        sync_db.add(site)
        sync_db.commit()
        sync_db.refresh(site)

        device = Device(
            device_id="dev-ap-001",
            name="Test POS",
            device_type="pos_terminal",
            site_id=site.id,
            is_active=True,
            status=DeviceStatus.ONLINE,
        )
        sync_db.add(device)
        sync_db.commit()

        admin = User(
            email="admin@arch-purge.test",
            username="admin_ap",
            hashed_password=hash_password("pass"),
            is_admin=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        sync_db.add(admin)
        sync_db.commit()
        return site.site_id, device.device_id, site.id
    finally:
        sync_db.close()


def _headers() -> dict:
    token = create_access_token({"sub": "admin@arch-purge.test"})
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------
# Site
# --------------------------------------------------------------------------


def test_site_archive_default_retains_data(file_db: Any) -> None:
    """Default delete archives the site + devices (data retained, hidden)."""
    site_id, device_id, _ = _seed_site_device_admin()
    client = TestClient(app)
    response = client.delete(f"/api/v1/sites/{site_id}", headers=_headers())
    assert response.status_code == 200
    assert "archived" in response.json()["message"].lower()

    sync_db = homepot.database.SessionLocal()
    try:
        site = sync_db.query(Site).filter(Site.site_id == site_id).first()
        device = sync_db.query(Device).filter(Device.device_id == device_id).first()
        assert site is not None and site.is_active is False
        assert site.lifecycle_state == "archived"
        assert device is not None and device.is_active is False
    finally:
        sync_db.close()


def test_site_purge_requires_confirm(file_db: Any) -> None:
    """Purge without confirm=true is rejected."""
    site_id, _, _ = _seed_site_device_admin()
    client = TestClient(app)
    response = client.delete(
        f"/api/v1/sites/{site_id}", params={"mode": "purge"}, headers=_headers()
    )
    assert response.status_code == 400
    assert "confirm" in response.json()["detail"].lower()


def test_site_restore_reactivates_site_and_devices(file_db: Any) -> None:
    """Restore flips an archived site back to active and re-activates devices."""
    site_id, device_id, _ = _seed_site_device_admin()
    client = TestClient(app)

    response = client.delete(f"/api/v1/sites/{site_id}", headers=_headers())
    assert response.status_code == 200

    response = client.post(f"/api/v1/sites/{site_id}/restore", headers=_headers())
    assert response.status_code == 200
    assert "restored" in response.json()["message"].lower()

    sync_db = homepot.database.SessionLocal()
    try:
        site = sync_db.query(Site).filter(Site.site_id == site_id).first()
        device = sync_db.query(Device).filter(Device.device_id == device_id).first()
        assert site is not None and site.is_active is True
        assert site.lifecycle_state == "active"
        assert device is not None and device.is_active is True
    finally:
        sync_db.close()


def test_site_restore_active_site_is_idempotent(file_db: Any) -> None:
    """Restoring an already-active site is a no-op success."""
    site_id, _, _ = _seed_site_device_admin()
    client = TestClient(app)
    response = client.post(f"/api/v1/sites/{site_id}/restore", headers=_headers())
    assert response.status_code == 200
    assert "already active" in response.json()["message"].lower()


def test_site_purge_with_confirm_deletes_everything(file_db: Any) -> None:
    """Purge with confirm=true deletes the site and its devices."""
    site_id, device_id, _ = _seed_site_device_admin()
    client = TestClient(app)
    response = client.delete(
        f"/api/v1/sites/{site_id}",
        params={"mode": "purge", "confirm": "true"},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert "purged" in response.json()["message"].lower()

    sync_db = homepot.database.SessionLocal()
    try:
        site = sync_db.query(Site).filter(Site.site_id == site_id).first()
        device = sync_db.query(Device).filter(Device.device_id == device_id).first()
        assert site is None
        assert device is None
    finally:
        sync_db.close()


# --------------------------------------------------------------------------
# Device
# --------------------------------------------------------------------------


def test_device_archive_default_retains_data(file_db: Any) -> None:
    """Default delete archives the device (unpaired, data retained)."""
    _, device_id, _ = _seed_site_device_admin()
    client = TestClient(app)
    response = client.delete(f"/api/v1/devices/device/{device_id}", headers=_headers())
    assert response.status_code == 200
    assert "archived" in response.json()["message"].lower()

    sync_db = homepot.database.SessionLocal()
    try:
        device = sync_db.query(Device).filter(Device.device_id == device_id).first()
        assert device is not None and device.is_active is False
        # archived device is no longer reachable, so connectivity status is offline
        assert device.status == "offline"
        assert device.lifecycle_state == "unpaired"
    finally:
        sync_db.close()


def test_device_purge_requires_confirm(file_db: Any) -> None:
    """Device purge without confirm=true is rejected."""
    _, device_id, _ = _seed_site_device_admin()
    client = TestClient(app)
    response = client.delete(
        f"/api/v1/devices/device/{device_id}",
        params={"mode": "purge"},
        headers=_headers(),
    )
    assert response.status_code == 400
    assert "confirm" in response.json()["detail"].lower()


def test_device_purge_with_confirm_deletes(file_db: Any) -> None:
    """Device purge with confirm=true deletes the device row."""
    _, device_id, _ = _seed_site_device_admin()
    client = TestClient(app)
    response = client.delete(
        f"/api/v1/devices/device/{device_id}",
        params={"mode": "purge", "confirm": "true"},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert "purged" in response.json()["message"].lower()

    sync_db = homepot.database.SessionLocal()
    try:
        device = sync_db.query(Device).filter(Device.device_id == device_id).first()
        assert device is None
    finally:
        sync_db.close()


def test_device_purge_creates_audit_tombstone(file_db: Any) -> None:
    """Purging a device leaves a 'device_deleted' audit tombstone."""
    _, device_id, site_pk = _seed_site_device_admin()
    client = TestClient(app)
    response = client.delete(
        f"/api/v1/devices/device/{device_id}",
        params={"mode": "purge", "confirm": "true"},
        headers=_headers(),
    )
    assert response.status_code == 200

    sync_db = homepot.database.SessionLocal()
    try:
        tombstone = (
            sync_db.query(AuditLog)
            .filter(
                AuditLog.event_type == "device_deleted",
                AuditLog.description.like(f"%{device_id}%"),
            )
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert tombstone is not None
        # device_id FK is null (device row is gone); identity preserved in data
        assert tombstone.device_id is None
        assert tombstone.old_values.get("device_id") == device_id
        assert tombstone.old_values.get("cleanup_policy") == "purge"
    finally:
        sync_db.close()


def _seed_emulated_device_admin() -> tuple[str, str]:
    """Create a site + an EMULATED device (device_source=emulator) + admin."""
    sync_db = homepot.database.SessionLocal()
    try:
        site = Site(site_id="test-emu-arch", name="Test Emu", is_active=True)
        sync_db.add(site)
        sync_db.commit()
        sync_db.refresh(site)

        device = Device(
            device_id="dev-emu-001",
            name="Emulated POS",
            device_type="pos_terminal",
            site_id=site.id,
            is_active=True,
            is_simulated=True,
            status=DeviceStatus.ONLINE,
            config={"device_source": "emulator"},
        )
        sync_db.add(device)
        sync_db.commit()

        admin = User(
            email="admin@emu-arch.test",
            username="admin_emu",
            hashed_password=hash_password("pass"),
            is_admin=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        sync_db.add(admin)
        sync_db.commit()
        return site.site_id, device.device_id
    finally:
        sync_db.close()


def test_emulated_device_archive_and_purge(file_db: Any) -> None:
    """Archive/purge apply to emulated devices too (device-agnostic)."""
    site_id, device_id = _seed_emulated_device_admin()
    client = TestClient(app)
    token = create_access_token({"sub": "admin@emu-arch.test"})
    headers = {"Authorization": f"Bearer {token}"}

    # Archive (default)
    response = client.delete(f"/api/v1/devices/device/{device_id}", headers=headers)
    assert response.status_code == 200
    assert "archived" in response.json()["message"].lower()

    sync_db = homepot.database.SessionLocal()
    try:
        device = sync_db.query(Device).filter(Device.device_id == device_id).first()
        assert device is not None and device.is_active is False
        assert device.status == "offline"
    finally:
        sync_db.close()

    # Purge (with confirm)
    response = client.delete(
        f"/api/v1/devices/device/{device_id}",
        params={"mode": "purge", "confirm": "true"},
        headers=headers,
    )
    assert response.status_code == 200
    assert "purged" in response.json()["message"].lower()

    sync_db = homepot.database.SessionLocal()
    try:
        device = sync_db.query(Device).filter(Device.device_id == device_id).first()
        assert device is None
    finally:
        sync_db.close()
