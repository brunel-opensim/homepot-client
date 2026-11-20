"""Regression tests for the AI action-plan SSE stream.

The stream holds one SQLAlchemy session for its whole lifetime. These tests
verify that a status committed by another session is observed by that same
stream without waiting for the client to reconnect.
"""

import asyncio
from datetime import datetime, timezone
import os
import sys
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from ai.actions import ActionProposal  # noqa: E402
from homepot.app.api.API_v1.Endpoints.AIActionEndpoint import (  # noqa: E402
    stream_action_plans,
)
from homepot.app.auth_utils import hash_password  # noqa: E402
from homepot.app.models.AnalyticsModel import AIActionPlan  # noqa: E402
from homepot.app.repositories.ai_action_repository import (  # noqa: E402
    AIActionRepository,
)
from homepot.config import reload_settings  # noqa: E402
import homepot.database  # noqa: E402
from homepot.models import Base, User  # noqa: E402


@pytest.fixture(autouse=True)
def mock_db_url(tmp_path, monkeypatch):
    """Use an isolated WAL-mode SQLite file so two sessions can write/read."""
    db_url = f"sqlite:///{tmp_path / 'stream.db'}"
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
        db_url,
        connect_args={"check_same_thread": False, "timeout": 30},
        pool_pre_ping=True,
    )
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(homepot.database, "sync_engine", engine)
    monkeypatch.setattr(homepot.database, "SessionLocal", sessionmaker(bind=engine))
    yield
    engine.dispose()


def _seed_admin_and_plan():
    """Create an admin and an executing plan; return the email and plan id."""
    db = homepot.database.SessionLocal()
    try:
        email = "stream-admin@deleg.test"
        db.add(
            User(
                email=email,
                username="stream-admin",
                hashed_password=hash_password("pass"),
                is_admin=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
        plan = AIActionRepository(db).create_plan(
            [
                ActionProposal(
                    "restart",
                    "DEV-STREAM-1",
                    {},
                    "verify SSE freshness",
                    "T2",
                    True,
                )
            ],
            risk_tier="T2",
            reversible=True,
            created_by="ai@deleg.test",
            status="executing",
        )
        return email, plan.plan_id
    finally:
        db.close()


@pytest.mark.asyncio
async def test_stream_observes_status_committed_by_another_session():
    """A succeeded commit in another session produces a new plan frame."""
    email, plan_id = _seed_admin_and_plan()

    stream_db = homepot.database.SessionLocal()
    response = await stream_action_plans(
        plan_status=None,
        days=30,
        current_user={"email": email},
        db=stream_db,
    )
    frames = response.body_iterator
    try:
        first_frame = await asyncio.wait_for(anext(frames), timeout=5)
        assert "event: plan" in first_frame
        assert "executing" in first_frame

        writer = homepot.database.SessionLocal()
        try:
            stored = writer.query(AIActionPlan).filter_by(plan_id=plan_id).one()
            stored.status = "succeeded"
            writer.commit()
        finally:
            writer.close()

        saw_succeeded = False
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            frame = await asyncio.wait_for(anext(frames), timeout=2)
            if "event: plan" in frame and "succeeded" in frame:
                saw_succeeded = True
                break

        assert saw_succeeded, "stream never emitted the committed status change"
    finally:
        await frames.aclose()
        stream_db.close()
