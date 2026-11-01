"""Tests for backend-owned investigation sessions (Stage 2).

Covers session creation, listing, retrieval, resume, archiving, message
persistence, and per-operation authorisation (session isolation).
"""

import asyncio
import os
import sys
import tempfile

current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from fastapi.testclient import TestClient  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from homepot.app.auth_utils import create_access_token, hash_password  # noqa: E402
from homepot.config import reload_settings  # noqa: E402
import homepot.database  # noqa: E402
from homepot.models import Base, User  # noqa: E402


@pytest.fixture(autouse=True)
def mock_db_url(monkeypatch):
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

    engine = create_engine(
        db_url, connect_args={"check_same_thread": False}, pool_pre_ping=True
    )
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(homepot.database, "sync_engine", engine)
    monkeypatch.setattr(homepot.database, "SessionLocal", sessionmaker(bind=engine))
    yield
    engine.dispose()
    if os.path.exists(path):
        os.unlink(path)


def _make_user(db, email, *, is_admin=False):
    user = User(
        email=email,
        username=email.split("@")[0],
        hashed_password=hash_password("pass"),
        is_admin=is_admin,
        role="Admin" if is_admin else "Client",
        created_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
        updated_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _headers(email):
    token = create_access_token({"sub": email})
    return {"Authorization": f"Bearer {token}"}


def _client():
    from homepot.app.main import app

    return TestClient(app)


def test_create_and_list_session():
    db = homepot.database.SessionLocal()
    try:
        u = _make_user(db, "a@example.com")
    finally:
        db.close()

    client = _client()
    r = client.post(
        "/api/v1/investigations",
        json={"title": "t1"},
        headers=_headers("a@example.com"),
    )
    assert r.status_code == 200
    sid = r.json()["data"]["session_id"]
    assert sid

    r2 = client.get("/api/v1/investigations", headers=_headers("a@example.com"))
    assert r2.status_code == 200
    sessions = r2.json()["data"]["sessions"]
    assert any(s["session_id"] == sid for s in sessions)


def test_session_isolation():
    db = homepot.database.SessionLocal()
    try:
        _make_user(db, "a@example.com")
        _make_user(db, "b@example.com")
    finally:
        db.close()

    client = _client()
    r = client.post(
        "/api/v1/investigations",
        json={"title": "a's"},
        headers=_headers("a@example.com"),
    )
    sid = r.json()["data"]["session_id"]

    # b cannot read a's session
    r2 = client.get(f"/api/v1/investigations/{sid}", headers=_headers("b@example.com"))
    assert r2.status_code == 403

    # b cannot list a's session
    r3 = client.get("/api/v1/investigations", headers=_headers("b@example.com"))
    assert r3.status_code == 200
    assert not any(s["session_id"] == sid for s in r3.json()["data"]["sessions"])


def test_resume_session():
    db = homepot.database.SessionLocal()
    try:
        _make_user(db, "a@example.com")
    finally:
        db.close()

    client = _client()
    r = client.post(
        "/api/v1/investigations",
        json={"title": "resume"},
        headers=_headers("a@example.com"),
    )
    sid = r.json()["data"]["session_id"]

    # add a message
    r = client.post(
        f"/api/v1/investigations/{sid}/messages",
        json={"role": "user", "content": "hello"},
        headers=_headers("a@example.com"),
    )
    assert r.status_code == 200

    # resume
    r = client.post(
        f"/api/v1/investigations/{sid}/resume", headers=_headers("a@example.com")
    )
    assert r.status_code == 200
    msgs = r.json()["data"]["messages"]
    assert len(msgs) == 1
    assert msgs[0]["content"] == "hello"


def test_archive_session():
    db = homepot.database.SessionLocal()
    try:
        _make_user(db, "a@example.com")
    finally:
        db.close()

    client = _client()
    r = client.post(
        "/api/v1/investigations",
        json={"title": "arch"},
        headers=_headers("a@example.com"),
    )
    sid = r.json()["data"]["session_id"]

    r = client.patch(
        f"/api/v1/investigations/{sid}",
        json={"status": "archived"},
        headers=_headers("a@example.com"),
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "archived"

    # archived excluded from default list
    r = client.get("/api/v1/investigations", headers=_headers("a@example.com"))
    assert not any(s["session_id"] == sid for s in r.json()["data"]["sessions"])

    # included with include_archived
    r = client.get(
        "/api/v1/investigations?include_archived=true",
        headers=_headers("a@example.com"),
    )
    assert any(s["session_id"] == sid for s in r.json()["data"]["sessions"])


def test_message_ordering():
    db = homepot.database.SessionLocal()
    try:
        _make_user(db, "a@example.com")
    finally:
        db.close()

    client = _client()
    r = client.post(
        "/api/v1/investigations",
        json={"title": "msgs"},
        headers=_headers("a@example.com"),
    )
    sid = r.json()["data"]["session_id"]

    for i in range(3):
        client.post(
            f"/api/v1/investigations/{sid}/messages",
            json={"role": "user", "content": f"msg{i}"},
            headers=_headers("a@example.com"),
        )

    r = client.get(
        f"/api/v1/investigations/{sid}/messages", headers=_headers("a@example.com")
    )
    msgs = r.json()["data"]["messages"]
    assert [m["content"] for m in msgs] == ["msg0", "msg1", "msg2"]


def test_run_lifecycle():
    db = homepot.database.SessionLocal()
    try:
        _make_user(db, "a@example.com")
    finally:
        db.close()

    client = _client()
    r = client.post(
        "/api/v1/investigations",
        json={"title": "run"},
        headers=_headers("a@example.com"),
    )
    sid = r.json()["data"]["session_id"]

    r = client.post(
        f"/api/v1/investigations/{sid}/runs",
        json={"status": "running"},
        headers=_headers("a@example.com"),
    )
    assert r.status_code == 200
    run_id = r.json()["data"]["run_id"]
    assert r.json()["data"]["status"] == "running"

    r = client.patch(
        f"/api/v1/investigations/{sid}/runs/{run_id}",
        json={"status": "completed"},
        headers=_headers("a@example.com"),
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "completed"
    assert r.json()["data"]["completed_at"] is not None

    # invalid status rejected
    r = client.patch(
        f"/api/v1/investigations/{sid}/runs/{run_id}",
        json={"status": "bogus"},
        headers=_headers("a@example.com"),
    )
    assert r.status_code == 400
