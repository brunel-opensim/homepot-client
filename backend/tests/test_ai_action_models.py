"""Tests for the AI action-delegation data model.

Phase 0 of ``docs/ai-delegation-plan.md`` is the persistence substrate only:
these tests cover table registration, persistence, relationships, defaults,
and cascade behaviour. No endpoints, LLM calls, or execution logic are
exercised here.
"""

import asyncio
import os
import tempfile

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from homepot.app.models.AnalyticsModel import (
    AIActionApproval,
    AIActionOutcome,
    AIActionPlan,
    AIActionStep,
)
from homepot.config import reload_settings
import homepot.database
from homepot.models import Base


@pytest.fixture(autouse=True)
def mock_db_url(monkeypatch):
    """Use a temporary file database for these tests."""
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
    NewSessionLocal = sessionmaker(bind=new_engine, autocommit=False, autoflush=False)

    monkeypatch.setattr(homepot.database, "sync_engine", new_engine)
    monkeypatch.setattr(homepot.database, "SessionLocal", NewSessionLocal)

    yield

    new_engine.dispose()
    if os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


def test_ai_action_tables_registered() -> None:
    """The models register all four delegation tables on the shared Base."""
    for table in (
        "ai_action_plan",
        "ai_action_step",
        "ai_approval",
        "ai_outcome",
    ):
        assert table in Base.metadata.tables


def test_plan_step_approval_outcome_round_trip() -> None:
    """A plan persists with its steps, approval, outcome, and defaults."""
    db = homepot.database.SessionLocal()
    try:
        plan = AIActionPlan(
            source_query_id="q-1",
            trust_mode="grounded",
            trust_score=0.92,
            passed_gates=["A", "B", "C", "D", "E"],
            risk_tier="T2",
            reversible=True,
            rationale="Config drift on POS-001.",
            evidence=[{"table": "configuration_history", "record_id": 7}],
            created_by="tech@test.local",
            provenance="simulated",
        )
        plan.steps.append(
            AIActionStep(
                seq=1,
                action="update_config",
                target_device_id="POS-001",
                params={"brightness": 80},
                postconditions={"config applied": True},
                rollback_params={"brightness": 100},
            )
        )
        plan.approvals.append(
            AIActionApproval(actor="tech@test.local", decision="approved")
        )
        plan.outcome = AIActionOutcome(
            verified=True,
            metrics_before={"cpu": 90},
            metrics_after={"cpu": 40},
        )
        db.add(plan)
        db.commit()
        plan_id = plan.plan_id
    finally:
        db.close()

    db = homepot.database.SessionLocal()
    try:
        loaded = db.execute(
            select(AIActionPlan).where(AIActionPlan.plan_id == plan_id)
        ).scalar_one()
        assert loaded.status == "proposed"
        assert loaded.reversible is True
        assert loaded.trust_score == 0.92
        assert loaded.passed_gates == ["A", "B", "C", "D", "E"]
        assert loaded.created_at is not None
        assert loaded.updated_at is not None

        assert len(loaded.steps) == 1
        step = loaded.steps[0]
        assert step.action == "update_config"
        assert step.status == "pending"
        assert step.step_id

        assert len(loaded.approvals) == 1
        approval = loaded.approvals[0]
        assert approval.decision == "approved"
        assert approval.approval_id
        assert approval.decided_at is not None

        assert loaded.outcome is not None
        assert loaded.outcome.verified is True
        assert loaded.outcome.rolled_back is False
        assert loaded.outcome.outcome_id
        assert loaded.outcome.recorded_at is not None
    finally:
        db.close()


def test_deleting_plan_cascades_to_children() -> None:
    """Deleting a plan removes its steps, approvals, and outcome."""
    db = homepot.database.SessionLocal()
    try:
        plan = AIActionPlan(rationale="cleanup")
        plan.steps.append(
            AIActionStep(seq=1, action="restart", target_device_id="POS-2")
        )
        plan.approvals.append(AIActionApproval(actor="tech", decision="rejected"))
        plan.outcome = AIActionOutcome(verified=False)
        db.add(plan)
        db.commit()
        plan_id = plan.plan_id
        db.delete(plan)
        db.commit()
    finally:
        db.close()

    db = homepot.database.SessionLocal()
    try:
        steps = (
            db.execute(select(AIActionStep).where(AIActionStep.plan_id == plan_id))
            .scalars()
            .all()
        )
        approvals = (
            db.execute(
                select(AIActionApproval).where(AIActionApproval.plan_id == plan_id)
            )
            .scalars()
            .all()
        )
        outcomes = (
            db.execute(
                select(AIActionOutcome).where(AIActionOutcome.plan_id == plan_id)
            )
            .scalars()
            .all()
        )
        assert steps == []
        assert approvals == []
        assert outcomes == []
    finally:
        db.close()


def test_plan_ids_are_unique() -> None:
    """Each generated plan_id is distinct."""
    db = homepot.database.SessionLocal()
    try:
        first = AIActionPlan()
        second = AIActionPlan()
        db.add_all([first, second])
        db.commit()
        assert first.plan_id
        assert second.plan_id
        assert first.plan_id != second.plan_id
    finally:
        db.close()
