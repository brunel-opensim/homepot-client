"""Rollback for failed AI action plans (Phase 3).

When a step fails mid-plan, the applied reversible steps are undone in reverse
order by queueing the inverse command through the same command queue. The
verifier then confirms the rollback commands completed.

* ``update_config`` — inverse is ``update_config`` with the snapshotted
  ``previous`` values (captured by the executor at queue time).
* ``install_program`` / ``uninstall_program`` — inverse is the opposite
  command with the same package id.
* ``restart`` — self-reverting: the device recovers on its own, so there is
  nothing to queue; the step is marked ``rolled_back`` immediately.

Actions with no reliable inverse (``update_program``, ``start_program``,
``stop_program``, read-only checks) are left untouched rather than being
reported as rolled back while their effect is still in place.
"""

import logging
from typing import Any, Dict, List

from sqlalchemy import update
from sqlalchemy.orm import Session as SASession

from homepot.app.ai_ops.registry import get_action_spec
from homepot.app.models.AnalyticsModel import AIActionStep
from homepot.database import get_database_service
from homepot.models import Device

logger = logging.getLogger(__name__)

STEP_DONE = "done"
STEP_ROLLED_BACK = "rolled_back"

# Key under which the inverse (rollback) command id is stored on the step.
ROLLBACK_COMMAND_KEY = "rollback_command_id"

# Reversible actions whose inverse is the opposite command with the same
# package id. Only these package operations have a reliable undo; other
# reversible actions are skipped during rollback instead of being falsely
# marked as rolled back.
PACKAGE_INVERSE_COMMANDS: Dict[str, str] = {
    "install_program": "uninstall_program",
    "uninstall_program": "install_program",
}


async def begin_rollback(db: SASession, plan: Any, db_service: Any = None) -> bool:
    """Queue inverse commands for applied, reversible steps (reverse order).

    Returns ``True`` when the plan has rollback work to track — either a command
    just queued, a command queued by an earlier (possibly interrupted) call, or
    a self-reverting step now marked ``rolled_back``. This lets the caller move
    the plan to ``rolling_back`` even across retries.

    Idempotent: steps that already carry a rollback command are skipped, so a
    retry after a partial failure never queues a duplicate inverse command. As
    in the executor, the sync read transaction is closed before the async
    inserts.
    """
    if db_service is None:
        db_service = await get_database_service()

    to_rollback: List[Dict[str, Any]] = []
    already_tracked = False
    for step in sorted(plan.steps, key=lambda s: s.seq, reverse=True):
        rollback_params = step.rollback_params or {}
        if rollback_params.get(ROLLBACK_COMMAND_KEY):
            already_tracked = True
            continue
        if step.status == STEP_ROLLED_BACK:
            continue

        spec = get_action_spec(step.action)
        if spec is None or not spec.reversible:
            continue

        if step.action == "update_config":
            if step.status not in (STEP_DONE, "failed"):
                continue
            previous = rollback_params.get("previous")
            if not previous:
                continue

            device = (
                db.query(Device)
                .filter(Device.device_id == step.target_device_id)
                .first()
            )
            if device is None:
                continue

            to_rollback.append(
                {
                    "step_id": step.step_id,
                    "self_reverting": False,
                    "device_pk": device.id,
                    "command_type": spec.command_type,
                    "previous": previous,
                    "existing": dict(rollback_params),
                }
            )
        elif step.action == "restart" and step.status == STEP_DONE:
            # Restart is self-reverting: the device recovers on its own.
            to_rollback.append({"step_id": step.step_id, "self_reverting": True})
        elif step.action in PACKAGE_INVERSE_COMMANDS and step.status == STEP_DONE:
            package = (step.params or {}).get("package")
            if not isinstance(package, str) or not package.strip():
                # Without the original package id there is nothing reliable to
                # queue; leave the step as-is instead of claiming a rollback.
                continue

            device = (
                db.query(Device)
                .filter(Device.device_id == step.target_device_id)
                .first()
            )
            if device is None:
                continue

            to_rollback.append(
                {
                    "step_id": step.step_id,
                    "self_reverting": False,
                    "device_pk": device.id,
                    "command_type": PACKAGE_INVERSE_COMMANDS[step.action],
                    "previous": {"package": package},
                    "existing": dict(rollback_params),
                }
            )

    db.commit()

    queued = False
    for item in to_rollback:
        if item["self_reverting"]:
            db.execute(
                update(AIActionStep)
                .where(AIActionStep.step_id == item["step_id"])
                .values(status=STEP_ROLLED_BACK)
            )
            db.commit()
            queued = True
            continue

        command = await db_service.create_device_command(
            device_id=item["device_pk"],
            command_type=item["command_type"],
            payload={"data": item["previous"]},
            issued_by="ai:rollback",
        )
        merged = dict(item["existing"])
        merged[ROLLBACK_COMMAND_KEY] = command.command_id
        db.execute(
            update(AIActionStep)
            .where(AIActionStep.step_id == item["step_id"])
            .values(rollback_params=merged)
        )
        db.commit()
        queued = True

    db.expire_all()
    return queued or already_tracked
