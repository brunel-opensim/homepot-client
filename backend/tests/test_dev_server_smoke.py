"""Dev server smoke tests — validates a fresh deployment before real devices connect.

Each test maps to a line in the PR 30 spec.  Uses a temporary SQLite database
so no PostgreSQL is required.
"""

import os
import tempfile
from typing import Any, Generator

# Disable the agent simulator so the test suite verifies the production
# deployment path (simulation endpoints return 404).  This must be set
# before any local imports evaluate the settings singleton.
os.environ.setdefault("ENABLE_AGENT_SIMULATION", "false")

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from homepot.app.auth_utils import create_access_token, hash_password
from homepot.config import reload_settings
import homepot.database
from homepot.models import Base, LifecycleState
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
            import asyncio
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
    """Seed an admin user, a tenant, a site, and an operator."""
    db = homepot.database.SessionLocal()

    tenant = create_tenant_sync(db, name="Smoke Tenant", slug="smoke-tenant")
    site = create_site_sync(
        db, site_id="smoke-site-001", name="Smoke Site", tenant_id=tenant.id
    )
    op_user = create_user_sync(
        db,
        email="operator@smoke.test",
        username="operator",
        password="pass",
        tenant_id=tenant.id,
    )
    admin = create_user_sync(
        db,
        email="admin@smoke.test",
        username="admin",
        password="pass",
        is_admin=True,
    )

    create_tenant_membership_sync(
        db, user_id=op_user.id, tenant_id=tenant.id, role="admin"
    )
    create_site_membership_sync(
        db, user_id=op_user.id, site_id=site.id, role="operator"
    )

    db.commit()
    db.close()
    return {
        "tenant": tenant,
        "site": site,
        "operator": op_user,
        "admin": admin,
    }


# ===================================================================
# Smoke Tests
# ===================================================================


class TestDevServerSmoke:
    """PR 30 dev server smoke tests — validates a fresh deployment."""

    def test_health_responds_200(self, client: TestClient) -> None:
        """Health endpoint must return 200."""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_unauthenticated_endpoints_reject_401(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """Unauthenticated access to device endpoints must return 401."""
        resp = client.get("/api/v1/devices/device")
        assert resp.status_code == 401

        resp = client.post(
            "/api/v1/devices/device",
            json={
                "site_id": "smoke-site-001",
                "device_id": "new-dev",
                "name": "New",
                "device_type": "pos_terminal",
            },
        )
        assert resp.status_code == 401

    def test_admin_can_create_site_and_enrolment_intent(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """Admin can create a site and an enrolment intent."""
        headers = _auth_header("admin@smoke.test")

        # Create site
        resp = client.post(
            "/api/v1/sites/",
            json={"site_id": "new-site-001", "name": "New Site"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["site_id"] == "new-site-001"

        # Create enrolment intent on that site
        resp = client.post(
            "/api/v1/sites/new-site-001/enrolment-intents",
            json={
                "site_id": "new-site-001",
                "device_type": "pos_terminal",
                "expires_in_hours": 48,
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        intent = resp.json()
        assert "intent_id" in intent
        assert "claim_token" in intent

    def test_cors_headers_include_dev_server_origin(
        self, client: TestClient
    ) -> None:
        """CORS response includes the configured dev server origin."""
        resp = client.options(
            "/api/v1/sites/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200
        cors_origin = resp.headers.get("access-control-allow-origin")
        assert cors_origin is not None
        assert "http://localhost:3000" in cors_origin

    def test_simulator_is_off(self, client: TestClient) -> None:
        """Simulation endpoints return 404 when ENABLE_AGENT_SIMULATION is false.

        This test relies on the ``client`` fixture already having patched
        ``ENABLE_AGENT_SIMULATION=false`` before the lifespan ran (see the
        module-level environment setup below).
        """

        resp = client.get("/api/v1/agents/simulation/status")
        assert resp.status_code == 404, resp.text

        resp = client.post("/api/v1/agents/simulation/start")
        assert resp.status_code == 404, resp.text

        resp = client.post("/api/v1/agents/simulation/stop")
        assert resp.status_code == 404, resp.text

    def test_is_simulated_false_on_provisioned_device(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """is_simulated=false on provisioned devices (default)."""
        headers = _auth_header("admin@smoke.test")

        resp = client.post(
            "/api/v1/devices/device",
            json={
                "site_id": "smoke-site-001",
                "device_id": "real-pos-001",
                "name": "Real POS",
                "device_type": "pos_terminal",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

        resp = client.get(
            "/api/v1/devices/device/real-pos-001", headers=headers
        )
        assert resp.status_code == 200, resp.text
        device = resp.json()
        assert device.get("is_simulated") is not None
        assert device["is_simulated"] is False

    def test_agent_bootstrap_provision_and_heartbeat(
        self, client: TestClient, seeded_db: Any
    ) -> None:
        """Agent bootstrap-provision + heartbeat flow."""
        headers = _auth_header("admin@smoke.test")

        # 1. Create enrolment intent
        resp = client.post(
            "/api/v1/sites/smoke-site-001/enrolment-intents",
            json={
                "site_id": "smoke-site-001",
                "device_type": "pos_terminal",
                "expires_in_hours": 48,
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        intent = resp.json()
        intent_id = intent["intent_id"]
        claim_token = intent["claim_token"]

        # 2. Approve the intent
        resp = client.put(
            f"/api/v1/sites/smoke-site-001/enrolment-intents/{intent_id}",
            json={"status": "approved"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

        # 3. Claim the intent (simulate agent bootstrap)
        resp = client.post(
            f"/api/v1/enrolment-intents/{intent_id}/claim",
            json={
                "claim_token": claim_token,
                "device_name": "Agent POS",
                "device_type": "pos_terminal",
                "os_details": "SmokeTestOS 1.0",
                "expected_device_identity": "smoke-identity-001",
            },
        )
        assert resp.status_code == 200, resp.text
        claim = resp.json()
        claimed_device_id = claim["device_id"]
        assert "api_key" in claim
        assert "site_id" in claim

        api_key = claim["api_key"]

        # 4. Register device DNA
        dev_headers = _device_headers(claimed_device_id, api_key)
        resp = client.post(
            "/api/v1/agent/device-dna",
            json={
                "device_id": claimed_device_id,
                "mac_address": "aa:bb:cc:dd:ee:01",
                "local_ip": "192.168.1.50",
                "hostname": "agent-pos-box",
                "os_details": "SmokeTestOS 1.0",
            },
            headers=dev_headers,
        )
        assert resp.status_code == 200, resp.text

        # 5. Submit a heartbeat
        resp = client.post(
            "/api/v1/agent/heartbeat",
            json={
                "device_id": claimed_device_id,
                "is_healthy": True,
                "response_time_ms": 42,
                "status_code": 200,
                "endpoint": "/health",
                "response_data": {
                    "status": "healthy",
                    "system": {
                        "cpu_percent": 45.0,
                        "memory_percent": 60.0,
                    },
                },
            },
            headers=dev_headers,
        )
        assert resp.status_code == 200, resp.text

        # 6. Verify is_simulated=false on the claimed device
        resp = client.get(
            f"/api/v1/devices/device/{claimed_device_id}", headers=headers
        )
        assert resp.status_code == 200, resp.text
        device = resp.json()
        assert device["is_simulated"] is False
