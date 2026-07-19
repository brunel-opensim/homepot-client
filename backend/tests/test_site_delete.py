"""Tests for site delete."""

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
from homepot.models import Base, Device, DeviceStatus, Site, User


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


def test_api_site_delete(file_db: Any) -> None:
    """Test backend site cascade deletion logic via the API."""
    sync_db = homepot.database.SessionLocal()
    try:
        site = Site(
            site_id="test-site-delete", name="Test Company Delete", is_active=True
        )
        sync_db.add(site)
        sync_db.commit()
        sync_db.refresh(site)

        device = Device(
            device_id="dev-delete-001",
            name="Test POS",
            device_type="pos_terminal",
            site_id=site.id,
            is_active=False,
            status=DeviceStatus.UNPAIRED,
        )
        sync_db.add(device)
        sync_db.commit()

        admin = User(
            email="admin@delete.test",
            username="admin_delete",
            hashed_password=hash_password("pass"),
            is_admin=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        sync_db.add(admin)
        sync_db.commit()
    finally:
        sync_db.close()

    token = create_access_token({"sub": "admin@delete.test"})
    headers = {"Authorization": f"Bearer {token}"}

    client = TestClient(app)
    response = client.delete("/api/v1/sites/test-site-delete", headers=headers)
    assert response.status_code == 200
    assert "deleted" in response.json()["message"].lower()
