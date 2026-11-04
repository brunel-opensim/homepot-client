"""Tests for autonomy hydration (D16) and confidence calibration (D15)."""

import asyncio
import os
import sys
import tempfile
from unittest.mock import AsyncMock, patch

current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from ai.actions import ActionProposal  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from homepot.app.ai_ops.autonomy import (  # noqa: E402
    get_autonomy_controller,
    hydrate_autonomy_from_reliability,
)
from homepot.app.models.AnalyticsModel import (  # noqa: E402
    AIActionOutcome,
)
from homepot.app.repositories import ai_action_repository  # noqa: E402
from homepot.config import reload_settings  # noqa: E402
import homepot.database  # noqa: E402
from homepot.models import Base, Device, Site, User  # noqa: E402
from homepot.app.auth_utils import create_access_token, hash_password  # noqa: E402


REL_METRICS = {
    "period_days": 30,
    "action_types": {
        "restart": {
            "counts": {
                "proposed": 2,
                "approved": 2,
                "rejected": 0,
                "executed": 5,
                "succeeded": 5,
                "failed": 0,
                "rolled_back": 1,
                "verified_improvement": 5,
            },
            "rates": {
                "proposal_acceptance": 1.0,
                "execution_success": 1.0,
                "verified_improvement": 1.0,
                "rollback_rate": 0.2,
            },
        }
    },
    "total_plans": 2,
}

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


def _seed(db):
    site = Site(site_id="site-a", name="Site A", location="Lab A")
    db.add(site)
    db.commit()
    db.refresh(site)
    device = Device(
        device_id="POS-A",
        name="POS A",
        device_type="pos_terminal",
        site_id=site.id,
        device_permissions={"root_access": True},
    )
    db.add(device)
    user = User(
        email="admin@cal.test",
        username="admin",
        hashed_password=hash_password("pass"),
        is_admin=True,
    )
    db.add(user)
    db.commit()
    return {"site": site, "device": device, "user": user}


def test_hydrate_autonomy_from_reliability():
    import homepot.app.ai_ops.autonomy as autonomy_mod

    autonomy_mod._controller = None
    with patch(
        "ai.analytics_service.AIAnalyticsService.get_ai_action_reliability",
        new=AsyncMock(return_value=REL_METRICS),
    ):
        controller = asyncio.run(hydrate_autonomy_from_reliability(days=30))
    level = controller.get_level("restart")
    assert level.sample_count == 5
    assert level.success_rate == 1.0
    assert level.rollback_proven is True


def test_autonomy_endpoint_returns_hydrated_levels(client: TestClient, monkeypatch):
    monkeypatch.setattr(
        "ai.analytics_service.AIAnalyticsService.get_ai_action_reliability",
        AsyncMock(return_value=REL_METRICS),
    )
    db = homepot.database.SessionLocal()
    try:
        seed = _seed(db)
        user_email = seed["user"].email
    finally:
        db.close()

    headers = {"Authorization": f"Bearer {create_access_token({'sub': user_email})}"}
    resp = client.get("/api/v1/ai/autonomy", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "restart" in body
    assert body["restart"]["sample_count"] == 5
