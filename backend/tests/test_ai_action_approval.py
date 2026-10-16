"""Tests for the Phase 2 AI action-delegation approval API.

Covers listing/scope filtering, detail scoping, approve/reject transitions,
RBAC (membership + role), and the double-decision guard. No execution happens
in Phase 2.
"""

import asyncio
from datetime import datetime, timezone
import os
import sys
import tempfile

current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from ai.actions import ActionProposal  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from homepot.app.auth_utils import create_access_token, hash_password  # noqa: E402
from homepot.app.models.AnalyticsModel import (  # noqa: E402
    AIActionApproval,
    AIActionPlan,
)
from homepot.app.repositories import ai_action_repository  # noqa: E402
from homepot.config import reload_settings  # noqa: E402
import homepot.database  # noqa: E402
from homepot.models import Base, Device, Site, SiteMembership, User  # noqa: E402


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
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed(db):
    """Create two sites/devices, an admin, a member tech and a non-member tech."""
    site_a = Site(site_id="site-a", name="Site A", location="Lab A")
    site_b = Site(site_id="site-b", name="Site B", location="Lab B")
    db.add_all([site_a, site_b])
    db.commit()
    db.refresh(site_a)
    db.refresh(site_b)

    dev_a = Device(
        device_id="POS-A",
        name="POS A",
        device_type="pos_terminal",
        site_id=site_a.id,
    )
    dev_b = Device(
        device_id="POS-B",
        name="POS B",
        device_type="pos_terminal",
        site_id=site_b.id,
    )
    db.add_all([dev_a, dev_b])

    admin = _make_user(db, "admin@deleg.test", is_admin=True)
    tech_a = _make_user(db, "tech-a@deleg.test")
    tech_none = _make_user(db, "tech-none@deleg.test")
    db.add(SiteMembership(user_id=tech_a.id, site_id=site_a.id, role="operator"))
    db.commit()
    return {
        "site_a": site_a,
        "site_b": site_b,
        "admin": admin,
        "tech_a": tech_a,
        "tech_none": tech_none,
    }


def _make_plan(db, device_id, *, created_by="ai@deleg.test"):
    proposals = [
        ActionProposal("restart", device_id, {}, "device unresponsive", "T2", True)
    ]
    return ai_action_repository.AIActionRepository(db).create_plan(
        proposals,
        risk_tier="T2",
        reversible=True,
        created_by=created_by,
        status="pending_approval",
    )


def _headers(email):
    return {"Authorization": f"Bearer {create_access_token({'sub': email})}"}


def test_list_is_scoped_to_member_devices(client: TestClient):
    """A technician only sees plans for devices in their sites."""
    db = homepot.database.SessionLocal()
    try:
        seed = _seed(db)
        plan_a = _make_plan(db, "POS-A")
        plan_b = _make_plan(db, "POS-B")
        plan_a_id, plan_b_id = plan_a.plan_id, plan_b.plan_id
        admin_email, tech_a_email = seed["admin"].email, seed["tech_a"].email
    finally:
        db.close()

    # Technician: only site A.
    resp = client.get("/api/v1/ai/action-plans", headers=_headers(tech_a_email))
    assert resp.status_code == 200
    ids = {p["plan_id"] for p in resp.json()["plans"]}
    assert ids == {plan_a_id}

    # Admin: everything.
    resp = client.get("/api/v1/ai/action-plans", headers=_headers(admin_email))
    assert resp.status_code == 200
    ids = {p["plan_id"] for p in resp.json()["plans"]}
    assert {plan_a_id, plan_b_id}.issubset(ids)


def test_detail_is_scoped(client: TestClient):
    """A non-member cannot see a plan for a device outside their scope."""
    db = homepot.database.SessionLocal()
    try:
        seed = _seed(db)
        plan_a = _make_plan(db, "POS-A")
        plan_a_id = plan_a.plan_id
        tech_a_email = seed["tech_a"].email
        tech_none_email = seed["tech_none"].email
        admin_email = seed["admin"].email
    finally:
        db.close()

    assert (
        client.get(
            f"/api/v1/ai/action-plans/{plan_a_id}", headers=_headers(tech_a_email)
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/ai/action-plans/{plan_a_id}", headers=_headers(tech_none_email)
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/ai/action-plans/{plan_a_id}", headers=_headers(admin_email)
        ).status_code
        == 200
    )


