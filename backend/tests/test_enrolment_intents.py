"""Tests for enrolment intent creation, listing, status transitions, and token operations."""

import asyncio
import os
import tempfile
from typing import Any, Generator

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from homepot.app.auth_utils import create_access_token
from homepot.config import reload_settings
import homepot.database
from homepot.models import Base, EnrolmentIntent, EnrolmentIntentStatus, Site, User
from homepot.seed_factories import (
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
    """Use a temporary SQLite file so sync+async engines share data between tests."""
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
    """Create a FastAPI TestClient with lifespan handlers for the async engine."""
    from homepot.main import app

    with TestClient(app) as tc:
        yield tc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth_header(email: str) -> dict[str, str]:
    """Build an Authorization header with a bearer token for the given email."""
    token = create_access_token({"sub": email})
    return {"Authorization": f"Bearer {token}"}


def _intent_payload(site_id: str, **overrides: Any) -> dict[str, Any]:
    """Build a minimal create-intent payload, merged with any overrides."""
    payload = {
        "site_id": site_id,
        "enrolment_method": "pre-provisioned",
        "expires_in_hours": 48,
    }
    payload.update(overrides)
    return payload


def _read_and_close(db: Any, site: Site, user: User) -> tuple[str, str]:
    """Read email and site_id while the session is active, then close it."""
    email_val = user.email
    site_id = site.site_id
    db.close()
    return email_val, site_id


def _seed_operator(db: Any) -> tuple[str, str]:
    """Create tenant, site, user and operator-level membership. Returns (email, site_id)."""
    tenant = create_tenant_sync(db, name="EI Test Tenant", slug="ei-test-tenant")
    site = create_site_sync(
        db, site_id="site-ei-1", name="Enrolment Intent Site", tenant_id=tenant.id
    )
    user = create_user_sync(
        db,
        email="operator@example.com",
        username="operator",
        password="pass",
        tenant_id=tenant.id,
    )
    create_tenant_membership_sync(
        db, user_id=user.id, tenant_id=tenant.id, role="admin"
    )
    create_site_membership_sync(db, user_id=user.id, site_id=site.id, role="operator")
    db.commit()
    db.refresh(site)
    db.refresh(user)
    return _read_and_close(db, site, user)


def _seed_viewer(db: Any) -> tuple[str, str]:
    """Create tenant, site, user and viewer-level membership. Returns (email, site_id)."""
    tenant = create_tenant_sync(db, name="EI Viewer Tenant", slug="ei-viewer-tenant")
    site = create_site_sync(
        db, site_id="site-ei-viewer", name="Viewer Site", tenant_id=tenant.id
    )
    user = create_user_sync(
        db,
        email="viewer@example.com",
        username="viewer",
        password="pass",
        tenant_id=tenant.id,
    )
    create_tenant_membership_sync(
        db, user_id=user.id, tenant_id=tenant.id, role="viewer"
    )
    create_site_membership_sync(db, user_id=user.id, site_id=site.id, role="viewer")
    db.commit()
    db.refresh(site)
    db.refresh(user)
    return _read_and_close(db, site, user)


def _seed_user_only(db: Any, email: str = "nosite@example.com") -> str:
    """Create a user with no site memberships. Returns email string."""
    user = create_user_sync(
        db, email=email, username=email.split("@")[0], password="pass"
    )
    db.commit()
    db.refresh(user)
    email_val = user.email
    db.close()
    return email_val


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateEnrolmentIntent:
    """Tests for POST /sites/{site_id}/enrolment-intents."""

    def test_creates_intent_and_returns_claim_token(self, client: TestClient):
        """Create a pending intent, verify the claim token is returned and the hash stored in the DB."""
        db = homepot.database.SessionLocal()
        email, site_id = _seed_operator(db)

        response = client.post(
            f"/api/v1/sites/{site_id}/enrolment-intents",
            json=_intent_payload(site_id),
            headers=_auth_header(email),
        )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["status"] == "success"
        assert "claim_token" in data
        assert len(data["claim_token"]) > 20
        assert "intent_id" in data

        db = homepot.database.SessionLocal()
        intent = (
            db.query(EnrolmentIntent)
            .filter(EnrolmentIntent.intent_id == data["intent_id"])
            .first()
        )
        assert intent is not None
        assert intent.status == EnrolmentIntentStatus.PENDING
        assert intent.claim_token_hash is not None
        assert intent.claim_token_hash != data["claim_token"]
        db.close()

    def test_rejects_unauthenticated_request(self, client: TestClient):
        """POST without an Authorization header returns 401."""
        response = client.post(
            "/api/v1/sites/site-ei-1/enrolment-intents",
            json=_intent_payload("site-ei-1"),
        )
        assert response.status_code == 401

    def test_rejects_insufficient_role(self, client: TestClient):
        """A user with viewer (not operator) role gets 403."""
        db = homepot.database.SessionLocal()
        email, site_id = _seed_viewer(db)

        response = client.post(
            f"/api/v1/sites/{site_id}/enrolment-intents",
            json=_intent_payload(site_id),
            headers=_auth_header(email),
        )
        assert response.status_code == 403

    def test_rejects_unknown_site(self, client: TestClient):
        """POST for a non-existent site returns 404."""
        db = homepot.database.SessionLocal()
        email, _site_id = _seed_operator(db)

        response = client.post(
            "/api/v1/sites/does-not-exist/enrolment-intents",
            json=_intent_payload("does-not-exist"),
            headers=_auth_header(email),
        )
        assert response.status_code == 404

    def test_accepts_optional_fields(self, client: TestClient):
        """expected_device_identity and idempotency_key are persisted correctly."""
        db = homepot.database.SessionLocal()
        email, site_id = _seed_operator(db)

        response = client.post(
            f"/api/v1/sites/{site_id}/enrolment-intents",
            json=_intent_payload(
                site_id,
                expires_in_hours=72,
                expected_device_identity="SN-ABC-123",
                idempotency_key="req-test-001",
            ),
            headers=_auth_header(email),
        )
        assert response.status_code == 200, response.text

        db = homepot.database.SessionLocal()
        intent = (
            db.query(EnrolmentIntent)
            .filter(EnrolmentIntent.idempotency_key == "req-test-001")
            .first()
        )
        assert intent is not None
        assert intent.expected_device_identity == "SN-ABC-123"
        db.close()


class TestListEnrolmentIntents:
    """Tests for GET /sites/{site_id}/enrolment-intents."""

    def test_lists_intents_for_site(self, client: TestClient):
        """Return all intents for a site with total count; no claim_token_hash leaked."""
        db = homepot.database.SessionLocal()
        email, site_id = _seed_operator(db)

        client.post(
            f"/api/v1/sites/{site_id}/enrolment-intents",
            json=_intent_payload(site_id),
            headers=_auth_header(email),
        )
        client.post(
            f"/api/v1/sites/{site_id}/enrolment-intents",
            json=_intent_payload(site_id, expires_in_hours=24),
            headers=_auth_header(email),
        )

        response = client.get(
            f"/api/v1/sites/{site_id}/enrolment-intents",
            headers=_auth_header(email),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["intents"]) == 2
        for intent in data["intents"]:
            assert intent["status"] == "pending"
            assert "intent_id" in intent
            assert "expires_at" in intent
            assert "created_at" in intent
            assert "claim_token_hash" not in intent

    def test_filters_by_status(self, client: TestClient):
        """The ?status= query parameter filters returned intents."""
        db = homepot.database.SessionLocal()
        email, site_id = _seed_operator(db)

        client.post(
            f"/api/v1/sites/{site_id}/enrolment-intents",
            json=_intent_payload(site_id),
            headers=_auth_header(email),
        )

        response = client.get(
            f"/api/v1/sites/{site_id}/enrolment-intents?status=consumed",
            headers=_auth_header(email),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["intents"]) == 0


class TestUpdateEnrolmentIntentStatus:
    """Tests for PUT /sites/{site_id}/enrolment-intents/{intent_id}."""

    def _create_intent(self, email: str, site_id: str, client: TestClient) -> str:
        """Create a pending intent and return its intent_id."""
        resp = client.post(
            f"/api/v1/sites/{site_id}/enrolment-intents",
            json=_intent_payload(site_id),
            headers=_auth_header(email),
        )
        return resp.json()["intent_id"]

    def test_approve_pending_intent(self, client: TestClient):
        """Transition a pending intent to approved."""
        db = homepot.database.SessionLocal()
        email, site_id = _seed_operator(db)
        intent_id = self._create_intent(email, site_id, client)

        response = client.put(
            f"/api/v1/sites/{site_id}/enrolment-intents/{intent_id}",
            json={"status": "approved"},
            headers=_auth_header(email),
        )
        assert response.status_code == 200
        assert response.json()["new_status"] == "approved"

    def test_reject_pending_intent(self, client: TestClient):
        """Transition a pending intent to rejected."""
        db = homepot.database.SessionLocal()
        email, site_id = _seed_operator(db)
        intent_id = self._create_intent(email, site_id, client)

        response = client.put(
            f"/api/v1/sites/{site_id}/enrolment-intents/{intent_id}",
            json={"status": "rejected"},
            headers=_auth_header(email),
        )
        assert response.status_code == 200
        assert response.json()["new_status"] == "rejected"

    def test_revoke_pending_intent(self, client: TestClient):
        """Transition a pending intent to revoked."""
        db = homepot.database.SessionLocal()
        email, site_id = _seed_operator(db)
        intent_id = self._create_intent(email, site_id, client)

        response = client.put(
            f"/api/v1/sites/{site_id}/enrolment-intents/{intent_id}",
            json={"status": "revoked"},
            headers=_auth_header(email),
        )
        assert response.status_code == 200
        assert response.json()["new_status"] == "revoked"

    def test_rejects_update_when_not_pending(self, client: TestClient):
        """Updating a non-pending intent (e.g. approved to revoked) returns 400."""
        db = homepot.database.SessionLocal()
        email, site_id = _seed_operator(db)
        intent_id = self._create_intent(email, site_id, client)

        client.put(
            f"/api/v1/sites/{site_id}/enrolment-intents/{intent_id}",
            json={"status": "approved"},
            headers=_auth_header(email),
        )
        response = client.put(
            f"/api/v1/sites/{site_id}/enrolment-intents/{intent_id}",
            json={"status": "revoked"},
            headers=_auth_header(email),
        )
        assert response.status_code == 400


class TestRegenerateToken:
    """Tests for POST /sites/{site_id}/enrolment-intents/{intent_id}/regenerate-token."""

    def test_regenerates_token_for_pending_intent(self, client: TestClient):
        """Regenerate a token returns a new token different from the original."""
        db = homepot.database.SessionLocal()
        email, site_id = _seed_operator(db)

        create_resp = client.post(
            f"/api/v1/sites/{site_id}/enrolment-intents",
            json=_intent_payload(site_id),
            headers=_auth_header(email),
        )
        data = create_resp.json()
        intent_id = data["intent_id"]
        original_token = data["claim_token"]

        response = client.post(
            f"/api/v1/sites/{site_id}/enrolment-intents/{intent_id}/regenerate-token",
            headers=_auth_header(email),
        )
        assert response.status_code == 200
        new_token = response.json()["claim_token"]
        assert new_token != original_token
        assert len(new_token) > 20


class TestGetEnrolmentIntent:
    """Tests for GET /sites/{site_id}/enrolment-intents/{intent_id}."""

    def test_get_returns_intent_details(self, client: TestClient):
        """Fetch intent details, verify no claim_token_hash is exposed."""
        db = homepot.database.SessionLocal()
        email, site_id = _seed_operator(db)

        create_resp = client.post(
            f"/api/v1/sites/{site_id}/enrolment-intents",
            json=_intent_payload(site_id, expected_device_identity="SN-GET-TEST"),
            headers=_auth_header(email),
        )
        intent_id = create_resp.json()["intent_id"]

        response = client.get(
            f"/api/v1/sites/{site_id}/enrolment-intents/{intent_id}",
            headers=_auth_header(email),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["intent_id"] == intent_id
        assert data["status"] == "pending"
        assert data["expected_device_identity"] == "SN-GET-TEST"
        assert "claim_token_hash" not in data
