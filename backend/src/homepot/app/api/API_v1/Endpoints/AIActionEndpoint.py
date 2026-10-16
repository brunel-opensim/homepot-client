"""AI action-delegation approval endpoints (Phase 2).

Technicians review AI-proposed action plans and approve or reject them. This is
the human-in-the-loop gate: **no action is executed here** (execution is
Phase 3). Every decision is audited with its actor and device scope.

Scoping: an approval is a privileged action, so it is role- and scope-checked
with ``verify_device_belongs_to_user(..., minimum_role="operator")`` (admins
bypass), not a bare admin check. Lists are filtered to the caller's accessible
devices.

See docs/ai-delegation-plan.md sections 6 (state machine), 10 (approval & RBAC)
and 11 (explainability).
"""

import logging
from typing import Any, Dict, List, Optional, Set, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as SASession

from homepot.app.auth_utils import (
    get_accessible_site_ids,
    require_user,
    verify_device_belongs_to_user,
)
from homepot.app.models.AnalyticsModel import AIActionPlan
from homepot.app.repositories.ai_action_repository import AIActionRepository
from homepot.app.schemas.schemas import UserDict
from homepot.audit import AuditEventType, get_audit_logger
from homepot.database import get_db
from homepot.models import Device, User

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_user())])

# Statuses a technician may still act on. Everything else is terminal.
REVIEWABLE_STATUSES: Set[str] = {"pending_approval"}


class DecisionRequest(BaseModel):
    """Body for an approve/reject decision."""

    reason: Optional[str] = None


def _serialize_plan(plan: AIActionPlan) -> Dict[str, Any]:
    """Serialize a plan (with steps, approvals and trust) for the API."""
    return {
        "plan_id": plan.plan_id,
        "status": plan.status,
        "risk_tier": plan.risk_tier,
        "reversible": plan.reversible,
        "rationale": plan.rationale,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "created_by": plan.created_by,
        "provenance": plan.provenance,
        "trust": {
            "mode": plan.trust_mode,
            "score": plan.trust_score,
            "passed_gates": plan.passed_gates,
            "failed_gate": plan.failed_gate,
        },
        "evidence": plan.evidence,
        "steps": [
            {
                "seq": step.seq,
                "action": step.action,
                "target_device_id": step.target_device_id,
                "params": step.params,
                "status": step.status,
            }
            for step in plan.steps
        ],
        "approvals": [
            {
                "actor": approval.actor,
                "decision": approval.decision,
                "reason": approval.reason,
                "decided_at": (
                    approval.decided_at.isoformat() if approval.decided_at else None
                ),
            }
            for approval in plan.approvals
        ],
    }


def _get_db_user(db: SASession, current_user: UserDict) -> User:
    """Load the ORM user for the authenticated caller."""
    db_user = cast(
        User, db.query(User).filter(User.email == current_user["email"]).first()
    )
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User not found"
        )
    return db_user


def _accessible_device_ids(db: SASession, db_user: User) -> Optional[List[str]]:
    """Return business device_ids the user can access, or ``None`` for admins."""
    site_pks = get_accessible_site_ids(db_user, db)
    return AIActionRepository(db).accessible_device_ids(site_pks)


def _plan_targets(plan: AIActionPlan) -> List[str]:
    """Return distinct device_ids targeted by a plan's steps (order preserved)."""
    targets: List[str] = []
    seen: Set[str] = set()
    for step in plan.steps:
        device_id = step.target_device_id
        if not device_id or device_id in seen:
            continue
        seen.add(device_id)
        targets.append(device_id)
    return targets


def _authorize_plan(db: SASession, db_user: User, plan: AIActionPlan) -> List[str]:
    """Verify operator access to every targeted device; return the targets."""
    targets = _plan_targets(plan)
    for device_id in targets:
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if device is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target device not found: {device_id}",
            )
        verify_device_belongs_to_user(db_user, device, db, minimum_role="operator")
    return targets


