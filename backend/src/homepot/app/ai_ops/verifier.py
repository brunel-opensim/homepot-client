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
from homepot.app.ai_ops.executor import dispatch_ready_steps
from homepot.app.models.AnalyticsModel import AIActionOutcome, utc_now
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
    all_done = True
    dispatched_new = False

    for step in plan.steps:
        if not step.command_id:
            # Step hasn't been dispatched yet (pending dependency or approval)
            if step.status in ("pending", "approved", "awaiting_approval"):
                all_done = False
            continue
        command = await db_service.get_command(step.command_id)
        status = _status_value(command)
        if status is None:
            all_done = False
            continue

        step.status = _COMMAND_TO_STEP.get(status, step.status)
        if step.status == STEP_DONE:
            # Check per-key failures inside a "completed" result
            failure = command_failure(getattr(command, "result", None))
            if failure:
                step.status = "failed"
                step.error = failure
                step.completed_at = utc_now()
            else:
                # Evaluate postconditions
                postcond_errors = _evaluate_postconditions(
                    step, getattr(command, "result", None)
                )
                if postcond_errors:
                    step.status = "failed"
                    step.error = "; ".join(postcond_errors)
                    step.completed_at = utc_now()
                else:
                    step.result = getattr(command, "result", None)
                    step.completed_at = utc_now()

        if step.status == "failed":
            any_failed = True
            # Block transitive dependents
            _block_dependents(plan, step.step_id)
        if step.status not in (STEP_DONE, STEP_ROLLED_BACK, "skipped"):
            all_done = False

    db.commit()

    if any_failed:
        trackable = await begin_rollback(db, plan, db_service)
        if trackable:
            plan.status = "rolling_back"
        else:
            _record_outcome(
                db, plan, verified=False, rolled_back=False, error="step failed"
            )
            plan.status = "failed"
        db.commit()
        return cast(str, plan.status)

    # Dispatch any newly-ready dependent steps
    try:
        actor = plan.created_by or "system"
        n = await dispatch_ready_steps(db, plan, actor, db_service)
        if n > 0:
            dispatched_new = True
            all_done = False
    except Exception as exc:
        logger.warning("dispatch_ready_steps failed: %s", exc)

    # all_done only when no step is pending/queued/running/awaiting_approval
    for step in plan.steps:
        if step.status in ("pending", "queued", "running", "awaiting_approval"):
            all_done = False
            break

    if all_done and not dispatched_new and bool(plan.steps):
        _record_outcome(db, plan, verified=True, rolled_back=False)
        plan.status = "succeeded"
        db.commit()
    return cast(str, plan.status)


def _block_dependents(plan: Any, failed_step_id: str) -> None:
    """Mark all transitive dependents of a failed step as 'skipped'."""
    # Build dependency map: step_id -> list of dependent step_ids
    dependents: dict = {}
    for step in plan.steps:
        dep_id = getattr(step, "depends_on_step_id", None)
        if dep_id is not None:
            dependents.setdefault(dep_id, []).append(step.step_id)

    # BFS to find all transitive dependents
    to_skip = set()
    queue = [failed_step_id]
    while queue:
        current = queue.pop(0)
        for dep in dependents.get(current, []):
            if dep not in to_skip:
                to_skip.add(dep)
                queue.append(dep)

    for step in plan.steps:
        if step.step_id in to_skip and step.status in ("pending", "approved"):
            step.status = "skipped"
            step.error = f"Blocked by failed dependency: {failed_step_id}"


def _evaluate_postconditions(step: Any, result: Any) -> list:
    """Evaluate a step's postconditions (deterministic, allowlisted).

    Returns a list of error strings (empty = all passed).
    """
    errors: list = []
    postconds = getattr(step, "postconditions", None)
    if not isinstance(postconds, dict):
        return errors

    if "health_ok" in postconds and postconds["health_ok"]:
        # Check if the command result indicates health is still OK
        if isinstance(result, dict):
            inner = result.get("result", result)
            if isinstance(inner, dict) and inner.get("status") in ("failed", "error"):
                errors.append(
                    "Postcondition 'health_ok' not met: command reported failure."
                )

    return errors


async def _reconcile_rolling_back(
    db: SASession, plan: Any, db_service: Any = None
) -> str:
    if db_service is None:
        db_service = await get_database_service()

    pending = False
    rollback_failed = False

    # Sort by reverse topological order (dependents first, then dependencies).
    # Build dependency map for topological sort.
    step_list = list(plan.steps)
    # Simple reverse-seq sort as fallback; if depends_on_step_id is set,
    # do a proper reverse-topological sort.
    has_deps = any(getattr(s, "depends_on_step_id", None) for s in step_list)
    if has_deps:
        # Topological sort (Kahn's algorithm, reversed)
        # Build adjacency: dep -> [dependents]
        dependents_map: dict = {}
        in_degree: dict = {s.step_id: 0 for s in step_list}
        for s in step_list:
            dep_id = getattr(s, "depends_on_step_id", None)
            if dep_id is not None and dep_id in in_degree:
                dependents_map.setdefault(dep_id, []).append(s.step_id)
                in_degree[s.step_id] = in_degree.get(s.step_id, 0) + 1
        # Start with steps that have no dependents (leaves)
        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        topo_order = []
        while queue:
            node = queue.pop(0)
            topo_order.append(node)
            for dep in dependents_map.get(node, []):
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)
        # If cycle, fall back to seq order
        if len(topo_order) != len(step_list):
            topo_order = [
                s.step_id for s in sorted(step_list, key=lambda x: x.seq, reverse=True)
            ]
        step_id_to_step = {s.step_id: s for s in step_list}
        ordered_steps = [
            step_id_to_step[sid] for sid in topo_order if sid in step_id_to_step
        ]
    else:
        ordered_steps = sorted(step_list, key=lambda x: x.seq, reverse=True)

    for step in ordered_steps:
        # Skip steps that never ran (pending/skipped) — nothing to undo
        if step.status in ("pending", "skipped", "awaiting_approval"):
            continue
        rollback_id = (step.rollback_params or {}).get(ROLLBACK_COMMAND_KEY)
        if not rollback_id:
            # A config step that should have a queued inverse but has none was
            # never rolled back (interrupted or un-snapshotted). Fail safe rather
            # than report a rollback that did not happen.
            if step.action == "update_config" and step.status in (STEP_DONE, "failed"):
                rollback_failed = True
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