def test_member_can_approve_and_it_is_recorded(client: TestClient):
    """Approval transitions the plan and records actor + scope."""
    db = homepot.database.SessionLocal()
    try:
        seed = _seed(db)
        plan_id = _make_plan(db, "POS-A").plan_id
        tech_a_email = seed["tech_a"].email
    finally:
        db.close()

    resp = client.post(
        f"/api/v1/ai/action-plans/{plan_id}/approve",
        json={"reason": "looks right"},
        headers=_headers(tech_a_email),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "approved"
    assert body["steps"][0]["target_device_id"] == "POS-A"

    db = homepot.database.SessionLocal()
    try:
        plan = db.execute(
            select(AIActionPlan).where(AIActionPlan.plan_id == plan_id)
        ).scalar_one()
        assert plan.status == "approved"
        approvals = (
            db.execute(
                select(AIActionApproval).where(AIActionApproval.plan_id == plan_id)
            )
            .scalars()
            .all()
        )
        assert len(approvals) == 1
        assert approvals[0].decision == "approved"
        assert approvals[0].actor == tech_a_email
        assert approvals[0].device_scope == ["POS-A"]
    finally:
        db.close()


def test_member_can_reject_with_reason(client: TestClient):
    """Rejection records the decision and reason."""
    db = homepot.database.SessionLocal()
    try:
        seed = _seed(db)
        plan_id = _make_plan(db, "POS-A").plan_id
        tech_a_email = seed["tech_a"].email
    finally:
        db.close()

    resp = client.post(
        f"/api/v1/ai/action-plans/{plan_id}/reject",
        json={"reason": "not now"},
        headers=_headers(tech_a_email),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"

    db = homepot.database.SessionLocal()
    try:
        approval = db.execute(
            select(AIActionApproval).where(AIActionApproval.plan_id == plan_id)
        ).scalar_one()
        assert approval.decision == "rejected"
        assert approval.reason == "not now"
    finally:
        db.close()


def test_non_member_cannot_decide(client: TestClient):
    """A technician outside the device's site is forbidden."""
    db = homepot.database.SessionLocal()
    try:
        seed = _seed(db)
        plan_id = _make_plan(db, "POS-A").plan_id
        tech_none_email = seed["tech_none"].email
    finally:
        db.close()

    resp = client.post(
        f"/api/v1/ai/action-plans/{plan_id}/approve",
        json={},
        headers=_headers(tech_none_email),
    )
    assert resp.status_code == 403

    db = homepot.database.SessionLocal()
    try:
        plan = db.execute(
            select(AIActionPlan).where(AIActionPlan.plan_id == plan_id)
        ).scalar_one()
        assert plan.status == "pending_approval"  # unchanged
    finally:
        db.close()


def test_double_decision_is_conflict(client: TestClient):
    """A plan can only be decided while pending_approval."""
    db = homepot.database.SessionLocal()
    try:
        seed = _seed(db)
        plan_id = _make_plan(db, "POS-A").plan_id
        tech_a_email = seed["tech_a"].email
    finally:
        db.close()

    first = client.post(
        f"/api/v1/ai/action-plans/{plan_id}/approve",
        json={},
        headers=_headers(tech_a_email),
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/v1/ai/action-plans/{plan_id}/reject",
        json={},
        headers=_headers(tech_a_email),
    )
    assert second.status_code == 409

    db = homepot.database.SessionLocal()
    try:
        approvals = (
            db.execute(
                select(AIActionApproval).where(AIActionApproval.plan_id == plan_id)
            )
            .scalars()
            .all()
        )
        assert len(approvals) == 1  # the rejected attempt was not recorded
    finally:
        db.close()


def test_unknown_plan_is_404(client: TestClient):
    """Deciding on a non-existent plan returns 404."""
    db = homepot.database.SessionLocal()
    try:
        seed = _seed(db)
        admin_email = seed["admin"].email
    finally:
        db.close()

    resp = client.post(
        "/api/v1/ai/action-plans/does-not-exist/approve",
        json={},
        headers=_headers(admin_email),
    )
    assert resp.status_code == 404
