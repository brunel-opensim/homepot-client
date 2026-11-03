"""Autonomy controller for AI action delegation (Phase D, item 16).

Determines the autonomy level for each action type based on measured
reliability. Levels:

- Level 0: Suggest only (AI answers in prose, no proposal)
- Level 1: Propose (AI proposes a plan, technician must approve)
- Level 2: Execute if trust >= threshold (AI proposes, auto-executes if
  trust score meets the bar, technician can still reject beforehand)
- Level 3: Auto-execute for proven-safe actions (no approval needed)

Autonomy is earned per action type from measured outcomes, never granted
globally. Advancing an action type requires:
  - >= 50 verified runs
  - >= 98% success rate
  - Rollback proven (at least one successful rollback)
"""

from dataclasses import dataclass, field
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Autonomy thresholds (from docs/ai-delegation-plan.md open decision #4)
MIN_SAMPLES_FOR_LEVEL_2 = 50
MIN_SUCCESS_RATE_FOR_LEVEL_2 = 0.98
MIN_SAMPLES_FOR_LEVEL_3 = 200
MIN_SUCCESS_RATE_FOR_LEVEL_3 = 0.995


@dataclass
class AutonomyLevel:
    """Autonomy level for a specific action type."""

    action_type: str
    level: int = 0  # 0=suggest, 1=propose, 2=auto-execute-if-trust, 3=auto-execute
    sample_count: int = 0
    success_rate: float = 0.0
    rollback_proven: bool = False
    last_updated: Optional[str] = None


@dataclass
class AutonomyDecision:
    """Result of an autonomy check."""

    action_type: str
    current_level: int
    may_auto_execute: bool
    reason: str
    metrics: Dict[str, Any] = field(default_factory=dict)


class AutonomyController:
    """Determines autonomy level per action type from reliability metrics."""

    def __init__(self) -> None:
        """Initialize the autonomy controller."""
        self._levels: Dict[str, AutonomyLevel] = {}

    def get_level(self, action_type: str) -> AutonomyLevel:
        """Return the current autonomy level for an action type."""
        if action_type not in self._levels:
            self._levels[action_type] = AutonomyLevel(action_type=action_type)
        return self._levels[action_type]

    def update_level(
        self,
        action_type: str,
        *,
        sample_count: int,
        success_rate: float,
        rollback_proven: bool = False,
    ) -> AutonomyLevel:
        """Update autonomy level based on measured reliability."""
        level = self.get_level(action_type)
        level.sample_count = sample_count
        level.success_rate = success_rate
        level.rollback_proven = rollback_proven

        # Determine new level
        new_level = 0
        if (
            sample_count >= MIN_SAMPLES_FOR_LEVEL_3
            and success_rate >= MIN_SUCCESS_RATE_FOR_LEVEL_3
            and rollback_proven
        ):
            new_level = 3
        elif (
            sample_count >= MIN_SAMPLES_FOR_LEVEL_2
            and success_rate >= MIN_SUCCESS_RATE_FOR_LEVEL_2
        ):
            new_level = 2
        elif sample_count > 0:
            new_level = 1

        if new_level != level.level:
            logger.info(
                "Autonomy level for '%s' changed: %d → %d (samples=%d, success=%.3f)",
                action_type,
                level.level,
                new_level,
                sample_count,
                success_rate,
            )
        level.level = new_level
        from datetime import datetime, timezone

        level.last_updated = datetime.now(timezone.utc).isoformat()
        return level

    def check_autonomy(self, action_type: str) -> AutonomyDecision:
        """Check whether an action may be auto-executed."""
        level = self.get_level(action_type)
        may_auto = level.level >= 3
        reason = f"Level {level.level}: " + (
            "auto-execute allowed"
            if may_auto
            else f"requires approval (samples={level.sample_count}, "
            f"success={level.success_rate:.3f})"
        )
        return AutonomyDecision(
            action_type=action_type,
            current_level=level.level,
            may_auto_execute=may_auto,
            reason=reason,
            metrics={
                "sample_count": level.sample_count,
                "success_rate": level.success_rate,
                "rollback_proven": level.rollback_proven,
            },
        )

    def all_levels(self) -> Dict[str, AutonomyLevel]:
        """Return all tracked autonomy levels."""
        return dict(self._levels)


# Singleton instance
_controller: Optional[AutonomyController] = None


def get_autonomy_controller() -> AutonomyController:
    """Get the singleton autonomy controller."""
    global _controller
    if _controller is None:
        _controller = AutonomyController()
    return _controller
