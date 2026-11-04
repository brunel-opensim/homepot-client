"""Tests for fleet-wide action proposals (B5)."""

import asyncio
import os
import sys
import tempfile

current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from ai.tools import (  # noqa: E402
    TOOL_REGISTRY,
    get_tool_proposal_sink,
    propose_fleet_action,
    set_tool_proposal_sink,
)
import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from homepot.config import reload_settings  # noqa: E402
import homepot.database  # noqa: E402
from homepot.models import Base, Device, Site  # noqa: E402


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


def test_fleet_action_is_registered():
    assert "propose_fleet_action" in TOOL_REGISTRY


def test_propose_fleet_action_records_per_device_proposals():
    import homepot.database

    db = homepot.database.SessionLocal()
    try:
        site = Site(site_id="site-a", name="Site A", location="Lab A")
        db.add(site)
        db.commit()
        db.refresh(site)
        db.add(
            Device(
                device_id="POS-A",
                name="POS A",
                device_type="pos_terminal",
                site_id=site.id,
                is_active=True,
            )
        )
        db.commit()
    finally:
        db.close()

    sink = []
    token = set_tool_proposal_sink(sink)
    try:
        result = asyncio.run(
            propose_fleet_action(
                action="health_check", site_id="site-a", rationale="routine"
            )
        )
    finally:
        from ai.tools import reset_tool_proposal_sink

        reset_tool_proposal_sink(token)

    assert "Recorded 1 fleet proposal" in result
    assert len(sink) == 1
    assert sink[0].action == "health_check"
    assert sink[0].target_device_id == "POS-A"
