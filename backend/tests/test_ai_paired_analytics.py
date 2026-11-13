"""Fleet analytics must only count devices that are still paired.

A device is "paired" while it is enrolled and can still receive commands:
``pending``, ``active`` or ``suspended``. ``unpaired`` devices are retained for
audit/re-enrol but excluded from reliability, calibration and the task
overview. Purged devices have no row at all and are excluded implicitly.
"""

import asyncio
import os
import sys
import tempfile

current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from homepot.app.models.AnalyticsModel import (  # noqa: E402
    AIActionOutcome,
    AIActionPlan,
    AIActionStep,
)
from homepot.config import reload_settings  # noqa: E402
import homepot.database  # noqa: E402
from homepot.models import Base, Device, Site  # noqa: E402


@pytest.fixture(autouse=True)
def file_db(monkeypatch):
    """Point both the sync and async engines at one temporary SQLite file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    async_url = f"sqlite+aiosqlite:///{path}"
    sync_url = f"sqlite:///{path}"
    monkeypatch.setenv("DATABASE_URL", async_url)
    monkeypatch.setenv("DATABASE__URL", async_url)
    reload_settings()

    if homepot.database._db_service is not None:
        try:
            asyncio.run(homepot.database._db_service.close())
        except Exception:
            pass
        homepot.database._db_service = None

    engine = create_engine(
        sync_url, connect_args={"check_same_thread": False}, pool_pre_ping=True
    )
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(homepot.database, "sync_engine", engine)
    monkeypatch.setattr(homepot.database, "SessionLocal", sessionmaker(bind=engine))

    yield path

    engine.dispose()
    if os.path.exists(path):
        os.unlink(path)


def _add_plan(
    db, *, plan_id, target, status, trust_score, verified=False, outcome=None
):
    """Add a one-step plan targeting ``target`` with an optional outcome."""
    db.add(
        AIActionPlan(
            plan_id=plan_id,
            status=status,
            trust_score=trust_score,
            created_by="tester",
        )
    )
    db.add(
        AIActionStep(
            plan_id=plan_id,
            seq=0,
            action="restart_service",
            target_device_id=target,
        )
    )
    if outcome is None:
        outcome = verified
    if outcome:
        db.add(AIActionOutcome(plan_id=plan_id, verified=verified))


def _seed(db):
    site = Site(site_id="site-paired", name="Paired site", location="Lab")
    db.add(site)
    db.commit()
    db.refresh(site)

    for device_id, state, os_name in (
        ("DEV-PENDING", "pending", "Windows 11"),
        ("DEV-ACTIVE", "active", "Windows 11"),
        ("DEV-SUSPENDED", "suspended", "Windows 10"),
        ("DEV-UNPAIRED", "unpaired", "Windows 11"),
    ):
        db.add(
            Device(
                device_id=device_id,
                name=device_id,
                device_type="pos_terminal",
                site_id=site.id,
                lifecycle_state=state,
                os_details=os_name,
            )
        )

    _add_plan(
        db,
        plan_id="plan-pending",
        target="DEV-PENDING",
        status="succeeded",
        trust_score=0.9,
        verified=True,
    )
    _add_plan(
        db,
        plan_id="plan-active",
        target="DEV-ACTIVE",
        status="succeeded",
        trust_score=0.9,
        verified=True,
    )
    _add_plan(
        db,
        plan_id="plan-suspended",
        target="DEV-SUSPENDED",
        status="failed",
        trust_score=0.2,
        outcome=True,
    )
    # Retained but no longer part of the fleet: must not be assessed.
    _add_plan(
        db,
        plan_id="plan-unpaired",
        target="DEV-UNPAIRED",
        status="succeeded",
        trust_score=0.9,
        verified=True,
    )
    # Row was purged entirely; only the plan/step remain.
    _add_plan(
        db,
        plan_id="plan-purged",
        target="DEV-GONE",
        status="succeeded",
        trust_score=0.9,
        verified=True,
    )
    # Pending approval on an unpaired device: excluded from the task counts
    # but still surfaced by the approval badge.
    _add_plan(
        db,
        plan_id="plan-unpaired-approval",
        target="DEV-UNPAIRED",
        status="pending_approval",
        trust_score=0.5,
    )
    db.commit()


def test_reliability_counts_only_paired_devices():
    """Reliability includes pending/active/suspended, excludes unpaired/purged."""
    from ai.analytics_service import AIAnalyticsService

    db = homepot.database.SessionLocal()
    try:
        _seed(db)
    finally:
        db.close()

    result = asyncio.run(
        AIAnalyticsService.get_ai_action_reliability(action_type="restart_service")
    )

    assert result["total_plans"] == 3
    counts = result["action_types"]["restart_service"]["counts"]
    assert counts["proposed"] == 3
    assert counts["executed"] == 3
    assert counts["succeeded"] == 2
    assert counts["failed"] == 1
    # The unpaired and purged successes are not counted.
    assert counts["verified_improvement"] == 2


def test_calibration_counts_only_paired_devices():
    """Calibration bands are built from paired devices only."""
    from ai.analytics_service import AIAnalyticsService

    db = homepot.database.SessionLocal()
    try:
        _seed(db)
    finally:
        db.close()

    result = asyncio.run(AIAnalyticsService.get_confidence_calibration())

    assert result["total_plans"] == 3
    assert result["bands"]["0.80-1.00"]["plans"] == 2
    assert result["bands"]["0.80-1.00"]["succeeded"] == 2
    assert result["bands"]["0.20-0.40"]["plans"] == 1
    assert result["bands"]["0.20-0.40"]["failed"] == 1


def test_plan_summary_paired_only_keeps_needs_approval_unscoped():
    """Task counts exclude unpaired targets; the approval badge does not."""
    from homepot.app.repositories.ai_action_repository import AIActionRepository

    db = homepot.database.SessionLocal()
    try:
        _seed(db)
        repo = AIActionRepository(db)

        scoped = repo.plan_summary(paired_only=True)
        assert scoped["total"] == 3
        assert "pending_approval" not in scoped["by_status"]
        assert scoped["needs_approval"] == 1
        assert {p["plan_id"] for p in scoped["recent"]}.isdisjoint(
            {"plan-unpaired", "plan-purged", "plan-unpaired-approval"}
        )

        # Without the paired filter the summary still shows the full history.
        unfiltered = repo.plan_summary(paired_only=False)
        assert unfiltered["total"] == 6
    finally:
        db.close()
