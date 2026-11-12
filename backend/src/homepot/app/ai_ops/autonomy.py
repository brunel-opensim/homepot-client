"""Autonomy controller for AI action delegation (Phase D, item 16).

Determines the autonomy level for each action type based on measured
reliability. Levels:

- Level 0: Suggest only (AI answers in prose, no proposal)
- Level 1: Propose (AI proposes a plan, technician must approve)
- Level 2: Execute if trust >= threshold (AI proposes, auto-executes if
  trust score meets the bar, technician can still reject beforehand)
- Level 3: Auto-execute for proven-safe actions (no approval needed)

Autonomy is earned per (action type, OS family) from measured outcomes, never
granted globally. This ensures that when a new OS is added to the fleet, it
starts at Level 0 and must earn autonomy independently -- an action that is
proven on Windows does not auto-execute on an untested Linux/macOS device.

Advancing an action type requires:
  - >= 50 verified runs
  - >= 98% success rate
  - Rollback proven (at least one successful rollback)
"""

from dataclasses import dataclass, field
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Autonomy thresholds (from docs/ai-delegation-plan.md open decision #4)
MIN_SAMPLES_FOR_LEVEL_2 = 50
MIN_SUCCESS_RATE_FOR_LEVEL_2 = 0.98
MIN_SAMPLES_FOR_LEVEL_3 = 200
MIN_SUCCESS_RATE_FOR_LEVEL_3 = 0.995


@dataclass
class AutonomyLevel:
    """Autonomy level for a specific action type and OS family."""

    action_type: str
    os_family: Optional[str] = None  # None = fleet-wide aggregate
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
    """Determines autonomy level per (action type, OS family)."""

    def __init__(self) -> None:
        """Initialize the autonomy controller."""
        self._levels: Dict[Tuple[str, Optional[str]], AutonomyLevel] = {}

    def _key(
        self, action_type: str, os_family: Optional[str]
    ) -> Tuple[str, Optional[str]]:
        return (action_type, os_family)

    def get_level(
        self, action_type: str, os_family: Optional[str] = None
    ) -> AutonomyLevel:
        """Return the autonomy level for an action type and OS family.

        When ``os_family`` is ``None``, returns the fleet-wide aggregate
        (across all OS families). When specified, returns the per-OS level.
        """
        key = self._key(action_type, os_family)
        if key not in self._levels:
            self._levels[key] = AutonomyLevel(
                action_type=action_type, os_family=os_family
            )
        return self._levels[key]

    def update_level(
        self,
        action_type: str,
        os_family: Optional[str] = None,
        *,
        sample_count: int,
        success_rate: float,
        rollback_proven: bool = False,
    ) -> AutonomyLevel:
        """Update autonomy level based on measured reliability."""
        level = self.get_level(action_type, os_family)
        level.sample_count = sample_count
        level.success_rate = success_rate
        level.rollback_proven = rollback_proven

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
                "Autonomy level for '%s' (os=%s) changed: %d → %d (samples=%d, success=%.3f)",
                action_type,
                os_family or "fleet",
                level.level,
                new_level,
                sample_count,
                success_rate,
            )
        level.level = new_level
        from datetime import datetime, timezone

        level.last_updated = datetime.now(timezone.utc).isoformat()
        return level

    def check_autonomy(
        self, action_type: str, os_family: Optional[str] = None
    ) -> AutonomyDecision:
        """Check whether an action may be auto-executed.

        When ``os_family`` is specified and that OS has no recorded samples,
        the action is treated as untested on that OS and auto-execution is
        blocked (Level 0) regardless of fleet-wide performance.
        """
        if os_family is not None:
            os_level = self.get_level(action_type, os_family)
            if os_level.sample_count == 0:
                return AutonomyDecision(
                    action_type=action_type,
                    current_level=0,
                    may_auto_execute=False,
                    reason=(
                        f"Level 0: untested on {os_family} (0 samples); "
                        f"requires approval"
                    ),
                    metrics={
                        "sample_count": 0,
                        "success_rate": 0.0,
                        "os_family": os_family,
                        "untested_os": True,
                    },
                )
            level = os_level
        else:
            level = self.get_level(action_type, None)

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
                "os_family": os_family or "fleet",
                "rollback_proven": level.rollback_proven,
            },
        )

    def all_levels(self) -> Dict[str, AutonomyLevel]:
        """Return fleet-wide (os_family=None) levels for all action types."""
        return {at: level for (at, osf), level in self._levels.items() if osf is None}

    def all_levels_by_os(self) -> Dict[str, Dict[Optional[str], AutonomyLevel]]:
        """Return all levels grouped by action type and OS family."""
        result: Dict[str, Dict[Optional[str], AutonomyLevel]] = {}
        for (at, osf), level in self._levels.items():
            result.setdefault(at, {})[osf] = level
        return result


