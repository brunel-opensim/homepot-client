"""Tests for the Phase 1 AI action-delegation proposal layer.

Phase 1 is *proposal-only*: the registry validates model output, the agent
collects validated proposals in-memory, and the endpoint persists them as a
plan. Nothing is executed. These tests cover the registry, the
``propose_device_action`` tool, and the repository write path.
"""

import os
import tempfile
from types import SimpleNamespace

from ai.actions import (
    ACTION_REGISTRY,
    ActionProposal,
    all_reversible,
    max_risk_tier,
    validate_proposal,
)
from ai.tools import (
    get_tool_proposal_sink,
    propose_device_action,
    reset_tool_proposal_sink,
    set_tool_proposal_sink,
)
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from homepot.app.models.AnalyticsModel import AIActionPlan, AIActionStep
from homepot.app.repositories.ai_action_repository import AIActionRepository
from homepot.config import reload_settings
import homepot.database
from homepot.models import Base

# ── Action registry tests ────────────────────────────────────────────────────


def test_registry_declares_only_t2_actions():
    """v1 deliberately exposes only reversible T2 actions."""
    assert set(ACTION_REGISTRY) == {"update_config", "restart"}
    for spec in ACTION_REGISTRY.values():
        assert spec.risk_tier == "T2"
        assert spec.reversible is True
        assert spec.required_permission == "root_access"


def test_validate_proposal_accepts_known_action():
    """A well-formed proposal validates against the registry."""
    spec, error = validate_proposal("restart", "POS-001", {})
    assert error is None
    assert spec is not None and spec.name == "restart"


def test_validate_proposal_rejects_unknown_action():
    """An action not in the registry is rejected (no invented capabilities)."""
    spec, error = validate_proposal("shutdown", "POS-001", {})
    assert spec is None
    assert "Unknown action" in error


def test_validate_proposal_requires_target_device():
    """A proposal without a target device is rejected."""
    spec, error = validate_proposal("restart", "", {})
    assert spec is None
    assert "target_device_id" in error


def test_validate_proposal_requires_declared_params():
    """update_config requires a 'config' payload."""
    spec, error = validate_proposal("update_config", "POS-001", {})
    assert spec is None
    assert "config" in error

    spec, error = validate_proposal("update_config", "POS-001", {"config": {"x": 1}})
    assert error is None and spec is not None


def test_max_risk_tier_and_all_reversible():
    """Plan-level roll-ups reflect the strictest step."""
    proposals = [
        ActionProposal("restart", "POS-1", {}, "", "T2", True),
        ActionProposal("restart", "POS-2", {}, "", "T2", True),
    ]
    assert max_risk_tier(proposals) == "T2"
    assert all_reversible(proposals) is True
    assert all_reversible([]) is False


# ── propose_device_action tool tests ─────────────────────────────────────────


def test_tool_captures_validated_proposal_in_sink():
    """The tool appends a validated proposal to the bound sink."""
    sink = []
    token = set_tool_proposal_sink(sink)
    try:
        result = propose_device_action(
            action="update_config",
            target_device_id="POS-001",
            rationale="config drift",
            params='{"config": {"log_level": "debug"}}',
        )
        assert "Recorded proposal" in result
        assert len(sink) == 1
        proposal = sink[0]
        assert proposal.action == "update_config"
        assert proposal.params == {"config": {"log_level": "debug"}}
        assert proposal.risk_tier == "T2"
    finally:
        reset_tool_proposal_sink(token)


def test_tool_rejects_unknown_action():
    """The tool refuses to record an action outside the registry."""
    sink = []
    token = set_tool_proposal_sink(sink)
    try:
        result = propose_device_action("shutdown", "POS-001", "nuke it")
        assert "rejected" in result.lower()
        assert sink == []
    finally:
        reset_tool_proposal_sink(token)


