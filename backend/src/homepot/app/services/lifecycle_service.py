"""Centralised device lifecycle state transition service.

All lifecycle_state changes must go through this service to ensure
transition rules are enforced and audit history is recorded.
"""

from datetime import datetime, timezone
import logging
from typing import Optional

from sqlalchemy.orm import Session

from homepot.app.models.AnalyticsModel import DeviceStateHistory
from homepot.models import Device, LifecycleState

logger = logging.getLogger(__name__)

ALLOWED_TRANSITIONS: dict[Optional[LifecycleState], list[LifecycleState]] = {
    None: [LifecycleState.PENDING],
    LifecycleState.PENDING: [LifecycleState.ACTIVE],
    LifecycleState.ACTIVE: [
        LifecycleState.SUSPENDED,
        LifecycleState.UNPAIRED,
        LifecycleState.RETIRED,
    ],
    LifecycleState.SUSPENDED: [
        LifecycleState.ACTIVE,
        LifecycleState.UNPAIRED,
        LifecycleState.RETIRED,
    ],
    LifecycleState.UNPAIRED: [LifecycleState.RETIRED],
    LifecycleState.RETIRED: [],
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LifecycleService:
    """Enforces lifecycle state transitions and records audit history."""

    def __init__(self, db: Session) -> None:
        """Initialise the lifecycle service with a database session."""
        self.db = db

    def transition(
        self,
        device: Device,
        new_state: LifecycleState,
        changed_by: str = "system",
        reason: str = "",
    ) -> Device:
        """Transition a device to *new_state* if the transition is allowed.

        Raises ValueError if the transition is not permitted.
        Persists the change, records DeviceStateHistory, and logs an audit event.
        """
        previous_state = (
            LifecycleState(device.lifecycle_state) if device.lifecycle_state else None
        )

        allowed = ALLOWED_TRANSITIONS.get(previous_state, [])
        if new_state not in allowed:
            raise ValueError(
                f"Transition from {previous_state.value if previous_state else 'none'} "
                f"to {new_state.value} is not allowed"
            )

        device.lifecycle_state = new_state.value  # type: ignore[assignment]

        if new_state in (LifecycleState.UNPAIRED, LifecycleState.RETIRED):
            device.is_active = False  # type: ignore[assignment]
        elif new_state in (
            LifecycleState.ACTIVE,
            LifecycleState.PENDING,
            LifecycleState.SUSPENDED,
        ):
            device.is_active = True  # type: ignore[assignment]

        self.db.add(device)

        history = DeviceStateHistory(
            device_id=device.id,
            previous_state=previous_state.value if previous_state else None,
            new_state=new_state.value,
            changed_by=changed_by,
            reason=reason,
            extra_data={"timestamp": _utc_now().isoformat()},
        )
        self.db.add(history)
        self.db.commit()
        self.db.refresh(device)

        logger.info(
            "Lifecycle transition: device=%s %s -> %s (by=%s, reason=%s)",
            device.device_id,
            previous_state.value if previous_state else "none",
            new_state.value,
            changed_by,
            reason,
        )

        return device

    def assert_active(self, device: Device) -> None:
        """Raise ValueError if device is not in an active lifecycle state."""
        if device.lifecycle_state != LifecycleState.ACTIVE.value:
            raise ValueError(
                f"Device '{device.device_id}' lifecycle state is "
                f"'{device.lifecycle_state}', expected 'active'"
            )
