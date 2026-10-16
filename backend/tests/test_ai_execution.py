"""Tests for the Phase 3 AI action-delegation executor.

Covers the policy engine, the executor's command queueing + snapshot capture,
the verifier's success/failure/rollback state machine, and the execute
endpoint. Execution is driven with an in-memory fake command service so the
state machine is fully deterministic and needs no live device.
"""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, Optional

from ai.actions import ActionProposal
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from homepot.app.ai_ops.executor import start_execution
from homepot.app.ai_ops.policy import evaluate_plan
from homepot.app.ai_ops.verifier import reconcile_plan
from homepot.app.auth_utils import create_access_token, hash_password
from homepot.app.models.AnalyticsModel import AIActionOutcome
from homepot.app.repositories.ai_action_repository import AIActionRepository
from homepot.config import reload_settings
import homepot.database
from homepot.models import Base, Device, LifecycleState, Site, SiteMembership, User


@pytest.fixture(autouse=True)
def mock_db_url(tmp_path, monkeypatch):
    """Use a temporary file database for these tests."""
    db_url = f"sqlite:///{tmp_path / 'exec.db'}"
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


class FakeCommandService:
    """Minimal async command store for deterministic execution tests."""

    def __init__(self) -> None:
        """Initialize an empty command store."""
        self.created = []
        self.commands: Dict[str, SimpleNamespace] = {}

    async def create_device_command(
        self,
        device_id: int,
        command_type: str,
        payload: Optional[Dict[str, Any]] = None,
        issued_by: Optional[str] = None,
    ) -> SimpleNamespace:
        """Record and return a fake device command."""
        command = SimpleNamespace(
            command_id=f"cmd-{len(self.created) + 1}",
            device_id=device_id,
            command_type=command_type,
            payload=payload,
            issued_by=issued_by,
            status="pending",
            result=None,
        )
        self.created.append(command)
        self.commands[command.command_id] = command
        return command

    async def get_command(self, command_id: str) -> Optional[SimpleNamespace]:
        """Return a previously created fake command, if any."""
        return self.commands.get(command_id)


