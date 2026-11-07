"""Tests for confidence calibration (D15)."""

import asyncio
import os
import sys
import tempfile
from unittest.mock import AsyncMock

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

CALIBRATION = {
    "period_days": 30,
    "buckets": 5,
    "bands": {
        "0.80-1.00": {
            "trust_min": 0.8,
            "trust_max": 1.0,
            "plans": 2,
            "succeeded": 2,
            "failed": 0,
            "avg_trust_score": 0.9,
            "observed_success_rate": 1.0,
            "calibration_gap": -0.1,
        }
    },
    "total_plans": 2,
}


@pytest.fixture(autouse=True)
def mock_db_url(monkeypatch):
    """Use a temporary SQLite database for each test."""
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


def _seed_user(db):
    user = User(
        email="admin@cal.test",
        username="admin",
        hashed_password=hash_password("pass"),
        is_admin=True,
    )
    db.add(user)
    db.commit()
    return user


def test_calibration_endpoint_returns_bands(client: TestClient, monkeypatch):
    """Return confidence calibration bands from the endpoint."""
    monkeypatch.setattr(
        "ai.analytics_service.AIAnalyticsService.get_confidence_calibration",
        AsyncMock(return_value=CALIBRATION),
    )
    db = homepot.database.SessionLocal()
    try:
        user = _seed_user(db)
        user_email = user.email
    finally:
        db.close()

    headers = {"Authorization": f"Bearer {create_access_token({'sub': user_email})}"}
    resp = client.get("/api/v1/ai/calibration?days=30", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "bands" in body
    assert body["total_plans"] == 2


def test_calibrate_direct():
    """Expose the confidence calibration service through AI operations."""
    # Smoke: the analytics function exists and is callable.
    from ai.analytics_service import AIAnalyticsService
    import homepot.app.ai_ops  # noqa

    assert hasattr(AIAnalyticsService, "get_confidence_calibration")
