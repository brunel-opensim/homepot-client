"""Verification and reconciliation for AI action plans (Phase 3).

Execution is asynchronous: the executor queues commands, the device runs them
and reports back. This module is the deterministic state machine that advances
a plan once results arrive:

* ``executing`` — map each command's status onto its step; when every step is
  ``done`` the plan is ``succeeded``; when any step ``failed`` the plan moves to
  ``rolling_back`` (or ``failed`` when there is nothing to undo).
* ``rolling_back`` — check the inverse commands; when they finish the plan is
  ``rolled_back`` (success) or ``failed`` (a rollback command itself failed).

Every terminal plan gets exactly one :class:`AIActionOutcome` row: this is the
empirical evidence that later autonomy decisions are earned from.
"""

import logging
from typing import Any, Optional, cast

from sqlalchemy.orm import Session as SASession

from homepot.app.ai_ops.rollback import ROLLBACK_COMMAND_KEY, begin_rollback
from homepot.app.models.AnalyticsModel import AIActionOutcome
from homepot.database import get_database_service
from homepot.models import Device, derive_provenance

logger = logging.getLogger(__name__)

# Step statuses.
STEP_DONE = "done"
STEP_ROLLED_BACK = "rolled_back"

# Map a device command status onto its step status.
_COMMAND_TO_STEP = {
    "pending": "queued",
    "sent": "running",
    "completed": STEP_DONE,
    "failed": "failed",
    "expired": "failed",
    "cancelled": "failed",
}
_TERMINAL_FAILURE = {"failed", "expired", "cancelled"}


def _status_value(command: Any) -> Optional[str]:
    """Return a command's status as a plain string (or ``None``)."""
    if command is None:
        return None
    status = getattr(command, "status", None)
    return getattr(status, "value", status)


def command_failure(result: Any) -> Optional[str]:
    """Return an error string when a *completed* command shows per-key failure.

    The device reports ``{"status": "completed", "result": {...}}`` for
    ``update_config`` even when individual keys failed to apply, so success is
    not just the command status.
    """
    if not isinstance(result, dict):
        return None
    inner = result.get("result")
    inner = inner if isinstance(inner, dict) else result

    per_key = inner.get("results")
    if isinstance(per_key, dict):
        bad = [
            key
            for key, value in per_key.items()
            if isinstance(value, dict) and value.get("status") in ("failed", "error")
        ]
        if bad:
            return f"config key(s) failed: {', '.join(sorted(bad))}"

    error = inner.get("error")
    return str(error) if error else None


async def reconcile_plan(
    db: SASession,
    plan: Any,
    db_service: Any = None,
) -> str:
    """Advance a plan in ``executing``/``rolling_back``; return its new status.

    Idempotent and safe to call repeatedly (e.g. from the background loop).
    Plans in any other state are left untouched.
    """
    if plan.status == "executing":
        return await _reconcile_executing(db, plan, db_service)
    if plan.status == "rolling_back":
        return await _reconcile_rolling_back(db, plan, db_service)
    return cast(str, plan.status)


async def _reconcile_executing(db: SASession, plan: Any, db_service: Any = None) -> str:
    if db_service is None:
        db_service = await get_database_service()

    any_failed = False
    all_done = bool(plan.steps)

    for step in plan.steps:
        if not step.command_id:
            all_done = False
            continue
        command = await db_service.get_command(step.command_id)
        status = _status_value(command)
        if status is None:
            all_done = False
            continue

        step.status = _COMMAND_TO_STEP.get(status, step.status)
        if step.status == STEP_DONE:
            failure = command_failure(getattr(command, "result", None))
            if failure:
                step.status = "failed"

        if step.status == "failed":
            any_failed = True
        if step.status != STEP_DONE:
            all_done = False

    db.commit()

    if any_failed:
        plan.status = "rolling_back"
        db.commit()
        queued = await begin_rollback(db, plan, db_service)
        if not queued:
            _record_outcome(
                db, plan, verified=False, rolled_back=False, error="step failed"
            )
            plan.status = "failed"
            db.commit()
        return cast(str, plan.status)

    if all_done:
        _record_outcome(db, plan, verified=True, rolled_back=False)
        plan.status = "succeeded"
        db.commit()
    return cast(str, plan.status)


async def _reconcile_rolling_back(
    db: SASession, plan: Any, db_service: Any = None
) -> str:
    if db_service is None:
        db_service = await get_database_service()

    pending = False
    rollback_failed = False
    for step in plan.steps:
        rollback_id = (step.rollback_params or {}).get(ROLLBACK_COMMAND_KEY)
        if not rollback_id:
            continue
        command = await db_service.get_command(rollback_id)
        if command is None:
            pending = True
            continue
        status = _status_value(command)
        if status in _TERMINAL_FAILURE:
            rollback_failed = True
        elif status != "completed":
            pending = True
        else:
            step.status = STEP_ROLLED_BACK

    db.commit()

    if pending:
        return cast(str, plan.status)
    if rollback_failed:
        _record_outcome(
            db,
            plan,
            verified=False,
            rolled_back=False,
            rollback_success=False,
            error="rollback command failed",
        )
        plan.status = "failed"
    else:
        _record_outcome(
            db, plan, verified=False, rolled_back=True, rollback_success=True
        )
        plan.status = "rolled_back"
    db.commit()
    return cast(str, plan.status)


def _first_device(db: SASession, plan: Any) -> Optional[Device]:
    """Return the ORM device targeted by the plan's first step, if any."""
    for step in plan.steps:
        if step.target_device_id:
            return (
                db.query(Device)
                .filter(Device.device_id == step.target_device_id)
                .first()
            )
    return None


def _record_outcome(
    db: SASession,
    plan: Any,
    *,
    verified: bool,
    rolled_back: bool,
    rollback_success: Optional[bool] = None,
    error: Optional[str] = None,
) -> AIActionOutcome:
    """Create or update the single outcome for a plan (idempotent)."""
    outcome = plan.outcome
    if outcome is None:
        provenance = derive_provenance(_first_device(db, plan))
        outcome = AIActionOutcome(
            plan_id=plan.plan_id,
            provenance=getattr(provenance, "value", provenance),
        )
        db.add(outcome)
    outcome.verified = verified
    outcome.rolled_back = rolled_back
    outcome.rollback_success = rollback_success
    outcome.error = error
    return cast(AIActionOutcome, outcome)