def _make_user(db, email, *, is_admin=False):
    user = User(
        email=email,
        username=email.split("@")[0],
        hashed_password=hash_password("pass"),
        is_admin=is_admin,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed(db, *, lifecycle=LifecycleState.ACTIVE.value, config=None):
    """Create a site, one device, an admin, a member tech and a non-member."""
    site = Site(site_id="site-a", name="Site A", location="Lab A")
    db.add(site)
    db.commit()
    db.refresh(site)

    device = Device(
        device_id="POS-A",
        name="POS A",
        device_type="pos_terminal",
        site_id=site.id,
        lifecycle_state=lifecycle,
        device_permissions={"root_access": True},
    )
    if config is not None:
        device.config = config
    db.add(device)

    admin = _make_user(db, "admin@exec.test", is_admin=True)
    tech = _make_user(db, "tech@exec.test")
    nonmember = _make_user(db, "none@exec.test")
    db.add(SiteMembership(user_id=tech.id, site_id=site.id, role="operator"))
    db.commit()
    return {
        "site": site,
        "device": device,
        "admin": admin,
        "tech": tech,
        "nonmember": nonmember,
    }


def _make_plan(db, device_id, *, action="restart", params=None, status="approved"):
    """Create a plan (default: single approved step) via the repository."""
    proposals = [ActionProposal(action, device_id, params or {}, "why", "T2", True)]
    return AIActionRepository(db).create_plan(
        proposals,
        risk_tier="T2",
        reversible=True,
        created_by="ai@exec.test",
        status=status,
    )


def _queue_plan(db, device_id, *, action="restart", params=None):
    """Create an approved plan and execute it into the fake queue."""
    plan = _make_plan(db, device_id, action=action, params=params)
    fake = FakeCommandService()
    plan, _ = asyncio.run(start_execution(db, plan, "t", db_service=fake))
    return plan, fake


def _headers(email):
    """Build an Authorization header for the given user."""
    return {"Authorization": f"Bearer {create_access_token({'sub': email})}"}


# --------------------------------------------------------------------------
# Policy engine
# --------------------------------------------------------------------------


def test_policy_allows_active_device_with_permission():
    """An active device that granted root_access passes policy."""
    db = homepot.database.SessionLocal()
    try:
        _seed(db)
        result = evaluate_plan(db, _make_plan(db, "POS-A"))
        assert result.allowed
        assert result.reasons == []
    finally:
        db.close()


def test_policy_blocks_inactive_device():
    """A non-active device is refused."""
    db = homepot.database.SessionLocal()
    try:
        _seed(db, lifecycle=LifecycleState.SUSPENDED.value)
        result = evaluate_plan(db, _make_plan(db, "POS-A"))
        assert not result.allowed
        assert any("not active" in reason for reason in result.reasons)
    finally:
        db.close()


def test_policy_blocks_missing_permission():
    """A device without the action's permission is refused."""
    db = homepot.database.SessionLocal()
    try:
        seed = _seed(db)
        seed["device"].device_permissions = {"root_access": False}
        db.commit()
        result = evaluate_plan(db, _make_plan(db, "POS-A"))
        assert not result.allowed
        assert any("root_access" in reason for reason in result.reasons)
    finally:
        db.close()


def test_policy_blocks_unknown_action():
    """An action not declared in the registry is refused."""
    db = homepot.database.SessionLocal()
    try:
        _seed(db)
        plan = _make_plan(db, "POS-A")
        plan.steps[0].action = "rm_rf"
        db.commit()
        result = evaluate_plan(db, plan)
        assert not result.allowed
        assert any("Unknown action" in reason for reason in result.reasons)
    finally:
        db.close()


def test_policy_enforces_blast_radius():
    """A plan exceeding the device limit is refused."""
    db = homepot.database.SessionLocal()
    try:
        _seed(db)
        result = evaluate_plan(db, _make_plan(db, "POS-A"), max_devices=0)
        assert not result.allowed
        assert any("blast-radius" in reason for reason in result.reasons)
    finally:
        db.close()


# --------------------------------------------------------------------------
# Executor
# --------------------------------------------------------------------------


def test_start_execution_queues_commands():
    """Each step becomes one queued device command."""
    db = homepot.database.SessionLocal()
    try:
        _seed(db)
        plan, fake = _queue_plan(db, "POS-A")
        assert plan.status == "executing"
        assert plan.steps[0].status == "queued"
        assert plan.steps[0].command_id == "cmd-1"
        assert fake.created[0].command_type == "restart"
        assert fake.created[0].issued_by == "ai:t"
        assert fake.created[0].payload is None
    finally:
        db.close()


def test_start_execution_snapshots_config_for_rollback():
    """update_config captures the prior value and wraps the payload."""
    db = homepot.database.SessionLocal()
    try:
        _seed(db, config={"brightness": 10, "volume": 5})
        plan, fake = _queue_plan(
            db, "POS-A", action="update_config", params={"config": {"brightness": 80}}
        )
        assert plan.steps[0].rollback_params == {"previous": {"brightness": 10}}
        assert fake.created[0].payload == {"data": {"brightness": 80}}
    finally:
        db.close()


def test_start_execution_blocked_leaves_nothing_queued():
    """A policy block records status=blocked and queues nothing."""
    db = homepot.database.SessionLocal()
    try:
        _seed(db, lifecycle=LifecycleState.SUSPENDED.value)
        plan = _make_plan(db, "POS-A")
        fake = FakeCommandService()
        plan, policy = asyncio.run(start_execution(db, plan, "t", db_service=fake))
        assert not policy.allowed
        assert plan.status == "blocked"
        assert fake.created == []
        assert plan.steps[0].status == "pending"
    finally:
        db.close()


# --------------------------------------------------------------------------
# Verifier / rollback
# --------------------------------------------------------------------------


def test_reconcile_completes_successfully():
    """All commands completing marks the plan succeeded with an outcome."""
    db = homepot.database.SessionLocal()
    try:
        _seed(db, config={"brightness": 10})
        plan, fake = _queue_plan(
            db, "POS-A", action="update_config", params={"config": {"brightness": 80}}
        )
        fake.commands[plan.steps[0].command_id].status = "completed"

        status = asyncio.run(reconcile_plan(db, plan, db_service=fake))

        assert status == "succeeded"
        assert plan.steps[0].status == "done"
        assert plan.outcome is not None
        assert plan.outcome.verified is True
        assert plan.outcome.rolled_back is False
    finally:
        db.close()


def test_reconcile_is_idempotent_after_terminal():
    """Reconciling a finished plan leaves it unchanged."""
    db = homepot.database.SessionLocal()
    try:
        _seed(db, config={"brightness": 10})
        plan, fake = _queue_plan(
            db, "POS-A", action="update_config", params={"config": {"brightness": 80}}
        )
        fake.commands[plan.steps[0].command_id].status = "completed"
        asyncio.run(reconcile_plan(db, plan, db_service=fake))
        assert asyncio.run(reconcile_plan(db, plan, db_service=fake)) == "succeeded"
    finally:
        db.close()


def test_reconcile_per_key_failure_triggers_rollback():
    """A completed command with a failed key rolls the config back."""
    db = homepot.database.SessionLocal()
    try:
        _seed(db, config={"brightness": 10})
        plan, fake = _queue_plan(
            db, "POS-A", action="update_config", params={"config": {"brightness": 80}}
        )
        command = fake.commands[plan.steps[0].command_id]
        command.status = "completed"
        command.result = {
            "status": "completed",
            "result": {"results": {"brightness": {"status": "failed"}}},
        }

        assert asyncio.run(reconcile_plan(db, plan, db_service=fake)) == "rolling_back"
        rollback = [c for c in fake.created if c.issued_by == "ai:rollback"]
        assert rollback and rollback[0].payload == {"data": {"brightness": 10}}

        rollback[0].status = "completed"
        assert asyncio.run(reconcile_plan(db, plan, db_service=fake)) == "rolled_back"
        assert plan.outcome.rolled_back is True
        assert plan.outcome.rollback_success is True
    finally:
        db.close()


def test_reconcile_hard_failure_without_rollback_fails():
    """A failed unrestartable step with nothing to undo fails the plan."""
    db = homepot.database.SessionLocal()
    try:
        _seed(db)
        plan, fake = _queue_plan(db, "POS-A", action="restart")
        fake.commands[plan.steps[0].command_id].status = "failed"

        assert asyncio.run(reconcile_plan(db, plan, db_service=fake)) == "failed"
        assert plan.outcome.verified is False
        assert plan.outcome.rolled_back is False
    finally:
        db.close()


def test_reconcile_rollback_command_failure_marks_failed():
    """A failed rollback command ends the plan as failed."""
    db = homepot.database.SessionLocal()
    try:
        _seed(db, config={"brightness": 10})
        plan, fake = _queue_plan(
            db, "POS-A", action="update_config", params={"config": {"brightness": 80}}
        )
        fake.commands[plan.steps[0].command_id].status = "failed"
        asyncio.run(reconcile_plan(db, plan, db_service=fake))

        rollback = [c for c in fake.created if c.issued_by == "ai:rollback"][0]
        rollback.status = "failed"
        assert asyncio.run(reconcile_plan(db, plan, db_service=fake)) == "failed"
        assert plan.outcome.rollback_success is False
    finally:
        db.close()


def test_reconcile_records_single_outcome():
    """A terminal plan carries exactly one outcome row."""
    db = homepot.database.SessionLocal()
    try:
        _seed(db, config={"brightness": 10})
        plan, fake = _queue_plan(
            db, "POS-A", action="update_config", params={"config": {"brightness": 80}}
        )
        fake.commands[plan.steps[0].command_id].status = "completed"
        asyncio.run(reconcile_plan(db, plan, db_service=fake))
        asyncio.run(reconcile_plan(db, plan, db_service=fake))

        rows = (
            db.query(AIActionOutcome)
            .filter(AIActionOutcome.plan_id == plan.plan_id)
            .all()
        )
        assert len(rows) == 1
    finally:
        db.close()


# --------------------------------------------------------------------------
# Execute endpoint
# --------------------------------------------------------------------------


def test_execute_requires_approval(client: TestClient):
    """A plan that is not approved cannot execute."""
    db = homepot.database.SessionLocal()
    try:
        seed = _seed(db)
        plan = _make_plan(db, "POS-A", status="pending_approval")
        plan_id, tech_email = plan.plan_id, seed["tech"].email
    finally:
        db.close()

    resp = client.post(
        f"/api/v1/ai/action-plans/{plan_id}/execute", headers=_headers(tech_email)
    )
    assert resp.status_code == 409


def test_execute_approved_plan_queues_commands(client: TestClient):
    """Executing an approved plan returns executing and queues a command."""
    db = homepot.database.SessionLocal()
    try:
        seed = _seed(db)
        plan = _make_plan(db, "POS-A")
        plan_id, tech_email = plan.plan_id, seed["tech"].email
    finally:
        db.close()

    resp = client.post(
        f"/api/v1/ai/action-plans/{plan_id}/execute", headers=_headers(tech_email)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "executing"
    assert body["policy"]["allowed"] is True
    assert body["steps"][0]["status"] == "queued"
    assert body["outcome"] is None

    check = homepot.database.SessionLocal()
    try:
        stored = AIActionRepository(check).get_plan(plan_id)
        assert stored is not None
        assert stored.status == "executing"
    finally:
        check.close()


def test_execute_blocked_plan_returns_blocked_status(client: TestClient):
    """An approved plan that fails policy is blocked, not executed."""
    db = homepot.database.SessionLocal()
    try:
        seed = _seed(db, lifecycle=LifecycleState.SUSPENDED.value)
        plan = _make_plan(db, "POS-A")
        plan_id, tech_email = plan.plan_id, seed["tech"].email
    finally:
        db.close()

    resp = client.post(
        f"/api/v1/ai/action-plans/{plan_id}/execute", headers=_headers(tech_email)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "blocked"
    assert body["policy"]["allowed"] is False


def test_execute_non_member_is_forbidden(client: TestClient):
    """A caller outside the device's site cannot execute the plan."""
    db = homepot.database.SessionLocal()
    try:
        seed = _seed(db)
        plan = _make_plan(db, "POS-A")
        plan_id, outsider_email = plan.plan_id, seed["nonmember"].email
    finally:
        db.close()

    resp = client.post(
        f"/api/v1/ai/action-plans/{plan_id}/execute", headers=_headers(outsider_email)
    )
    assert resp.status_code in (403, 404)


def test_execute_unknown_plan_is_404(client: TestClient):
    """Executing a non-existent plan returns 404."""
    db = homepot.database.SessionLocal()
    try:
        admin_email = _seed(db)["admin"].email
    finally:
        db.close()

    resp = client.post(
        "/api/v1/ai/action-plans/nope/execute", headers=_headers(admin_email)
    )
    assert resp.status_code == 404
