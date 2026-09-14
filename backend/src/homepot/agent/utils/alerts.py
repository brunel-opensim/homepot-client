"""Proactive alert evaluation for the real device agent.

The real device agent measures genuine host telemetry (CPU, memory, disk,
network latency, disk I/O) instead of fabricating values, so its alerts are
raised from real measurements against explicit thresholds.  This module owns
the rule set, the alert payload construction (which matches the backend
``AgentAlertRequest`` schema in ``app/schemas/agent.py``), and an
edge-triggered deduplication state machine so a sustained condition produces
exactly one alert.

Two mechanisms keep the alert stream from becoming noisy around a threshold
boundary:

- **Edge triggering**: a condition must be observed on two consecutive
  evaluations before it is reported, so a transient blip is ignored.
- **Hysteresis**: once reported, a condition only clears (and can therefore
  recur) when its measurement drops below a dedicated ``*_clear`` threshold
  that is meaningfully lower than the warning line.

Conditions produce a single alert and, when they eventually clear, the caller
is told which conditions cleared so it can auto-resolve the corresponding
backend alert rows.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Default thresholds for real-device alerts.  ``cpu``/``memory``/``disk`` are
# the same 90% marks the health-check diagnostics (``command_poller.py``)
# already treat as unhealthy; ``latency_warning`` aligns with the AI anomaly
# feed's 200ms flag and ``latency_critical`` with the emulator's 500ms
# critical escalation.  Each warning threshold has a companion ``*_clear``
# threshold (roughly 80% of the warning value) that the measurement must drop
# below before an active condition is considered resolved.
DEFAULT_ALERT_THRESHOLDS: Dict[str, float] = {
    "cpu": 90.0,
    "cpu_clear": 80.0,
    "memory": 90.0,
    "memory_clear": 80.0,
    "disk": 90.0,
    "disk_clear": 80.0,
    "latency_warning": 200.0,
    "latency_critical": 500.0,
    "latency_clear": 160.0,
}

# Condition keys the evaluator can raise for metric-derived conditions.
_METRIC_ALERT_KEYS = {
    "high_cpu",
    "high_memory",
    "high_disk",
    "high_latency",
    "backend_unreachable",
}

# Maps each metric-derived condition to the telemetry snapshot key and its
# warning (trigger) + clear (hysteresis) threshold keys.
_CONDITION_SPECS: Dict[str, Dict[str, str]] = {
    "high_cpu": {
        "metric": "cpu_usage",
        "trigger": "cpu",
        "clear": "cpu_clear",
    },
    "high_memory": {
        "metric": "memory_usage",
        "trigger": "memory",
        "clear": "memory_clear",
    },
    "high_disk": {
        "metric": "disk_usage",
        "trigger": "disk",
        "clear": "disk_clear",
    },
    "high_latency": {
        "metric": "network_latency_ms",
        "trigger": "latency_warning",
        "clear": "latency_clear",
    },
}


@dataclass
class AlertCycle:
    """Outcome of one alert evaluation.

    ``new_alerts`` holds ``(condition_key, payload)`` pairs to post to the
    backend (``device_id`` and ``timestamp`` are filled in by the caller) and
    ``cleared_conditions`` lists the condition keys that transitioned from
    *active* to *clear* this cycle, so the caller can auto-resolve the alerts
    it previously raised.
    """

    new_alerts: List[Tuple[str, Dict[str, Any]]] = field(default_factory=list)
    cleared_conditions: List[str] = field(default_factory=list)


class AlertEvaluator:
    """Evaluate telemetry snapshots against thresholds, deduplicated.

    Edge semantics:
    - A metric condition must be observed on **two consecutive** evaluations
      to be reported, so a transient blip is ignored.
    - Once reported a condition stays ``active`` and is not re-reported until
      its measurement drops below the ``*_clear`` threshold (hysteresis width
      prevents alert storms from jitter around the warning line).
    - Each clear/recur cycle produces exactly one alert, and each clear is
      surfaced via ``AlertCycle.cleared_conditions`` for auto-resolution.

    Thread-safety: the evaluator is only ever used from the agent's single
    asyncio loop, so no locking is required.
    """

    def __init__(self, thresholds: Optional[Dict[str, float]] = None) -> None:
        """Configure thresholds, merging user overrides on top of defaults.

        ``thresholds`` uses the same keys as ``DEFAULT_ALERT_THRESHOLDS``;
        unprovided keys keep their default value.
        """
        self.thresholds = dict(DEFAULT_ALERT_THRESHOLDS)
        if thresholds:
            self.thresholds.update(thresholds)
        # Keep the hysteresis band sane: a clear threshold above its trigger
        # line would delete state on every evaluation and silently disable
        # the condition, so clamp clears to at most their trigger.
        for key, spec in _CONDITION_SPECS.items():
            self.thresholds[spec["clear"]] = min(
                self.thresholds[spec["clear"]], self.thresholds[spec["trigger"]]
            )
        # per-condition state: missing = clear, "pending" = seen once,
        # "active" = already reported
        self._state: Dict[str, str] = {}

    def alert_candidates(self, metrics: Dict[str, Any]) -> AlertCycle:
        """Return the outcome for one evaluation of ``metrics``.

        ``AlertCycle.new_alerts`` is empty when nothing *new* crosses a
        threshold (at most one payload per condition per clear/recur cycle) and
        ``AlertCycle.cleared_conditions`` lists the conditions that just
        resolved so the caller can auto-resolve their backend alert rows.
        """
        new_alerts: List[Tuple[str, Dict[str, Any]]] = []
        cleared_conditions: List[str] = []

        violated = set(self._violations(metrics))
        for key in violated:
            state = self._state.get(key)
            if state == "active":
                continue
            if state == "pending":
                new_alerts.append((key, self._payload_for(key, metrics)))
                self._state[key] = "active"
            else:
                self._state[key] = "pending"

        # Only conditions whose measurement has dropped below the clear
        # threshold resolve; anything still inside the hysteresis band keeps
        # its current state (pending blips are dropped silently).
        cleared = set(self._cleared_keys(metrics))
        for key in [k for k in self._state if k in cleared]:
            if self._state[key] == "active":
                cleared_conditions.append(key)
            del self._state[key]

        return AlertCycle(new_alerts=new_alerts, cleared_conditions=cleared_conditions)

    def _violations(self, metrics: Dict[str, Any]) -> List[str]:
        """Return the condition keys currently violated by ``metrics``."""
        keys: List[str] = []

        latency = metrics.get("network_latency_ms")
        if latency is None:
            keys.append("backend_unreachable")
        elif latency >= self.thresholds["latency_warning"]:
            keys.append("high_latency")

        for key, spec in _CONDITION_SPECS.items():
            if key == "high_latency":
                continue
            value = float(metrics.get(spec["metric"]) or 0)
            if value >= self.thresholds[spec["trigger"]]:
                keys.append(key)

        return keys

    def _cleared_keys(self, metrics: Dict[str, Any]) -> List[str]:
        """Return the condition keys that count as *clear* for ``metrics``.

        A condition is clear only when its measurement has dropped below the
        ``*_clear`` threshold (hysteresis).  ``backend_unreachable`` clears as
        soon as any latency measurement is present again.
        """
        keys: List[str] = []

        latency = metrics.get("network_latency_ms")
        if latency is not None:
            keys.append("backend_unreachable")
            if latency < self.thresholds["latency_clear"]:
                keys.append("high_latency")

        for key, spec in _CONDITION_SPECS.items():
            if key == "high_latency":
                continue
            value = float(metrics.get(spec["metric"]) or 0)
            if value < self.thresholds[spec["clear"]]:
                keys.append(key)

        return keys

    def _payload_for(self, key: str, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Build an ``AgentAlertRequest``-compatible payload for ``key``."""
        thresholds = self.thresholds
        if key == "high_cpu":
            value = float(metrics["cpu_usage"])
            return {
                "title": f"High CPU: {value:.1f}%",
                "description": f"CPU usage exceeded {thresholds['cpu']:.0f}% "
                f"threshold: {value:.1f}% observed on the host",
                "severity": "warning",
                "category": "hardware",
            }
        if key == "high_memory":
            value = float(metrics["memory_usage"])
            return {
                "title": f"High Memory Usage: {value:.1f}%",
                "description": f"Memory usage exceeded {thresholds['memory']:.0f}% "
                f"threshold: {value:.1f}% observed on the host",
                "severity": "warning",
                "category": "hardware",
            }
        if key == "high_disk":
            value = float(metrics["disk_usage"])
            return {
                "title": f"High Disk Usage: {value:.1f}%",
                "description": f"Disk usage exceeded {thresholds['disk']:.0f}% "
                f"threshold: {value:.1f}% observed on the primary volume",
                "severity": "warning",
                "category": "hardware",
            }
        if key == "high_latency":
            value = float(metrics["network_latency_ms"])
            severity = (
                "critical" if value > thresholds["latency_critical"] else "warning"
            )
            return {
                "title": f"High Network Latency: {value:.0f}ms",
                "description": f"Network latency to the backend exceeded "
                f"{thresholds['latency_warning']:.0f}ms: {value:.0f}ms observed "
                "on the primary interface",
                "severity": severity,
                "category": "network",
            }
        if key == "backend_unreachable":
            return {
                "title": "Backend Unreachable",
                "description": "No response from the backend during telemetry "
                "collection",
                "severity": "warning",
                "category": "network",
            }
        raise KeyError(f"no alert payload defined for condition {key}")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        """Return a short debug representation of the evaluator."""
        return (
            f"AlertEvaluator(thresholds={self.thresholds!r}, " f"state={self._state!r})"
        )


__all__ = [
    "AlertCycle",
    "AlertEvaluator",
    "DEFAULT_ALERT_THRESHOLDS",
    "_METRIC_ALERT_KEYS",
]