@router.get("/action-plans", tags=["AI Action Delegation"])
async def list_action_plans(
    plan_status: Optional[str] = Query(
        None, alias="status", description="Filter by plan status"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: UserDict = Depends(require_user()),
    db: SASession = Depends(get_db),
) -> Dict[str, Any]:
    """List AI action plans, newest first, scoped to the caller's devices."""
    db_user = _get_db_user(db, current_user)
    repo = AIActionRepository(db)
    plans = repo.list_plans(
        statuses={plan_status} if plan_status else None,
        accessible_device_ids=_accessible_device_ids(db, db_user),
        limit=limit,
        offset=offset,
    )
    return {
        "plans": [_serialize_plan(plan) for plan in plans],
        "count": len(plans),
    }


@router.get("/action-plans/{plan_id}", tags=["AI Action Delegation"])
async def get_action_plan(
    plan_id: str,
    current_user: UserDict = Depends(require_user()),
    db: SASession = Depends(get_db),
) -> Dict[str, Any]:
    """Return a single plan if it is within the caller's device scope."""
    db_user = _get_db_user(db, current_user)
    plan = AIActionRepository(db).get_plan(plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found"
        )

    accessible = _accessible_device_ids(db, db_user)
    if accessible is not None:
        targets = set(_plan_targets(plan))
        if not targets or not targets.issubset(set(accessible)):
            # Do not reveal plans for devices outside the caller's scope.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found"
            )

    return _serialize_plan(plan)


async def _log_decision(
    current_user: UserDict,
    plan: AIActionPlan,
    event_type: AuditEventType,
    targets: List[str],
) -> None:
    """Best-effort audit of an approval decision; never breaks the request."""
    try:
        audit = get_audit_logger()
        await audit.log_event(
            event_type=event_type,
            description=(
                f"AI proposal {plan.status} | plan={plan.plan_id} | "
                f"risk={plan.risk_tier} | devices={','.join(targets) or 'N/A'}"
            ),
            user_id=current_user.get("user_id"),
            event_metadata={
                "plan_id": plan.plan_id,
                "decision": plan.status,
                "risk_tier": plan.risk_tier,
                "reversible": plan.reversible,
                "target_devices": targets,
                "actor": current_user.get("email"),
            },
        )
    except Exception:
        logger.warning("Failed to audit AI proposal decision", exc_info=True)


async def _decide(
    plan_id: str,
    decision: str,
    payload: DecisionRequest,
    current_user: UserDict,
    db: SASession,
) -> Dict[str, Any]:
    """Shared approve/reject path: scope-check, transition, audit."""
    db_user = _get_db_user(db, current_user)
    repo = AIActionRepository(db)
    plan = repo.get_plan(plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found"
        )

    # Scope first, so a caller outside the device's site cannot even learn the
    # plan state (and cannot act on it).
    targets = _authorize_plan(db, db_user, plan)

    if plan.status not in REVIEWABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Plan is '{plan.status}' and can no longer be "
                f"{decision[:6]}d (only {sorted(REVIEWABLE_STATUSES)} are reviewable)"
            ),
        )

    repo.record_decision(
        plan,
        actor=str(current_user.get("email")),
        decision=decision,
        reason=payload.reason,
        device_scope=targets,
    )

    event = (
        AuditEventType.AI_PROPOSAL_APPROVED
        if decision == "approved"
        else AuditEventType.AI_PROPOSAL_REJECTED
    )
    await _log_decision(current_user, plan, event, targets)

    logger.info(
        "AI proposal %s | plan=%s | actor=%s | devices=%s",
        decision,
        plan.plan_id,
        current_user.get("email"),
        targets,
    )
    return _serialize_plan(plan)


@router.post("/action-plans/{plan_id}/approve", tags=["AI Action Delegation"])
async def approve_action_plan(
    plan_id: str,
    payload: DecisionRequest,
    current_user: UserDict = Depends(require_user()),
    db: SASession = Depends(get_db),
) -> Dict[str, Any]:
    """Approve an AI action plan. Records the actor; does not execute."""
    return await _decide(plan_id, "approved", payload, current_user, db)


@router.post("/action-plans/{plan_id}/reject", tags=["AI Action Delegation"])
async def reject_action_plan(
    plan_id: str,
    payload: DecisionRequest,
    current_user: UserDict = Depends(require_user()),
    db: SASession = Depends(get_db),
) -> Dict[str, Any]:
    """Reject an AI action plan, recording the actor and reason."""
    return await _decide(plan_id, "rejected", payload, current_user, db)