async def hydrate_autonomy_from_reliability(
    days: int = 30,
    os_family: Optional[str] = None,
    controller: Optional[AutonomyController] = None,
) -> AutonomyController:
    """Hydrate an :class:`AutonomyController` from measured reliability.

    When ``os_family`` is specified, only metrics for that OS are loaded.
    When ``None``, metrics are loaded for all OS families found in the data,
    plus a fleet-wide aggregate.
    """
    if controller is None:
        controller = get_autonomy_controller()
    try:
        from ai.analytics_service import AIAnalyticsService

        metrics = await AIAnalyticsService.get_ai_action_reliability(
            days=days, os_family=os_family
        )
    except Exception:
        logger.warning("Could not hydrate autonomy from reliability", exc_info=True)
        return controller

    if not isinstance(metrics, dict) or metrics.get("status") == "error":
        return controller

    action_types = metrics.get("action_types", {}) or {}
    for action_type, data in action_types.items():
        counts = (data or {}).get("counts", {}) or {}
        rates = (data or {}).get("rates", {}) or {}
        sample_count = int(counts.get("executed", 0) or 0)
        success_rate = float(rates.get("execution_success", 0.0) or 0.0)
        rollback_proven = int(counts.get("rolled_back", 0) or 0) > 0

        # When hydrating a specific OS, store as per-OS entry (not fleet-wide).
        if os_family is not None:
            try:
                controller.update_level(
                    action_type,
                    os_family=os_family,
                    sample_count=sample_count,
                    success_rate=success_rate,
                    rollback_proven=rollback_proven,
                )
            except Exception:
                logger.warning(
                    "Failed to update autonomy for %s (os=%s)",
                    action_type,
                    os_family,
                    exc_info=True,
                )
            continue

        # Fleet-wide aggregate
        os_family_val = None  # fleet aggregate
        try:
            controller.update_level(
                action_type,
                os_family=os_family_val,
                sample_count=sample_count,
                success_rate=success_rate,
                rollback_proven=rollback_proven,
            )
        except Exception:
            logger.warning(
                "Failed to update autonomy for %s (os=%s)",
                action_type,
                os_family_val,
                exc_info=True,
            )

        # Per-OS breakdown
        by_os = (data or {}).get("by_os", {}) or {}
        for osf, os_data in by_os.items():
            os_counts = (os_data or {}).get("counts", {}) or {}
            os_rates = (os_data or {}).get("rates", {}) or {}
            os_samples = int(os_counts.get("executed", 0) or 0)
            os_success = float(os_rates.get("execution_success", 0.0) or 0.0)
            os_rollback = int(os_counts.get("rolled_back", 0) or 0) > 0
            try:
                controller.update_level(
                    action_type,
                    os_family=osf,
                    sample_count=os_samples,
                    success_rate=os_success,
                    rollback_proven=os_rollback,
                )
            except Exception:
                logger.warning(
                    "Failed to update autonomy for %s (os=%s)",
                    action_type,
                    osf,
                    exc_info=True,
                )
    return controller


# Singleton instance
_controller: Optional[AutonomyController] = None


def get_autonomy_controller() -> AutonomyController:
    """Get the singleton autonomy controller."""
    global _controller
    if _controller is None:
        _controller = AutonomyController()
    return _controller
