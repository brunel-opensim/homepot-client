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
from homepot.models import (
    AuditLog,
    Base,
    Device,
    DeviceStatus,
    LifecycleEpoch,
    Site,
    User,
)


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

    from sqlalchemy import event

    @event.listens_for(new_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=new_engine)
    new_session_local = sessionmaker(bind=new_engine, autocommit=False, autoflush=False)

    monkeypatch.setattr(homepot.database, "sync_engine", new_engine)
    monkeypatch.setattr(homepot.database, "SessionLocal", new_session_local)

    # The async engine used by the API is created lazily; construct it now,
    # attach FK enforcement before any connection is opened, then initialize so
    # the tests exercise the same FK constraints as PostgreSQL.
    import homepot.database as db_mod

    async def _init_async() -> None:
        service = db_mod.DatabaseService()
        from sqlalchemy import event as sa_event

        @sa_event.listens_for(service.engine.sync_engine, "connect")
        def _async_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        await service.initialize()
        db_mod._db_service = service

    asyncio.run(_init_async())

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
        sync_db.refresh(device)

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


def _seed_device_with_epoch(device_id: str = "dev-epoch-001") -> None:
    """Create a site, device, and a linked lifecycle epoch (as after claiming)."""
    import uuid

    sync_db = homepot.database.SessionLocal()
    try:
        site = Site(site_id="site-epoch", name="Epoch Co", is_active=True)
        sync_db.add(site)
        sync_db.commit()
        sync_db.refresh(site)

        device = Device(
            device_id=device_id,
            name="Epoch POS",
            device_type="pos_terminal",
            site_id=site.id,
            is_active=True,
            status=DeviceStatus.ONLINE,
        )
        sync_db.add(device)
        sync_db.commit()
        sync_db.refresh(device)

        epoch = LifecycleEpoch(
            epoch_id=str(uuid.uuid4()),
            device_id=device.id,
            site_id=site.id,
            claimed_at=datetime.now(timezone.utc),
            enrolment_method="pre-provisioned",
        )
        sync_db.add(epoch)
        sync_db.commit()
        sync_db.refresh(epoch)

        admin = User(
            email="admin@arch-purge.test",
            username="admin_ap",
            hashed_password=hash_password("pass"),
            is_admin=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        if not sync_db.query(User).filter(User.email == admin.email).first():
            sync_db.add(admin)

        device.lifecycle_epoch_id = epoch.id  # type: ignore[assignment]
        sync_db.commit()
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
        assert device.lifecycle_state == "suspended"
        assert device.status == "offline"
    finally:
        sync_db.close()


def test_site_list_excludes_archived_by_default(file_db: Any) -> None:
    """GET /sites/ hides archived sites unless include_archived=true."""
    site_id, device_id, _ = _seed_site_device_admin()
    client = TestClient(app)

    archived = client.delete(f"/api/v1/sites/{site_id}", headers=_headers())
    assert archived.status_code == 200

    default_list = client.get("/api/v1/sites/", headers=_headers())
    assert default_list.status_code == 200
    default_ids = [s["site_id"] for s in default_list.json()["sites"]]
    assert site_id not in default_ids

    archived_list = client.get(
        "/api/v1/sites/", params={"include_archived": "true"}, headers=_headers()
    )
    assert archived_list.status_code == 200
    archived_ids = [s["site_id"] for s in archived_list.json()["sites"]]
    assert site_id in archived_ids
    archived_site = next(
        s for s in archived_list.json()["sites"] if s["site_id"] == site_id
    )
    assert archived_site["is_active"] is False
    assert archived_site["lifecycle_state"] == "archived"
    assert archived_site["devices_count"] == 1


def test_archived_site_status_is_offline_even_if_device_status_online(
    file_db: Any,
) -> None:
    """An archived site shows Offline even if a suspended device's raw status column still says online.

    The raw status field can be stale (from the simulation agent). Site status
    must only consider active devices; suspended devices must not make an
    archived site appear online.
    """
    site_id, device_id, _ = _seed_site_device_admin()
    client = TestClient(app)

    archived = client.delete(f"/api/v1/sites/{site_id}", headers=_headers())
    assert archived.status_code == 200

    # Simulate a stale raw status field on the suspended device (the simulation
    # agent used to flip this back to 'online').
    sync_db = homepot.database.SessionLocal()
    try:
        device = sync_db.query(Device).filter(Device.device_id == device_id).first()
        assert device is not None
        device.status = DeviceStatus.ONLINE.value
        sync_db.commit()
    finally:
        sync_db.close()

    archived_list = client.get(
        "/api/v1/sites/", params={"include_archived": "true"}, headers=_headers()
    )
    assert archived_list.status_code == 200
    archived_site = next(
        s for s in archived_list.json()["sites"] if s["site_id"] == site_id
    )
    assert archived_site["is_active"] is False
    assert archived_site["status"] == "Offline"


def test_site_purge_requires_confirm(file_db: Any) -> None:
    """Purge without confirm=true is rejected."""
    site_id, _, _ = _seed_site_device_admin()
    client = TestClient(app)
    response = client.delete(
        f"/api/v1/sites/{site_id}", params={"mode": "purge"}, headers=_headers()
    )
    assert response.status_code == 400
    assert "confirm" in response.json()["detail"].lower()


def test_site_restore_keeps_devices_suspended(file_db: Any) -> None:
    """Restore flips an archived site back to active but leaves devices suspended.

    Model B: restoring a site un-hides the site; its devices stay suspended
    (is_active=false) until each is individually restored.
    """
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
        assert device is not None and device.is_active is False
        assert device.lifecycle_state == "suspended"
    finally:
        sync_db.close()


def test_site_restore_active_site_is_idempotent(file_db: Any) -> None:
    """Restoring an already-active site is a no-op success."""
    site_id, _, _ = _seed_site_device_admin()
    client = TestClient(app)
    response = client.post(f"/api/v1/sites/{site_id}/restore", headers=_headers())
    assert response.status_code == 200
    assert "already active" in response.json()["message"].lower()


def test_device_resume_reactivates_suspended_device(file_db: Any) -> None:
    """Resuming a device that was suspended by a site archive re-activates it.

    Model B: after archiving + restoring a site, the device stays suspended
    (is_active=false). Calling resume should bring it back to active/online so
    it reappears on the Dashboard.
    """
    site_id, device_id, _ = _seed_site_device_admin()
    client = TestClient(app)

    archived = client.delete(f"/api/v1/sites/{site_id}", headers=_headers())
    assert archived.status_code == 200

    restored = client.post(f"/api/v1/sites/{site_id}/restore", headers=_headers())
    assert restored.status_code == 200

    resumed = client.post(
        f"/api/v1/devices/device/{device_id}/resume", headers=_headers(), json={}
    )
    assert resumed.status_code == 200

    sync_db = homepot.database.SessionLocal()
    try:
        device = sync_db.query(Device).filter(Device.device_id == device_id).first()
        assert device is not None
        assert device.is_active is True
        assert device.lifecycle_state == "active"
        assert device.status == "online"
    finally:
        sync_db.close()


def test_device_resume_reactivates_unpaired_device(file_db: Any) -> None:
    """Resuming an independently-unpaired device re-activates it.

    A device archived directly (not via a site) has lifecycle_state 'unpaired'.
    The restore/resume action should bring it back to active/online.
    """
    _, device_id, _ = _seed_site_device_admin()
    client = TestClient(app)

    archived = client.delete(
        f"/api/v1/devices/device/{device_id}",
        params={"mode": "archive"},
        headers=_headers(),
    )
    assert archived.status_code == 200

    resumed = client.post(
        f"/api/v1/devices/device/{device_id}/resume", headers=_headers(), json={}
    )
    assert resumed.status_code == 200

    sync_db = homepot.database.SessionLocal()
    try:
        device = sync_db.query(Device).filter(Device.device_id == device_id).first()
        assert device is not None
        assert device.is_active is True
        assert device.lifecycle_state == "active"
        assert device.status == "online"
    finally:
        sync_db.close()


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


def test_device_purge_with_lifecycle_epoch_deletes(file_db: Any) -> None:
    """Purging a device whose current epoch is linked via lifecycle_epoch_id works.

    Regression: deleting the lifecycle epochs before the device row used to
    violate devices_lifecycle_epoch_id_fkey on PostgreSQL (device still
    referenced the epoch), returning an Internal Server Error.
    """
    device_id = "dev-epoch-001"
    _seed_device_with_epoch(device_id)
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
        epoch = sync_db.query(LifecycleEpoch).filter(
            LifecycleEpoch.device_id.isnot(None)
        )
        assert epoch.count() == 0
    finally:
        sync_db.close()


# --------------------------------------------------------------------------
# AI visibility guards (archived sites/devices must be invisible to the AI)
# --------------------------------------------------------------------------


def test_ai_insights_device_hidden_after_archive(file_db: Any) -> None:
    """AI device insights return 404 once the device is archived."""
    _, device_id, _ = _seed_site_device_admin()
    client = TestClient(app)

    active = client.get(f"/api/v1/ai/insights/device/{device_id}", headers=_headers())
    assert active.status_code in (200, 500)

    response = client.delete(f"/api/v1/devices/device/{device_id}", headers=_headers())
    assert response.status_code == 200

    archived = client.get(f"/api/v1/ai/insights/device/{device_id}", headers=_headers())
    assert archived.status_code == 404
    assert "not found or not active" in archived.json()["detail"].lower()


def test_ai_failure_prediction_hidden_after_archive(file_db: Any) -> None:
    """AI failure prediction returns 404 once the device is archived."""
    _, device_id, _ = _seed_site_device_admin()
    client = TestClient(app)

    active = client.get(
        f"/api/v1/ai/predictions/failure/{device_id}", headers=_headers()
    )
    assert active.status_code in (200, 500)

    response = client.delete(f"/api/v1/devices/device/{device_id}", headers=_headers())
    assert response.status_code == 200

    archived = client.get(
        f"/api/v1/ai/predictions/failure/{device_id}", headers=_headers()
    )
    assert archived.status_code == 404


def test_ai_site_insights_hidden_after_archive(file_db: Any) -> None:
    """AI site insights return 404 once the site is archived."""
    site_id, _, _ = _seed_site_device_admin()
    client = TestClient(app)

    active = client.get(f"/api/v1/ai/insights/site/{site_id}", headers=_headers())
    assert active.status_code in (200, 500)

    response = client.delete(f"/api/v1/sites/{site_id}", headers=_headers())
    assert response.status_code == 200

    archived = client.get(f"/api/v1/ai/insights/site/{site_id}", headers=_headers())
    assert archived.status_code == 404
    assert "not found or not active" in archived.json()["detail"].lower()


def test_ai_endpoints_require_auth(file_db: Any) -> None:
    """AI endpoints reject unauthenticated requests (401/403)."""
    site_id, _, _ = _seed_site_device_admin()
    client = TestClient(app)

    response = client.get(f"/api/v1/ai/insights/site/{site_id}")
    assert response.status_code in (401, 403)

    query = client.post("/api/v1/ai/query", json={"query": "hi"})
    assert query.status_code in (401, 403)


def test_ai_site_insights_scoped_to_user_access(file_db: Any) -> None:
    """A non-admin user without site membership is denied AI site insights."""
    site_id, _, _ = _seed_site_device_admin()
    client = TestClient(app)

    # Seed a non-admin viewer with no site membership.
    sync_db = homepot.database.SessionLocal()
    try:
        viewer = User(
            email="viewer@arch-purge.test",
            username="viewer_ap",
            hashed_password=hash_password("pass"),
            is_admin=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        sync_db.add(viewer)
        sync_db.commit()
    finally:
        sync_db.close()

    viewer_headers = {
        "Authorization": f"Bearer {create_access_token({'sub': 'viewer@arch-purge.test'})}"
    }

    # The viewer is not a member of the site, so AI insights are forbidden.
    denied = client.get(f"/api/v1/ai/insights/site/{site_id}", headers=viewer_headers)
    assert denied.status_code == 403

    # The admin still has access.
    allowed = client.get(f"/api/v1/ai/insights/site/{site_id}", headers=_headers())
    assert allowed.status_code in (200, 500)
