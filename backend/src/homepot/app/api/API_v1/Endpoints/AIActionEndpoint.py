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
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.orm import Session as SASession

from homepot.app.ai_ops.executor import dispatch_ready_steps, start_execution
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
                "step_id": step.step_id,
                "seq": step.seq,
                "action": step.action,
                "target_device_id": step.target_device_id,
                "params": step.params,
                "status": step.status,
                "depends_on_step_id": getattr(step, "depends_on_step_id", None),
                "result": getattr(step, "result", None),
                "error": getattr(step, "error", None),
                "started_at": (
                    step.started_at.isoformat()
                    if getattr(step, "started_at", None)
                    else None
                ),
                "completed_at": (
                    step.completed_at.isoformat()
                    if getattr(step, "completed_at", None)
                    else None
                ),
                "approval_required": getattr(step, "approval_required", False),
                "command_id": getattr(step, "command_id", None),
                "retry_count": getattr(step, "retry_count", 0),
                "max_retries": getattr(step, "max_retries", 3),
                "next_retry_at": (
                    step.next_retry_at.isoformat()
                    if getattr(step, "next_retry_at", None)
                    else None
                ),
                "last_error": getattr(step, "last_error", None),
                "idempotency_key": getattr(step, "idempotency_key", None),
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
        "outcome": (
            {
                "verified": plan.outcome.verified,
                "rolled_back": plan.outcome.rolled_back,
                "rollback_success": plan.outcome.rollback_success,
                "error": plan.outcome.error,
                "recorded_at": (
                    plan.outcome.recorded_at.isoformat()
                    if plan.outcome.recorded_at
                    else None
                ),
                "provenance": plan.outcome.provenance,
            }
            if plan.outcome is not None
            else None
        ),
    }


@router.get("/action-plans/summary", tags=["AI Action Delegation"])
async def get_action_plan_summary(
    days: int = 30,
    created_by: Optional[str] = None,
    current_user: UserDict = Depends(require_user()),
    db: SASession = Depends(get_db),
) -> Dict[str, Any]:
    """Return cross-session task aggregation (counts by status + recent plans)."""
    db_user = _get_db_user(db, current_user)
    repo = AIActionRepository(db)

    accessible = None
    if not db_user.is_admin:
        accessible = _accessible_device_ids(db, db_user)

    return repo.plan_summary(
        accessible_device_ids=accessible,
        created_by=created_by,
        days=days,
    )


