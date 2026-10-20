"""Signup must never create a privileged account.

``POST /auth/signup`` is public (rate-limited only), and its request body
carries a caller-supplied ``role``. Historically the endpoint derived the
stored ``User.is_admin`` flag from ``is_privileged()``, which returns ``True``
for every role while ``HOMEPOT_DEV_UNIFIED_ACCESS`` is on. That meant a
self-registered ``Technician`` was written to the database as a genuine admin
and could reach admin-only endpoints -- the role-assignment and user-deletion
routes both authorise via ``require_role("Admin")``, which treats a set
``is_admin`` column as Admin.

Against the old code the end-to-end test below observes a self-registered
account receiving 200 from ``PUT /auth/users/{email}/role`` and promoting
another user; with the fix it receives 403.

These tests exercise the endpoint rather than the helper, because the helper
was already covered and correct; the defect was in how signup called it.
"""

import asyncio
import os
import tempfile
from typing import Any, Generator

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from homepot.app.api.API_v1.Endpoints import UserRegisterEndpoint
from homepot.app.roles import ADMIN
from homepot.config import reload_settings
import homepot.database
from homepot.models import Base

pytestmark = pytest.mark.slow


@pytest.fixture(autouse=True)
def file_db(monkeypatch: Any) -> Generator[None, None, None]:
    """Use a temporary file-based SQLite DB so sync+async engines share data.

    An in-memory database is private to a single connection, so a helper
    reading through ``get_db()`` would not see rows the request wrote. The
    file-backed engine is the pattern the other endpoint tests use.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    db_url = f"sqlite:///{path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DATABASE__URL", db_url)
    reload_settings()

    # Drop any service left over from the previous test before re-initialising.
    # The suite's autouse reset_db_service fixture closes the service after each
    # test, but ordering means a stale service can still be bound to a file that
    # has since been deleted, which surfaces as "no such table: users".
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

    # ``UserRegisterEndpoint`` binds ``SessionLocal`` at import time
    # (``from homepot.database import SessionLocal``), so patching the attribute
    # on ``homepot.database`` alone is not enough -- the endpoint module keeps
    # its own reference to the original session factory. Without this second
    # patch the endpoint keeps reading the database that was current when the
    # module was first imported, which only has the schema on the first test.
    monkeypatch.setattr(
        UserRegisterEndpoint,
        "SessionLocal",
        new_session_local,
    )

    # The tenant FK matters: signup attaches the new user to the "default"
    # tenant when one exists. Seed it through the same session factory the API
    # uses so it lands in the shared file database.
    db = new_session_local()
    try:
        if db.query(homepot.models.Tenant).count() == 0:
            db.add(homepot.models.Tenant(name="Default", slug="default"))
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
    """Clear the signup rate limiter between tests.

    ``POST /auth/signup`` is limited to 5 requests per minute and the limiter
    uses process-wide in-memory storage, so without this the later tests in the
    module receive 429 rather than exercising the endpoint.
    """
    from homepot.app.utils.limiter import limiter

    limiter.reset()
    yield
    limiter.reset()


_SIGNUP_PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def signed_up_user(client: TestClient, request: Any) -> Any:
    """Register a user with an explicit requested role; return its email."""
    counter = {"n": 0}

    def _signup(role: str) -> str:
        counter["n"] += 1
        email = (
            f"signup-{role.lower()}-{abs(hash(request.node.name))}"
            f"-{counter['n']}@example.com"
        )
        resp = client.post(
            "/api/v1/auth/signup",
            json={
                "email": email,
                "password": _SIGNUP_PASSWORD,
                "full_name": "Signup Probe",
                "role": role,
            },
        )
        assert resp.status_code == 201, resp.text
        return email

    return _signup


def _stored_user(email: str) -> Any:
    """Read a user row through the shared session factory."""
    db = homepot.database.SessionLocal()
    try:
        return db.query(homepot.models.User).filter_by(email=email).first()
    finally:
        db.close()


def _login(client: TestClient, email: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": _SIGNUP_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return str(resp.json()["data"]["access_token"])


class TestSignupCannotCreatePrivilegedUser:
    """A public signup must never produce an admin-equivalent row."""

    @pytest.mark.parametrize(
        "requested_role",
        ["Technician", "technician", "viewer", "Client", "engineer"],
    )
    def test_non_admin_role_is_not_stored_as_admin(
        self, signed_up_user: Any, requested_role: str
    ) -> None:
        """Any non-Admin role must store is_admin=False."""
        user = _stored_user(signed_up_user(requested_role))
        assert user is not None
        assert bool(user.is_admin) is False, (
            f"signup with role={requested_role!r} stored is_admin=True; a "
            "non-admin role must never be a route to privilege"
        )

    def test_requested_admin_role_is_also_not_honoured(
        self, signed_up_user: Any
    ) -> None:
        """Self-registration must not mint an admin even if Admin is asked for."""
        user = _stored_user(signed_up_user(ADMIN))
        assert user is not None
        assert bool(user.is_admin) is False
        assert user.role != ADMIN

    def test_signup_always_lands_on_the_least_privileged_role(
        self, signed_up_user: Any
    ) -> None:
        """The stored role is Technician regardless of what was requested."""
        user = _stored_user(signed_up_user("Admin"))
        assert user is not None
        assert user.role == "Technician"


class TestSignupEscalationIsClosed:
    """The concrete escalation that motivated the fix must no longer work."""

    def test_self_registered_user_cannot_assign_roles(
        self, client: TestClient, signed_up_user: Any
    ) -> None:
        """A signup-created account must be refused by the admin-only route.

        Before the fix the row carried is_admin=True, so require_role("Admin")
        saw "Admin" and returned 200, promoting the victim. The victim account
        is created too, so a 404 ("User not found") cannot be what stops the
        request -- a 403 is only evidence of the role check if the target
        exists.
        """
        attacker_email = signed_up_user("Technician")
        victim_email = signed_up_user("Technician")
        token = _login(client, attacker_email)

        resp = client.put(
            f"/api/v1/auth/users/{victim_email}/role",
            params={"new_role": "Admin"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403, (
            "a self-registered account reached the role-assignment endpoint "
            f"for an existing user; expected 403, got {resp.status_code}"
        )

        victim = _stored_user(victim_email)
        assert victim is not None
        assert bool(victim.is_admin) is False
        assert victim.role != ADMIN

    def test_login_response_reports_signup_user_as_non_admin(
        self, client: TestClient, signed_up_user: Any
    ) -> None:
        """The login response and the stored column must agree."""
        email = signed_up_user("Technician")
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": _SIGNUP_PASSWORD},
        )
        assert resp.status_code == 200, resp.text

        user = _stored_user(email)
        assert user is not None
        assert resp.json()["data"]["is_admin"] is False
        assert resp.json()["data"]["is_admin"] == bool(user.is_admin)