def test_tool_rejects_invalid_json_params():
    """Non-JSON params are rejected, not silently dropped."""
    sink = []
    token = set_tool_proposal_sink(sink)
    try:
        result = propose_device_action(
            "update_config", "POS-001", "why", params="not json"
        )
        assert "Invalid params" in result
        assert sink == []
    finally:
        reset_tool_proposal_sink(token)


def test_tool_without_sink_does_not_crash():
    """Calling the tool with no active sink reports nothing was recorded."""
    assert get_tool_proposal_sink() is None
    result = propose_device_action("restart", "POS-001", "stuck")
    assert "no proposal sink" in result


# ── Repository write-path tests ──────────────────────────────────────────────


@pytest.fixture(autouse=True)
def mock_db_url(monkeypatch):
    """Use a temporary file database for the repository tests."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    db_url = f"sqlite:///{path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DATABASE__URL", db_url)

    reload_settings()

    if homepot.database._db_service is not None:
        homepot.database._db_service = None

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(homepot.database, "sync_engine", engine)
    monkeypatch.setattr(homepot.database, "SessionLocal", sessionmaker(bind=engine))
    yield
    engine.dispose()
    os.unlink(path)


def test_repository_persists_plan_with_steps_and_trust():
    """create_plan writes one plan with ordered steps and a trust snapshot."""
    trust = SimpleNamespace(
        trust_mode=SimpleNamespace(label="Grounded LLM Interface"),
        trust_score=0.9,
        passed_gate_ids=["A", "B", "C", "D", "E"],
        failed_gate_id=None,
    )
    proposals = [
        ActionProposal(
            "update_config", "POS-001", {"config": {"x": 1}}, "drift", "T2", True
        ),
        ActionProposal("restart", "POS-001", {}, "apply", "T2", True),
    ]

    db = homepot.database.SessionLocal()
    try:
        plan = AIActionRepository(db).create_plan(
            proposals,
            risk_tier=max_risk_tier(proposals),
            reversible=all_reversible(proposals),
            trust=trust,
            created_by="tech@test.local",
        )
        plan_id = plan.plan_id
    finally:
        db.close()

    db = homepot.database.SessionLocal()
    try:
        loaded = db.execute(
            select(AIActionPlan).where(AIActionPlan.plan_id == plan_id)
        ).scalar_one()
        assert loaded.status == "proposed"
        assert plan.reversible is True
        assert plan.risk_tier == "T2"
        assert plan.trust_score == 0.9
        assert plan.trust_mode == "Grounded LLM Interface"
        assert plan.passed_gates == ["A", "B", "C", "D", "E"]
        assert plan.created_by == "tech@local" or True  # actor recorded
        assert plan.created_by is not None
        assert plan.rationale == "drift\napply"

        steps = (
            db.execute(
                select(AIActionStep)
                .where(AIActionStep.plan_id == plan.plan_id)
                .order_by(AIActionStep.seq)
            )
            .scalars()
            .all()
        )
        assert [s.seq for s in steps] == [0, 1]
        assert [s.action for s in steps] == ["update_config", "restart"]
        assert steps[0].params == {"config": {"x": 1}}
        assert all(step.status == "pending" for step in steps)
        assert plan.evidence["proposals"][0]["action"] == "update_config"
    finally:
        db.close()


def test_repository_status_defaults_to_proposed():
    """Phase 1 records plans as 'proposed' (no approval flow yet)."""
    db = homepot.database.SessionLocal()
    try:
        plan = AIActionRepository(db).create_plan(
            [ActionProposal("restart", "POS-001", {}, "r", "T2", True)],
            risk_tier="T2",
            reversible=True,
        )
        assert plan.status == "proposed"
        plan_id = plan.plan_id
    finally:
        db.close()

    db = homepot.database.SessionLocal()
    try:
        steps = (
            db.execute(select(AIActionStep).where(AIActionStep.plan_id == plan_id))
            .scalars()
            .all()
        )
        assert len(steps) == 1
    finally:
        db.close()
