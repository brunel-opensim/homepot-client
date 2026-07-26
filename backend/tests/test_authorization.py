"""Tests for ownership enforcement at API boundaries.

Verifies that:
- User from tenant A cannot view or modify tenant B.
- Site operator cannot act outside assigned sites.
- Device credentials only operate on that same device.
- Unauthenticated provisioning and unpairing are rejected.
"""

import asyncio
import os
import tempfile
from typing import Any, Generator

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from homepot.app.auth_utils import (
    create_access_token,
    hash_password,
)
from homepot.config import reload_settings
import homepot.database
from homepot.models import Base, LifecycleState, Site
from homepot.seed_factories import (
    create_device_sync,
    create_site_membership_sync,
    create_site_sync,
    create_tenant_membership_sync,
    create_tenant_sync,
    create_user_sync,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
    if os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Test client with lifespan handlers that init the async engine."""
    from homepot.main import app

    with TestClient(app) as tc:
        yield tc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth_header(email: str) -> dict[str, str]:
    token = create_access_token({"sub": email})
    return {"Authorization": f"Bearer {token}"}


def _device_headers(device_id: str, api_key: str = "device-key") -> dict[str, str]:
    return {"X-Device-ID": device_id, "X-API-Key": api_key}


# ---------------------------------------------------------------------------
# Seed data fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded_db(file_db: Any) -> Any:
    """Seed two tenants, each with site, device, and user, plus an admin user."""
    db = homepot.database.SessionLocal()

    tenant_a = create_tenant_sync(db, name="Tenant A", slug="tenant-a")
    tenant_b = create_tenant_sync(db, name="Tenant B", slug="tenant-b")

    site_a = create_site_sync(
        db, site_id="site-a-1", name="Site A-1", tenant_id=tenant_a.id
    )
    site_b = create_site_sync(
        db, site_id="site-b-1", name="Site B-1", tenant_id=tenant_b.id
    )

    dev_a = create_device_sync(
        db,
        device_id="dev-a-1",
        name="Device A-1",
        device_type="pos_terminal",
        site_id=site_a.id,
        is_active=True,
        lifecycle_state=LifecycleState.ACTIVE.value,
        api_key_hash=hash_password("device-key"),
    )
    dev_b = create_device_sync(
        db,
        device_id="dev-b-1",
        name="Device B-1",
        device_type="pos_terminal",
        site_id=site_b.id,
        is_active=True,
        lifecycle_state=LifecycleState.ACTIVE.value,
        api_key_hash=hash_password("device-key"),
    )

    user_a = create_user_sync(
        db,
        email="user.a@example.com",
        username="user.a",
        password="pass",
        tenant_id=tenant_a.id,
    )
    user_b = create_user_sync(
        db,
        email="user.b@example.com",
        username="user.b",
        password="pass",
        tenant_id=tenant_b.id,
    )
    admin = create_user_sync(
        db,
        email="admin@example.com",
        username="admin",
        password="pass",
        is_admin=True,
    )

    create_tenant_membership_sync(
        db, user_id=user_a.id, tenant_id=tenant_a.id, role="admin"
    )
    create_tenant_membership_sync(
        db, user_id=user_b.id, tenant_id=tenant_b.id, role="admin"
    )

    create_site_membership_sync(
        db, user_id=user_a.id, site_id=site_a.id, role="operator"
    )
    create_site_membership_sync(
        db, user_id=user_b.id, site_id=site_b.id, role="operator"
    )

    db.commit()
    db.close()
    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "site_a": site_a,
        "site_b": site_b,
        "dev_a": dev_a,
        "dev_b": dev_b,
        "user_a": user_a,
        "user_b": user_b,
        "admin": admin,
    }


# ===================================================================
# Tests: unauthenticated requests are rejected
# ===================================================================


class TestUnauthenticated:
    """Unauthenticated requests to protected endpoints must be rejected."""

    def test_list_sites_requires_auth(self, client: TestClient, seeded_db: Any) -> None:
        """Unauthenticated list-sites request must be rejected."""
        resp = client.get("/api/v1/sites/")
        assert resp.status_code == 401

    def test_get_site_requires_auth(self, client: TestClient, seeded_db: Any) -> None:
        """Unauthenticated get-site request must be rejected."""
        resp = client.get("/api/v1/sites/site-a-1")
        assert resp.status_code == 401

    def test_create_site_requires_auth(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """Unauthenticated create-site request must be rejected."""
        resp = client.post(
            "/api/v1/sites/", json={"site_id": "new-site", "name": "New"}
        )
        assert resp.status_code == 401

    def test_delete_site_requires_auth(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """Unauthenticated delete-site request must be rejected."""
        resp = client.delete("/api/v1/sites/site-a-1")
        assert resp.status_code == 401

    def test_site_stats_requires_auth(self, client: TestClient, seeded_db: Any) -> None:
        """Unauthenticated site-stats request must be rejected."""
        resp = client.get("/api/v1/sites/site-a-1/stats")
        assert resp.status_code == 401

    def test_list_devices_requires_auth(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """Unauthenticated list-devices request must be rejected."""
        resp = client.get("/api/v1/devices/device")
        assert resp.status_code == 401

    def test_get_device_requires_auth(self, client: TestClient, seeded_db: Any) -> None:
        """Unauthenticated get-device request must be rejected."""
        resp = client.get("/api/v1/devices/device/dev-a-1")
        assert resp.status_code == 401

    def test_create_device_requires_auth(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """Unauthenticated create-device request must be rejected."""
        resp = client.post(
            "/api/v1/devices/device",
            json={
                "site_id": "site-a-1",
                "device_id": "new-dev",
                "name": "New",
                "device_type": "pos_terminal",
            },
        )
        assert resp.status_code == 401

    def test_register_device_to_site_requires_auth(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """Unauthenticated register-device request must be rejected."""
        resp = client.post(
            "/api/v1/devices/sites/site-a-1/devices",
            json={
                "site_id": "site-a-1",
                "device_id": "new-dev",
                "name": "New",
                "device_type": "pos_terminal",
            },
        )
        assert resp.status_code == 401

    def test_update_device_requires_auth(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """Unauthenticated update-device request must be rejected."""
        resp = client.put("/api/v1/devices/device/dev-a-1", json={"name": "Updated"})
        assert resp.status_code == 401

    def test_delete_device_requires_auth(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """Unauthenticated delete-device request must be rejected."""
        resp = client.delete("/api/v1/devices/device/dev-a-1")
        assert resp.status_code == 401

    def test_provision_requires_auth(self, client: TestClient, seeded_db: Any) -> None:
        """Unauthenticated provision request must be rejected."""
        resp = client.post(
            "/api/v1/devices/provision",
            json={
                "site_id": "site-a-1",
                "user_identity": "tech@example.com",
                "device_type": "pos_terminal",
            },
        )
        assert resp.status_code == 401

    def test_queue_command_requires_auth(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """Unauthenticated queue-command request must be rejected."""
        resp = client.post(
            "/api/v1/devices/dev-a-1/commands",
            json={"command_type": "restart"},
        )
        assert resp.status_code == 401

    def test_create_job_requires_auth(self, client: TestClient, seeded_db: Any) -> None:
        """Unauthenticated create-job request must be rejected."""
        resp = client.post(
            "/api/v1/sites/site-a-1/jobs",
            json={"action": "restart"},
        )
        assert resp.status_code == 401

    def test_toggle_monitor_requires_auth(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """Unauthenticated toggle-monitor request must be rejected."""
        resp = client.put("/api/v1/devices/device/dev-a-1/monitor?monitor=true")
        assert resp.status_code == 401


# ===================================================================
# Tests: Cross-tenant isolation
# ===================================================================


class TestCrossTenantIsolation:
    """User from tenant A must not be able to view or modify tenant B's data."""

    def test_user_a_cannot_get_site_b(self, client: TestClient, seeded_db: Any) -> None:
        """User A must be denied access to tenant B's site."""
        resp = client.get(
            "/api/v1/sites/site-b-1", headers=_auth_header("user.a@example.com")
        )
        assert resp.status_code == 403

    def test_user_a_cannot_list_site_b_devices(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """User A must be denied listing tenant B's devices."""
        resp = client.get(
            "/api/v1/devices/sites/site-b-1/devices",
            headers=_auth_header("user.a@example.com"),
        )
        assert resp.status_code == 403

    def test_user_a_cannot_get_device_b(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """User A must be denied reading tenant B's device."""
        resp = client.get(
            "/api/v1/devices/device/dev-b-1",
            headers=_auth_header("user.a@example.com"),
        )
        assert resp.status_code == 403

    def test_user_a_cannot_update_device_b(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """User A must be denied updating tenant B's device."""
        resp = client.put(
            "/api/v1/devices/device/dev-b-1",
            json={"name": "Hacked"},
            headers=_auth_header("user.a@example.com"),
        )
        assert resp.status_code == 403

    def test_user_a_cannot_delete_device_b(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """User A must be denied deleting tenant B's device."""
        resp = client.delete(
            "/api/v1/devices/device/dev-b-1",
            headers=_auth_header("user.a@example.com"),
        )
        assert resp.status_code == 403

    def test_user_a_cannot_create_device_in_site_b(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """User A must be denied creating a device in tenant B's site."""
        resp = client.post(
            "/api/v1/devices/device",
            json={
                "site_id": "site-b-1",
                "device_id": "dev-a-trojan",
                "name": "Trojan",
                "device_type": "pos_terminal",
            },
            headers=_auth_header("user.a@example.com"),
        )
        assert resp.status_code == 403

    def test_user_a_cannot_register_device_to_site_b(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """User A must be denied registering a device to tenant B's site."""
        resp = client.post(
            "/api/v1/devices/sites/site-b-1/devices",
            json={
                "site_id": "site-b-1",
                "device_id": "dev-trojan",
                "name": "Trojan",
                "device_type": "pos_terminal",
            },
            headers=_auth_header("user.a@example.com"),
        )
        assert resp.status_code == 403

    def test_user_a_cannot_provision_to_site_b(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """User A must be denied provisioning a device to tenant B's site."""
        resp = client.post(
            "/api/v1/devices/provision",
            json={
                "site_id": "site-b-1",
                "user_identity": "hacker@evil.com",
                "device_type": "pos_terminal",
            },
            headers=_auth_header("user.a@example.com"),
        )
        assert resp.status_code == 403

    def test_user_a_cannot_queue_command_on_device_b(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """User A must be denied queuing a command on tenant B's device."""
        resp = client.post(
            "/api/v1/devices/dev-b-1/commands",
            json={"command_type": "restart"},
            headers=_auth_header("user.a@example.com"),
        )
        assert resp.status_code == 403

    def test_user_a_cannot_create_job_on_site_b(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """User A must be denied creating a job on tenant B's site."""
        resp = client.post(
            "/api/v1/sites/site-b-1/jobs",
            json={"action": "restart"},
            headers=_auth_header("user.a@example.com"),
        )
        assert resp.status_code == 403

    def test_user_a_cannot_get_site_b_stats(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """User A must be denied reading tenant B's site statistics."""
        resp = client.get(
            "/api/v1/sites/site-b-1/stats",
            headers=_auth_header("user.a@example.com"),
        )
        assert resp.status_code == 403

    def test_user_a_cannot_toggle_site_b_monitor(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """User A must be denied toggling monitoring on tenant B's site."""
        resp = client.put(
            "/api/v1/sites/site-b-1/monitor?monitor=true",
            headers=_auth_header("user.a@example.com"),
        )
        assert resp.status_code == 403

    def test_user_a_cannot_delete_site_b(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """User A must be denied deleting tenant B's site."""
        resp = client.delete(
            "/api/v1/sites/site-b-1",
            headers=_auth_header("user.a@example.com"),
        )
        assert resp.status_code == 403

    def test_user_b_cannot_get_site_a(self, client: TestClient, seeded_db: Any) -> None:
        """User B must be denied access to tenant A's site (symmetry check)."""
        resp = client.get(
            "/api/v1/sites/site-a-1", headers=_auth_header("user.b@example.com")
        )
        assert resp.status_code == 403

    def test_user_b_cannot_list_site_a_devices(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """User B must be denied listing tenant A's devices (symmetry check)."""
        resp = client.get(
            "/api/v1/devices/sites/site-a-1/devices",
            headers=_auth_header("user.b@example.com"),
        )
        assert resp.status_code == 403

    def test_list_devices_only_shows_own_accessible(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """User A listing devices should not include devices from tenant B."""
        resp = client.get(
            "/api/v1/devices/device", headers=_auth_header("user.a@example.com")
        )
        assert resp.status_code == 200
        device_ids = [d["device_id"] for d in resp.json()["devices"]]
        assert "dev-a-1" in device_ids
        assert "dev-b-1" not in device_ids

    def test_list_sites_only_shows_own_accessible(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """User A listing sites should not include sites from tenant B."""
        resp = client.get("/api/v1/sites/", headers=_auth_header("user.a@example.com"))
        assert resp.status_code == 200
        site_ids = [s["site_id"] for s in resp.json()["sites"]]
        assert "site-a-1" in site_ids
        assert "site-b-1" not in site_ids


# ===================================================================
# Tests: Site operator scope
# ===================================================================


class TestSiteOperatorScope:
    """Site operator must not act outside assigned sites."""

    def test_operator_on_site_a_cannot_modify_site_b(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """Operator on site A must be denied modifying a device on site B."""
        resp = client.put(
            "/api/v1/devices/device/dev-b-1",
            json={"name": "Hacked"},
            headers=_auth_header("user.a@example.com"),
        )
        assert resp.status_code == 403

    def test_viewer_cannot_perform_operator_actions(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """A viewer-level user should be denied operator-level operations."""
        db = homepot.database.SessionLocal()
        site_a = db.query(Site).filter(Site.site_id == "site-a-1").first()
        viewer_user = create_user_sync(
            db, email="viewer@example.com", username="viewer", password="pass"
        )
        create_site_membership_sync(
            db, user_id=viewer_user.id, site_id=site_a.id, role="viewer"
        )
        db.close()

        resp = client.put(
            "/api/v1/devices/device/dev-a-1",
            json={"name": "Viewer Update"},
            headers=_auth_header("viewer@example.com"),
        )
        assert resp.status_code == 403


# ===================================================================
# Tests: Device credentials scope
# ===================================================================


class TestDeviceCredentials:
    """Device credentials only operate on that same device."""

    def test_device_cannot_access_other_device_data(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """Device credentials must not grant access to other devices' data."""
        resp = client.get(
            "/api/v1/devices/pending",
            headers=_device_headers("dev-a-1"),
        )
        assert resp.status_code == 200

        wrong_headers = {"X-Device-ID": "dev-a-1", "X-API-Key": "wrong-key"}
        resp = client.get(
            "/api/v1/devices/pending",
            headers=wrong_headers,
        )
        assert resp.status_code == 401


# ===================================================================
# Tests: Admin bypass
# ===================================================================


class TestAdminBypass:
    """Admin users bypass site-level access checks."""

    def test_admin_can_access_any_site(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """Admin must be able to access any site regardless of tenant."""
        resp = client.get(
            "/api/v1/sites/site-b-1", headers=_auth_header("admin@example.com")
        )
        assert resp.status_code == 200
        assert resp.json()["site_id"] == "site-b-1"

    def test_admin_can_get_any_device(self, client: TestClient, seeded_db: Any) -> None:
        """Admin must be able to read any device regardless of tenant."""
        resp = client.get(
            "/api/v1/devices/device/dev-b-1",
            headers=_auth_header("admin@example.com"),
        )
        assert resp.status_code == 200
        assert resp.json()["device_id"] == "dev-b-1"

    def test_admin_list_devices_shows_all(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """Admin listing devices must include devices from all tenants."""
        resp = client.get(
            "/api/v1/devices/device", headers=_auth_header("admin@example.com")
        )
        assert resp.status_code == 200
        device_ids = [d["device_id"] for d in resp.json()["devices"]]
        assert "dev-a-1" in device_ids
        assert "dev-b-1" in device_ids

    def test_admin_list_sites_shows_all(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """Admin listing sites must include sites from all tenants."""
        resp = client.get("/api/v1/sites/", headers=_auth_header("admin@example.com"))
        assert resp.status_code == 200
        site_ids = [s["site_id"] for s in resp.json()["sites"]]
        assert "site-a-1" in site_ids
        assert "site-b-1" in site_ids