@router.get("/reliability", tags=["AI Action Delegation"])
async def get_ai_reliability(
    days: int = 30,
    action_type: Optional[str] = None,
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Return per-action-type reliability metrics for AI delegation."""
    from ai.analytics_service import AIAnalyticsService

    return await AIAnalyticsService.get_ai_action_reliability(
        action_type=action_type, days=days
    )


@router.get("/autonomy", tags=["AI Action Delegation"])
async def get_autonomy_levels(
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Return current autonomy levels for all action types."""
    from homepot.app.ai_ops.autonomy import (
        hydrate_autonomy_from_reliability,
    )

    # Hydrate from measured reliability so the report reflects real outcomes
    # instead of an empty in-memory singleton.
    controller = await hydrate_autonomy_from_reliability(days=30)
    levels = controller.all_levels()
    return {
        action_type: {
            "level": level.level,
            "sample_count": level.sample_count,
            "success_rate": level.success_rate,
            "rollback_proven": level.rollback_proven,
            "last_updated": level.last_updated,
        }
        for action_type, level in levels.items()
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
    session_id: Optional[str] = Query(
        None, description="Filter by investigation session id"
    ),
    run_id: Optional[str] = Query(None, description="Filter by investigation run id"),
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
        session_id=session_id,
        run_id=run_id,
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


async def _log_step_approval(
    current_user: UserDict,
    plan: AIActionPlan,
    step: Any,
    targets: List[str],
    reason: Optional[str],
) -> None:
    """Best-effort audit of a per-step approval; never breaks the request."""
    try:
        audit = get_audit_logger()
        await audit.log_event(
            event_type=AuditEventType.AI_STEP_APPROVED,
            description=(
                f"AI step approved | plan={plan.plan_id} | step={step.step_id} | "
                f"action={step.action} | device={step.target_device_id}"
            ),
            user_id=current_user.get("user_id"),
            event_metadata={
                "plan_id": plan.plan_id,
                "step_id": step.step_id,
                "action": step.action,
                "target_device_id": step.target_device_id,
                "risk_tier": plan.risk_tier,
                "target_devices": targets,
                "actor": current_user.get("email"),
                "reason": reason,
            },
        )
    except Exception:
        logger.warning("Failed to audit AI step approval", exc_info=True)


@router.post(
    "/action-plans/{plan_id}/steps/{step_id}/approve",
    tags=["AI Action Delegation"],
)
async def approve_action_step(
    plan_id: str,
    step_id: str,
    payload: DecisionRequest,
    current_user: UserDict = Depends(require_user()),
    db: SASession = Depends(get_db),
) -> Dict[str, Any]:
    """Approve one step that carries its own human gate (Phase A item 4).

    Steps the plan marked ``approval_required`` (disruptive actions by default)
    pause after plan approval until an operator releases them individually.
    Approving while the plan is executing re-dispatches the step immediately
    when its dependencies are complete; approving before execution simply
    pre-clears the gate.
    """
    db_user = _get_db_user(db, current_user)
    repo = AIActionRepository(db)
    plan = repo.get_plan(plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found"
        )

    # Scope first, so a caller outside the step's site cannot act on it.
    targets = _authorize_plan(db, db_user, plan)

    step = next((s for s in plan.steps if s.step_id == step_id), None)
    if step is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Step not found"
        )

    if not getattr(step, "approval_required", False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Step does not require per-step approval",
        )
    if plan.status not in ("approved", "executing"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Plan is '{plan.status}' and its steps can no longer be "
                "approved (only 'approved' or 'executing' plans)"
            ),
        )
    if step.status in ("done", "queued", "running", "failed", "skipped"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Step is '{step.status}' and can no longer be approved",
        )

    if step.status != "approved":
        step.status = "approved"
        step.error = None
        db.commit()

    await _log_step_approval(current_user, plan, step, targets, payload.reason)

    if plan.status == "executing":
        # Release the step now rather than waiting for the next reconcile tick.
        try:
            await dispatch_ready_steps(db, plan, str(current_user.get("email")))
        except Exception:
            logger.warning(
                "Step approved but immediate dispatch failed; reconcile will retry",
                exc_info=True,
            )

    db.refresh(plan)
    logger.info(
        "AI step approved | plan=%s | step=%s | actor=%s",
        plan.plan_id,
        step.step_id,
        current_user.get("email"),
    )
    return _serialize_plan(plan)


@router.post("/action-plans/{plan_id}/cancel", tags=["AI Action Delegation"])
async def cancel_action_plan(
    plan_id: str,
    current_user: UserDict = Depends(require_user()),
    db: SASession = Depends(get_db),
) -> Dict[str, Any]:
    """Cancel an executing AI action plan.

    Moves an ``executing`` plan to ``cancelled`` and prevents further step
    dispatch. Already-queued commands are not recalled, but their results will
    be ignored by the reconcile loop.
    """
    db_user = _get_db_user(db, current_user)
    repo = AIActionRepository(db)
    plan = repo.get_plan(plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found"
        )

    targets = _authorize_plan(db, db_user, plan)

    if plan.status not in ("executing", "approved", "pending_approval"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Plan is '{plan.status}' and cannot be cancelled "
                "(only executing/approved/pending plans cancel)"
            ),
        )

    plan.status = "cancelled"  # type: ignore[assignment]
    db.commit()

    logger.info(
        "AI plan cancelled | plan=%s | actor=%s | devices=%s",
        plan.plan_id,
        current_user.get("email"),
        targets,
    )
    return _serialize_plan(plan)


