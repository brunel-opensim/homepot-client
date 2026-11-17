"""Audit helpers for commands dispatched by the AI delegation paths.

The operator command endpoint writes ``command_queued`` when it inserts a
``DeviceCommand``. The AI executor and rollback paths insert through the same
database service but skipped that event, so AI-dispatched commands had no
queue-side audit trail. This module gives both paths one shared, best-effort
writer for that event.
"""

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session as SASession

from homepot.models import User

logger = logging.getLogger(__name__)


async def log_ai_command_queued(
    db: SASession,
    plan: Any,
    command: Any,
    device: Any,
    actor: str,
    step_id: Optional[str] = None,
    origin: str = "AI plan",
) -> None:
    """Write the ``command_queued`` event for an AI-dispatched command.

    Args:
        db: Sync session used to resolve the acting user, when known.
        plan: The action plan that produced the command.
        command: The newly created ``DeviceCommand`` row.
        device: The target device row.
        actor: Email of the technician who approved the action, or an AI actor.
        step_id: Step that produced the command, when available.
        origin: Leading label for the audit description ("AI plan" or
            "AI rollback for plan").
    """
    try:
        from homepot.audit import AuditEventType, get_audit_logger

        user = db.query(User).filter(User.email == actor).first() if actor else None
        await get_audit_logger().log_event(
            event_type=AuditEventType.COMMAND_QUEUED,
            description=(
                f"{origin} '{plan.plan_id}' queued {command.command_type} "
                f"command '{command.command_id}' for device '{device.device_id}'"
            ),
            user_id=int(user.id) if user is not None else None,
            device_id=device.id,
            site_id=device.site_id,
            new_values={
                "command_id": str(command.command_id),
                "command_type": str(command.command_type),
                "payload": command.payload,
            },
            event_metadata={
                "actor": actor,
                "plan_id": plan.plan_id,
                "step_id": step_id,
                "source": "ai",
            },
        )
    except Exception:
        # Audit parity must never stop a command that is already queued.
        logger.warning(
            "Failed to log command_queued for AI plan %s step %s",
            getattr(plan, "plan_id", None),
            step_id,
            exc_info=True,
        )
