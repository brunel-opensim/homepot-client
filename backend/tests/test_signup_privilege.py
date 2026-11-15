"""Signup is admin-only and never creates a privileged account.

``POST /auth/signup`` now requires an authenticated Admin (it is no longer
public).  Admins use it to provision Technician or Viewer accounts; the
caller-supplied ``role`` is honoured (admin-only, so it is safe) but it can
never mint an Admin -- promotion to Admin goes through ``PUT
/auth/users/{email}/role``.

These tests exercise the endpoint rather than the helper, because the
defect being guarded against is in how signup calls it.
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

from homepot.app.api.API_v1.Endpoints import UserRegisterEndpoint
from homepot.config import reload_settings
import homepot.database
from homepot.models import Base, User

pytestmark = pytest.mark.slow


_ADMIN_EMAIL = "admin@test.com"
_ADMIN_PASSWORD = "admin-password-correct-horse"
_TECH_EMAIL = "tech@test.com"
_TECH_PASSWORD = "tech-password-correct-horse"


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
    monkeypatch.setattr(
        UserRegisterEndpoint,
        "SessionLocal",
        new_session_local,
    )

    db = new_session_local()
    try:
        if db.query(homepot.models.Tenant).count() == 0:
            db.add(homepot.models.Tenant(name="Default", slug="default"))
            db.commit()
        # Seed an admin and a technician so the access-control tests can log in.
        from homepot.app.auth_utils import hash_password

        if db.query(User).filter(User.email == _ADMIN_EMAIL).count() == 0:
            db.add(
                User(
                    email=_ADMIN_EMAIL,
                    username="admin",
                    hashed_password=hash_password(_ADMIN_PASSWORD),
                    role="Admin",
                    is_admin=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
        if db.query(User).filter(User.email == _TECH_EMAIL).count() == 0:
            db.add(
                User(
                    email=_TECH_EMAIL,
                    username="tech",
                    hashed_password=hash_password(_TECH_PASSWORD),
                    role="Technician",
                    is_admin=False,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
        db.commit()
    finally:
        db.close()

    yield

    new_engine.dispose()
    if os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Test client with lifespan handlers that initialise the database."""
    from homepot.main import app

    with TestClient(app) as tc:
        yield tc


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> Generator[None, None, None]:
    """Clear the signup rate limiter between tests."""
    from homepot.app.utils.limiter import limiter

    limiter.reset()
    yield
    limiter.reset()


def _login(client: TestClient, email: str, password: str) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text


class TestSignupRequiresAdmin:
    """Signup is admin-only: unauthenticated and non-admin callers are rejected."""

    def test_unauthenticated_signup_is_rejected(self, client: TestClient) -> None:
        """Unauthenticated signup must be rejected (401/403)."""
        resp = client.post(
            "/api/v1/auth/signup",
            json={
                "email": "anon@example.com",
                "password": "correct-horse-battery-staple",
                "full_name": "Anon",
                "username": "anon",
            },
        )
        assert resp.status_code in (401, 403), resp.text

    def test_non_admin_signup_is_rejected(self, client: TestClient) -> None:
        """A non-admin (Technician) caller must be rejected (401/403)."""
        _login(client, _TECH_EMAIL, _TECH_PASSWORD)
        resp = client.post(
            "/api/v1/auth/signup",
            json={
                "email": "second@example.com",
                "password": "correct-horse-battery-staple",
                "full_name": "Second",
                "username": "second",
            },
        )
        assert resp.status_code in (401, 403), resp.text
        # Clear the session so later tests start unauthenticated.
        client.cookies.clear()


class TestAdminCanCreateUsers:
    """An admin can create Technician and Viewer accounts via signup."""

    def _signup_as_admin(self, client: TestClient, role: str, email: str) -> Any:
        _login(client, _ADMIN_EMAIL, _ADMIN_PASSWORD)
        resp = client.post(
            "/api/v1/auth/signup",
            json={
                "email": email,
                "password": "correct-horse-battery-staple",
                "full_name": "Created User",
                "username": email.split("@")[0],
                "role": role,
            },
        )
        assert resp.status_code == 201, resp.text
        return email

    def test_admin_creates_technician(self, client: TestClient) -> None:
        """An admin can create a Technician account."""
        email = "newtech@example.com"
        self._signup_as_admin(client, "Technician", email)

        db = homepot.database.SessionLocal()
        try:
            user = db.query(homepot.models.User).filter_by(email=email).first()
            assert user is not None
            assert user.role == "Technician"
            assert bool(user.is_admin) is False
        finally:
            db.close()

    def test_admin_creates_viewer(self, client: TestClient) -> None:
        """An admin can create a Viewer account."""
        email = "newviewer@example.com"
        self._signup_as_admin(client, "Viewer", email)

        db = homepot.database.SessionLocal()
        try:
            user = db.query(homepot.models.User).filter_by(email=email).first()
            assert user is not None
            assert user.role == "Viewer"
            assert bool(user.is_admin) is False
        finally:
            db.close()

    def test_admin_cannot_create_admin_via_signup(self, client: TestClient) -> None:
        """Signup must never create an admin, even when Admin is requested."""
        email = "newadmin@example.com"
        _login(client, _ADMIN_EMAIL, _ADMIN_PASSWORD)
        resp = client.post(
            "/api/v1/auth/signup",
            json={
                "email": email,
                "password": "correct-horse-battery-staple",
                "full_name": "Created Admin",
                "username": "newadmin",
                "role": "Admin",
            },
        )
        assert resp.status_code in (400, 403), resp.text

    def test_signup_defaults_to_technician(self, client: TestClient) -> None:
        """Signup defaults to Technician when no role is supplied."""
        email = "defaultrole@example.com"
        _login(client, _ADMIN_EMAIL, _ADMIN_PASSWORD)
        resp = client.post(
            "/api/v1/auth/signup",
            json={
                "email": email,
                "password": "correct-horse-battery-staple",
                "full_name": "Default Role",
                "username": "defaultrole",
            },
        )
        assert resp.status_code == 201, resp.text

        db = homepot.database.SessionLocal()
        try:
            user = db.query(homepot.models.User).filter_by(email=email).first()
            assert user is not None
            assert user.role == "Technician"
            assert bool(user.is_admin) is False
        finally:
            db.close()