@router.post("/action-plans/{plan_id}/dry-run", tags=["AI Action Delegation"])
async def dry_run_action_plan(
    plan_id: str,
    current_user: UserDict = Depends(require_user()),
    db: SASession = Depends(get_db),
) -> Dict[str, Any]:
    """Dry-run an AI action plan (non-destructive preview).

    Re-runs policy checks and computes predicted outcomes for each step
    without queueing any commands. Returns policy reasons and per-step
    predicted changes.
    """
    db_user = _get_db_user(db, current_user)
    repo = AIActionRepository(db)
    plan = repo.get_plan(plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found"
        )

    _authorize_plan(db, db_user, plan)

    from homepot.app.ai_ops.executor import applied_config
    from homepot.app.ai_ops.policy import evaluate_plan, evaluate_step

    policy = evaluate_plan(db, plan)

    step_previews = []
    for step in plan.steps:
        step_policy = evaluate_step(db, step, plan=plan)
        preview: Dict[str, Any] = {
            "seq": step.seq,
            "action": step.action,
            "target_device_id": step.target_device_id,
            "policy_allowed": step_policy.allowed,
            "policy_reasons": step_policy.reasons,
        }
        # Compute predicted change
        if step.action in ("update_config", "rollback_config"):
            config = applied_config(step)
            preview["predicted_change"] = {
                "config_keys": list(config.keys()),
                "values": config,
            }
        elif step.action == "restart":
            preview["predicted_change"] = {"action": "device restart"}
        elif step.action == "restart_service":
            params = step.params or {}
            preview["predicted_change"] = {
                "action": f"restart service: {params.get('service_name', 'unknown')}"
            }
        elif step.action in ("health_check", "list_processes", "scan_filesystem"):
            preview["predicted_change"] = {"action": f"read-only: {step.action}"}
        else:
            preview["predicted_change"] = {"action": step.action}

        step_previews.append(preview)

    return {
        "plan_id": plan.plan_id,
        "policy": {"allowed": policy.allowed, "reasons": policy.reasons},
        "steps": step_previews,
        "dry_run": True,
    }


async def _log_execution(
    current_user: UserDict,
    plan: AIActionPlan,
    event_type: AuditEventType,
    targets: List[str],
) -> None:
    """Best-effort audit of an execution transition; never breaks the request."""
    try:
        await get_audit_logger().log_event(
            event_type=event_type,
            description=(
                f"AI plan {plan.status} | plan={plan.plan_id} | "
                f"risk={plan.risk_tier} | devices={','.join(targets) or 'N/A'}"
            ),
            user_id=current_user.get("user_id"),
            event_metadata={
                "plan_id": plan.plan_id,
                "status": plan.status,
                "risk_tier": plan.risk_tier,
                "reversible": plan.reversible,
                "target_devices": targets,
                "actor": current_user.get("email"),
            },
        )
    except Exception:
        logger.warning("Failed to audit AI plan execution", exc_info=True)


@router.post("/action-plans/{plan_id}/execute", tags=["AI Action Delegation"])
async def execute_action_plan(
    plan_id: str,
    current_user: UserDict = Depends(require_user()),
    db: SASession = Depends(get_db),
) -> Dict[str, Any]:
    """Execute an *approved* AI action plan (Phase 3).

    Policy is re-checked against live data, then one device command is queued
    per step through the same command path the operator UI uses. Completion is
    asynchronous: the plan moves to ``executing`` and the verifier finalises it
    once the device reports back. Nothing executes without a prior approval.
    """
    db_user = _get_db_user(db, current_user)
    repo = AIActionRepository(db)
    plan = repo.get_plan(plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found"
        )

    # Scope first, so a caller outside the device's site cannot trigger it.
    targets = _authorize_plan(db, db_user, plan)

    # Atomically claim the plan so two concurrent requests cannot both execute.
    # Run off the event loop: a blocking write here can wait on a SQLite lock
    # held by a detached async writer (e.g. analytics) that needs this loop to
    # commit, which would otherwise deadlock until the busy timeout.
    if not await run_in_threadpool(repo.claim_for_execution, str(plan.plan_id)):
        db.refresh(plan)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Plan is '{plan.status}' and cannot be executed "
                "(only 'approved' plans execute)"
            ),
        )
    db.refresh(plan)

    plan, policy = await start_execution(db, plan, actor=str(current_user.get("email")))

    if not policy.allowed:
        await _log_execution(
            current_user, plan, AuditEventType.AI_EXECUTION_BLOCKED, targets
        )
    else:
        await _log_execution(
            current_user, plan, AuditEventType.AI_EXECUTION_STARTED, targets
        )

    logger.info(
        "AI plan execute | plan=%s | status=%s | actor=%s | devices=%s",
        plan.plan_id,
        plan.status,
        current_user.get("email"),
        targets,
    )
    result = _serialize_plan(plan)
    result["policy"] = {"allowed": policy.allowed, "reasons": policy.reasons}
    return result
