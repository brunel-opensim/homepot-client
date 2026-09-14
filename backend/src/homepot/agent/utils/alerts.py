"""Proactive alert evaluation for the real device agent.

The real device agent measures genuine host telemetry (CPU, memory, disk,
network latency, disk I/O) instead of fabricating values, so its alerts are
raised from real measurements against explicit thresholds.  This module owns
the rule set, the alert payload construction (which matches the backend
``AgentAlertRequest`` schema in ``app/schemas/agent.py``), and an
edge-triggered deduplication state machine so a sustained condition produces
exactly one alert.
"""

from typing import Any, Dict, List, Optional

# Default thresholds for real-device alerts.  ``cpu``/``memory``/``disk`` are
# the same 90% marks the health-check diagnostics (``command_poller.py``)
# already treat as unhealthy; ``latency_warning`` aligns with the AI anomaly
# feed's 200ms flag and ``latency_critical`` with the emulator's 500ms
# critical escalation.
DEFAULT_ALERT_THRESHOLDS: Dict[str, float] = {
    "cpu": 90.0,
    "memory": 90.0,
    "disk": 90.0,
    "latency_warning": 200.0,
    "latency_critical": 500.0,
}

# Condition keys the evaluator can raise for metric-derived conditions.
_METRIC_ALERT_KEYS = {
    "high_cpu",
    "high_memory",
    "high_disk",
    "high_latency",
    "backend_unreachable",
}


class AlertEvaluator:
    """Evaluate telemetry/job snapshots against thresholds, deduplicated.

    Edge semantics:
    - A metric condition must be observed on **two consecutive** evaluations
      to be reported, so a transient blip is ignored.
    - Once reported a condition stays ``active`` and is not re-reported until
      it clears and recurs.
    - Background-job failures are reported once per job id.

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
        # per-condition state: missing = clear, "pending" = seen once,
        # "active" = already reported
        self._state: Dict[str, str] = {}
        # job ids already reported as failed
        self._reported_jobs: set = set()

    def alert_candidates(
        self,
        metrics: Dict[str, Any],
        last_job: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Return alert payloads that should be sent on this evaluation.

        Empty when nothing new crosses a threshold; returns at most one
        payload per condition per clear/recur cycle.
        """
        candidates: List[Dict[str, Any]] = []

        violated = set(self._violations(metrics))
        for key in violated:
            state = self._state.get(key)
            if state == "active":
                continue
            if state == "pending":
                candidates.append(self._payload_for(key, metrics))
                self._state[key] = "active"
            else:
                self._state[key] = "pending"

        # Any condition no longer violated clears (a pending-only blip also
        # resolves without ever being reported).
        for key in [k for k in self._state if k not in violated]:
            del self._state[key]

        if last_job and last_job.get("status") == "failed":
            job_id = last_job.get("job_id")
            action = last_job.get("action") or "background task"
            if job_id and job_id not in self._reported_jobs:
                candidates.append(
                    {
                        "title": "Background Job Failed",
                        "description": f"Background job '{action}' failed to "
                        "complete within the expected time",
                        "severity": "warning",
                        "category": "software",
                    }
                )
                self._reported_jobs.add(job_id)

        return candidates

    def _violations(self, metrics: Dict[str, Any]) -> List[str]:
        """Return the condition keys currently violated by ``metrics``."""
        keys: List[str] = []

        cpu = float(metrics.get("cpu_usage") or 0)
        if cpu >= self.thresholds["cpu"]:
            keys.append("high_cpu")

        memory = float(metrics.get("memory_usage") or 0)
        if memory >= self.thresholds["memory"]:
            keys.append("high_memory")

        disk = float(metrics.get("disk_usage") or 0)
        if disk >= self.thresholds["disk"]:
            keys.append("high_disk")

        latency = metrics.get("network_latency_ms")
        if latency is None:
            keys.append("backend_unreachable")
        elif latency >= self.thresholds["latency_warning"]:
            keys.append("high_latency")

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


__all__ = ["AlertEvaluator", "DEFAULT_ALERT_THRESHOLDS", "_METRIC_ALERT_KEYS"]
