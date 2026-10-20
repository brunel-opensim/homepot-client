"""Unit tests for require_role's stored-role enforcement.

require_role is not exercised anywhere else in the suite, which is how the
admin-claim bypass went unnoticed. These tests call the dependency directly so
they are independent of the HTTP/DB fixture plumbing.
"""

from typing import Any

from fastapi import HTTPException
import pytest

from homepot.app.auth_utils import TokenData, require_role
from homepot.seed_factories import create_user_sync


class _FakeQuery:
    def __init__(self, user: Any) -> None:
        self._user = user

    def filter(self, *a: Any, **k: Any) -> "_FakeQuery":
        return self

    def first(self) -> Any:
        return self._user


class _FakeSession:
    """Minimal stand-in for a Session, returning a fixed user."""

    def __init__(self, user: Any) -> None:
        self._user = user

    def query(self, *a: Any, **k: Any) -> _FakeQuery:
        return _FakeQuery(self._user)


@pytest.fixture
def db_session() -> Any:
    """Return an in-memory session holding one Technician and one Admin."""
    import os
    import tempfile

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import homepot.database
    from homepot.models import Base

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(
        f"sqlite:///{path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    homepot.database.SessionLocal = sessionmaker(bind=engine, autoflush=False)

    session = homepot.database.SessionLocal()
    create_user_sync(
        session,
        email="tech@example.com",
        username="tech",
        password="x",
        role="Technician",
        is_admin=False,
    )
    create_user_sync(
        session,
        email="boss@example.com",
        username="boss",
        password="x",
        role="Admin",
        is_admin=True,
    )
    session.commit()
    yield session
    session.close()
    engine.dispose()
    os.unlink(path)


def _call(db: Any, email: str, token_role: str, required: str = "Admin") -> Any:
    """Invoke the require_role dependency with a forged token role."""
    checker = require_role(required)
    return checker(TokenData(email=email, role=token_role), db)


def test_technician_with_admin_token_claim_is_rejected(db_session: Any) -> None:
    """An inflated token claim must not grant admin access."""
    with pytest.raises(HTTPException) as exc:
        _call(db_session, "tech@example.com", "Admin")
    assert exc.value.status_code == 403


def test_admin_is_allowed(db_session: Any) -> None:
    """A genuine admin passes."""
    result = _call(db_session, "boss@example.com", "Admin")
    assert result["role"] == "Admin"


def test_technician_without_claim_is_rejected(db_session: Any) -> None:
    """A technician is rejected even without the inflated claim."""
    with pytest.raises(HTTPException) as exc:
        _call(db_session, "tech@example.com", "User")
    assert exc.value.status_code == 403


def test_unknown_user_is_rejected(db_session: Any) -> None:
    """A token for a user absent from the database is rejected."""
    with pytest.raises(HTTPException) as exc:
        _call(db_session, "ghost@example.com", "Admin")
    assert exc.value.status_code == 403


def test_stored_role_beats_token_claim_after_demotion(db_session: Any) -> None:
    """A demoted admin loses access even while holding an old admin token."""
    from homepot.models import User

    boss = db_session.query(User).filter(User.email == "boss@example.com").first()
    boss.role = "Technician"
    boss.is_admin = False
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        _call(db_session, "boss@example.com", "Admin")
    assert exc.value.status_code == 403
