"""Deterministic executor for approved AI action plans (Phase 3).

Given an ``approved`` plan, the executor:

1. re-runs the policy engine against live data (never trust the proposal);
2. queues one device command per step through the same ``DeviceCommand`` path
   the operator UI uses (single audited mutate path);
3. snapshots what is needed to undo each step;
4. moves the plan to ``executing``.

Completion is asynchronous — the device polls, runs the command and reports
back — so the executor returns immediately. The verifier
(:mod:`homepot.app.ai_ops.verifier`) advances the plan once results arrive.

If policy blocks the plan, it is recorded as ``blocked`` and nothing is queued.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import update
from sqlalchemy.orm import Session as SASession

from homepot.app.ai_ops.policy import PolicyResult, evaluate_plan
from homepot.app.ai_ops.registry import get_action_spec
from homepot.app.models.AnalyticsModel import AIActionStep, utc_now
from homepot.database import get_database_service
from homepot.models import Device

logger = logging.getLogger(__name__)

# Step status recorded once a command has been queued (model default: pending).
STEP_QUEUED = "queued"

# Param keys that are metadata, not part of the applied config.
_RESERVED_PARAMS = ("config", "previous", "before", "reason")


def applied_config(step: Any) -> Dict[str, Any]:
    """Return the config mapping a step will apply (may be empty)."""
    params = step.params or {}
    config = params.get("config")
    if isinstance(config, dict):
        return config
    return {k: v for k, v in params.items() if k not in _RESERVED_PARAMS}


# Titles mirror the compose-command labels in PushReview.jsx so AI-created
# commands show the same friendly title and are reusable from push history.
_AI_COMMAND_TITLES = {
    "health_check": "Health Check",
    "list_processes": "List Processes",
    "scan_filesystem": "Scan Filesystem",
    "list_installed_programs": "List Installed Programs",
    "list_connections": "List Network Connections",
    "update_config": "Apply Configuration",
    "restart": "Reboot System",
    "restart_agent": "Restart Agent",
    "update_app": "Update User App",
    "rollback_app": "Roll Back User App",
    "rollback_config": "Apply Configuration",
    "start_program": "Start Program",
    "stop_program": "Stop Program",
    "install_program": "Install Program",
    "uninstall_program": "Uninstall Program",
    "update_program": "Update Program",
    "upgrade_all_programs": "Upgrade All Programs",
    "bootstrap_winget": "Bootstrap Winget",
    "restart_service": "Restart Service",
    "shutdown": "Shut Down System",
    "run_command": "Run Command",
    "run_command_unprivileged": "Run Command",
    "run_script": "Run Script",
}


def command_payload(step: Any) -> Optional[Dict[str, Any]]:
    """Map a plan step to the device-command payload, or ``None``.

    Payloads mirror the compose-command envelope (``title`` + ``data``) so
    AI-created commands display the same friendly title in push history and
    can be reused by technicians. ``update_config``/``rollback_config`` nest
    their config under ``data``; ``restart_service`` passes the service name
    through (the device agent picks the OS-appropriate command).
    """
    title = _AI_COMMAND_TITLES.get(step.action, step.action.replace("_", " ").title())
    if step.action in ("update_config", "rollback_config"):
        return {"title": title, "data": applied_config(step)}
    params = step.params or {}
    if params:
        return {"title": title, "data": dict(params)}
    # Read-only / no-param actions still carry a title so history is readable.
    return {"title": title, "data": {}}


def rollback_snapshot(step: Any, device: Optional[Device]) -> Optional[Dict[str, Any]]:
    """Capture what is needed to undo a step, or ``None`` if not reversible here.

    Preference order for ``update_config``: an explicit ``previous``/``before``
    mapping supplied in the proposal, then the values stored on the device's
    configuration for the keys being changed.
    """
    if step.action not in ("update_config", "rollback_config"):
        return None

    params = step.params or {}
    previous = params.get("previous") or params.get("before")
    if isinstance(previous, dict) and previous:
        return {"previous": previous}

    device_config = device.config if device is not None else None
    if isinstance(device_config, dict):
        keys = applied_config(step)
        prior = {key: device_config[key] for key in keys if key in device_config}
        if prior:
            return {"previous": prior}
    return None


def _is_step_ready(step: Any, plan: Any) -> bool:
    """Check if a step is ready to be dispatched.

    A step is ready when:
    - Its status is ``pending`` (or ``approved`` for per-step gates)
    - All its dependencies have status ``done``
    - It has not already been queued/running/done
    """
    if step.status not in ("pending", "approved"):
        return False
    # A step waiting out its retry backoff is not ready yet.
    next_retry_at = getattr(step, "next_retry_at", None)
    if next_retry_at is not None and next_retry_at > utc_now():
        return False
    deps = getattr(step, "depends_on", None)
    if deps is not None:
        # Single dependency (linear chain)
        if deps.status != "done":
            return False
    # Check depends_on_step_id for steps not loaded with relationship
    dep_id = getattr(step, "depends_on_step_id", None)
    if dep_id is not None and deps is None:
        # Need to check via plan steps
        dep_step = next((s for s in plan.steps if s.step_id == dep_id), None)
        if dep_step is not None and dep_step.status != "done":
            return False
    return True


async def _dispatch_step(
    db: SASession,
    step: Any,
    plan: Any,
    actor: str,
    db_service: Any,
) -> bool:
    """Dispatch a single ready step. Returns True if dispatched."""
    spec = get_action_spec(step.action)
    if spec is None:
        return False

    device = db.query(Device).filter(Device.device_id == step.target_device_id).first()
    if device is None:
        return False

    # Idempotency: skip if already has a command_id
    if step.command_id is not None:
        return False

    command = await db_service.create_device_command(
        device_id=device.id,
        command_type=spec.command_type,
        payload=command_payload(step),
        issued_by=f"ai:{actor}",
        idempotency_key=getattr(step, "idempotency_key", None),
    )

    snapshot = rollback_snapshot(step, device)

    values: Dict[str, Any] = {
        "status": STEP_QUEUED,
        "command_id": command.command_id,
        "started_at": utc_now(),
        # A re-dispatch ends the current backoff window.
        "next_retry_at": None,
    }
    if snapshot is not None:
        values["rollback_params"] = snapshot

    db.execute(
        update(AIActionStep)
        .where(AIActionStep.step_id == step.step_id)
        .values(**values)
    )
    db.commit()
    return True


async def dispatch_ready_steps(
    db: SASession,
    plan: Any,
    actor: str,
    db_service: Any = None,
) -> int:
    """Dispatch all ready steps in a plan. Returns count of newly dispatched.

    A step is ready when its dependencies are all ``done`` and its status is
    ``pending``/``approved``. This is called by the executor (initial dispatch)
    and by the reconcile loop (progression after a step completes).

    Idempotent: steps already queued/running/done are skipped.
    """
    if db_service is None:
        db_service = await get_database_service()

    dispatched = 0
    # Evaluate dependencies against the current plan state.
    for step in plan.steps:
        if not _is_step_ready(step, plan):
            continue
        # Per-step policy check
        from homepot.app.ai_ops.policy import evaluate_step

        step_policy = evaluate_step(db, step, plan=plan)
        if not step_policy.allowed:
            # Check if this is a deferral (maintenance window) vs a hard failure
            reasons_text = "; ".join(step_policy.reasons) or "policy blocked"
            if "maintenance window" in reasons_text.lower():
                step.status = "deferred"
                step.error = reasons_text
                # Don't set completed_at — step will be retried when window opens
            else:
                step.status = "failed"
                step.error = reasons_text
                step.completed_at = utc_now()
            db.commit()
            continue

        # Per-step approval gate
        if getattr(step, "approval_required", False) and step.status != "approved":
            step.status = "awaiting_approval"
            db.commit()
            continue

        ok = await _dispatch_step(db, step, plan, actor, db_service)
        if ok:
            dispatched += 1

    db.expire_all()
    return dispatched


async def start_execution(
    db: SASession,
    plan: Any,
    actor: str,
    db_service: Any = None,
) -> Tuple[Any, PolicyResult]:
    """Run policy then dispatch ready (root) steps of an approved plan.

    A blocked plan is recorded as ``blocked`` (nothing queued); an allowed plan
    moves to ``executing`` with only its root steps ``queued``. Dependent steps
    remain ``pending`` until their dependencies complete. The reconcile loop
    drives further progression via ``dispatch_ready_steps``.

    The sync session's read transaction is closed *before* the async command
    path is entered, so a command insert never contends with a lock held by
    this session.
    """
    policy = evaluate_plan(db, plan)

    if not policy.allowed:
        plan.status = "blocked"
        db.commit()
        return plan, policy

    # Capture metrics_before snapshot for outcome tracking (Phase D).
    try:
        from homepot.app.models.AnalyticsModel import DeviceMetrics as DM
        from homepot.models import Device as Dev

        device_ids = {s.target_device_id for s in plan.steps if s.target_device_id}
        metrics_before: dict = {}
        for did in device_ids:
            dev = db.query(Dev).filter(Dev.device_id == did).first()
            if dev is not None:
                latest = (
                    db.query(DM)
                    .filter(DM.device_id == dev.id)
                    .order_by(DM.timestamp.desc())
                    .first()
                )
                if latest is not None:
                    metrics_before[did] = {
                        "cpu_percent": latest.cpu_percent,
                        "memory_percent": latest.memory_percent,
                        "disk_percent": latest.disk_percent,
                        "timestamp": (
                            latest.timestamp.isoformat() if latest.timestamp else None
                        ),
                    }
        if metrics_before:
            # Persist in plan evidence so the verifier can read it back
            evidence = plan.evidence if isinstance(plan.evidence, dict) else {}
            evidence["_metrics_before"] = metrics_before
            plan.evidence = evidence
    except Exception:
        pass  # Non-critical; don't block execution

    # Validate dependency graph (no cycles, no missing targets)
    from homepot.app.ai_ops.policy import validate_dependencies

    dep_errors = validate_dependencies(plan)
    if dep_errors:
        plan.status = "blocked"
        db.commit()
        return plan, policy

    plan.status = "executing"
    db.commit()

    if db_service is None:
        db_service = await get_database_service()

    await dispatch_ready_steps(db, plan, actor, db_service)

    db.expire_all()
    return plan, policy
