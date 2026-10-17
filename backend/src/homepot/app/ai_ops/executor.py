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
from homepot.app.models.AnalyticsModel import AIActionStep
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


def command_payload(step: Any) -> Optional[Dict[str, Any]]:
    """Map a plan step to the device-command payload, or ``None``.

    ``update_config`` payloads are nested under ``data`` to match
    ``command_poller._command_data``; ``restart`` carries no payload.
    """
    if step.action == "update_config":
        return {"data": applied_config(step)}
    return None


def rollback_snapshot(step: Any, device: Optional[Device]) -> Optional[Dict[str, Any]]:
    """Capture what is needed to undo a step, or ``None`` if not reversible here.

    Preference order for ``update_config``: an explicit ``previous``/``before``
    mapping supplied in the proposal, then the values stored on the device's
    configuration for the keys being changed.
    """
    if step.action != "update_config":
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


async def start_execution(
    db: SASession,
    plan: Any,
    actor: str,
    db_service: Any = None,
) -> Tuple[Any, PolicyResult]:
    """Run policy then queue one device command per step of an approved plan.

    A blocked plan is recorded as ``blocked`` (nothing queued); an allowed plan
    moves to ``executing`` with every step ``queued``. The sync session's read
    transaction is closed *before* the async command path is entered, so a
    command insert never contends with a lock held by this session.
    """
    policy = evaluate_plan(db, plan)

    # Capture everything needed for the async command path as plain data, then
    # end the read transaction so we do not hold a lock across the inserts.
    queued_steps = []
    for step in plan.steps:
        spec = get_action_spec(step.action)
        device = (
            db.query(Device).filter(Device.device_id == step.target_device_id).first()
        )
        queued_steps.append(
            {
                "step_id": step.step_id,
                "command_type": spec.command_type if spec else None,
                "device_pk": device.id if device is not None else None,
                "payload": command_payload(step),
                "snapshot": rollback_snapshot(step, device),
            }
        )

    if not policy.allowed:
        plan.status = "blocked"
        db.commit()
        return plan, policy

    plan.status = "executing"
    db.commit()

    if db_service is None:
        db_service = await get_database_service()

    for item in queued_steps:
        if item["command_type"] is None or item["device_pk"] is None:
            continue
        command = await db_service.create_device_command(
            device_id=item["device_pk"],
            command_type=item["command_type"],
            payload=item["payload"],
            issued_by=f"ai:{actor}",
        )
        values: Dict[str, Any] = {
            "status": STEP_QUEUED,
            "command_id": command.command_id,
        }
        if item["snapshot"] is not None:
            values["rollback_params"] = item["snapshot"]
        db.execute(
            update(AIActionStep)
            .where(AIActionStep.step_id == item["step_id"])
            .values(**values)
        )

    db.commit()
    db.expire_all()
    return plan, policy
