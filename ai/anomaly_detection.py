"""Module for detecting anomalies in device metrics."""

import logging
from typing import Any, Dict

from .config import load_ai_config

logger = logging.getLogger(__name__)

# Fallback defaults used when ai/config.yaml does not supply a value (see
# ai/config.py). Runtime thresholds come from the anomaly_detection section.
DEFAULT_SENSITIVITY = 0.8
DEFAULT_CPU_PERCENT = 90.0
DEFAULT_MEMORY_PERCENT = 90.0
DEFAULT_DISK_PERCENT = 90.0
DEFAULT_ERROR_RATE = 0.05
DEFAULT_NETWORK_LATENCY_MS = 200.0
DEFAULT_MAX_FLAPPING_COUNT = 5
DEFAULT_CONSECUTIVE_FAILURES = 3


class AnomalyDetector:
    """Detects anomalies in device metrics using rule-based thresholds."""

    def __init__(
        self, config_path: str | None = None, sensitivity: float | None = None
    ) -> None:
        """Initialize the AnomalyDetector with configuration."""
        self.config = (
            load_ai_config() if config_path is None else self._load_config(config_path)
        )
        section = self.config.get("anomaly_detection", {}) or {}

        configured_sensitivity = section.get("sensitivity", DEFAULT_SENSITIVITY)
        # An explicit `sensitivity` argument overrides the configured value so
        # callers/tests can isolate the raw per-signal scoring.
        self.sensitivity = (
            sensitivity if sensitivity is not None else configured_sensitivity
        )

        thresholds = section.get("thresholds", {}) or {}
        self.thresholds = {
            "cpu_percent": thresholds.get("cpu_percent", DEFAULT_CPU_PERCENT),
            "memory_percent": thresholds.get("memory_percent", DEFAULT_MEMORY_PERCENT),
            "disk_percent": thresholds.get("disk_percent", DEFAULT_DISK_PERCENT),
            "error_rate": thresholds.get("error_rate", DEFAULT_ERROR_RATE),
            "network_latency_ms": thresholds.get(
                "network_latency_ms", DEFAULT_NETWORK_LATENCY_MS
            ),
            "flapping_count": thresholds.get(
                "max_flapping_count", DEFAULT_MAX_FLAPPING_COUNT
            ),
            "consecutive_failures": thresholds.get(
                "consecutive_failures", DEFAULT_CONSECUTIVE_FAILURES
            ),
        }

    @staticmethod
    def _load_config(config_path: str) -> Dict[str, Any]:
        """Load an explicit config file, degrading to ``{}`` on error."""
        try:
            import yaml

            with open(config_path, "r") as f:
                return yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            return {}

    def check_anomaly(self, metrics: Dict[str, Any]) -> tuple[float, list[str]]:
        """Calculate anomaly score (0.0 to 1.0) based on metrics.

        Args:
            metrics: Dictionary containing device metrics.
                     Expected keys: cpu_percent, memory_percent, disk_percent,
                     error_rate, network_latency_ms, flapping_count, consecutive_failures

        Returns:
            tuple: (Anomaly score, List of anomaly descriptions)
        """
        score = 0.0
        anomalies = []

        try:
            # 1. Critical Stability Checks (High Impact)

            # Check Flapping (State Changes)
            flapping = metrics.get("flapping_count")
            if flapping is not None and flapping > self.thresholds["flapping_count"]:
                score += 0.6  # High impact
                anomalies.append(f"High Instability: {flapping} state changes/hr")

            # Check Consecutive Failures
            failures = metrics.get("consecutive_failures")
            if (
                failures is not None
                and failures >= self.thresholds["consecutive_failures"]
            ):
                score += 0.8  # Very High impact
                anomalies.append(
                    f"System Failure: {failures} consecutive health check failures"
                )

            # Check Error Rate
            err = metrics.get("error_rate")
            if err is not None and err > self.thresholds["error_rate"]:
                score += 0.5
                anomalies.append(f"High Error Rate: {err:.1%}")

            # Check Latency
            lat = metrics.get("network_latency_ms")
            if lat is not None and lat > self.thresholds["network_latency_ms"]:
                score += 0.4
                anomalies.append(f"High Latency: {lat}ms")

            # 2. Resource Usage Checks (Lower Impact - Warning Signs)

            # Check CPU
            cpu = metrics.get("cpu_percent")
            if cpu is not None and cpu > self.thresholds["cpu_percent"]:
                score += 0.2
                anomalies.append(f"High CPU: {cpu}%")

            # Check Memory
            mem = metrics.get("memory_percent")
            if mem is not None and mem > self.thresholds["memory_percent"]:
                score += 0.2
                anomalies.append(f"High Memory: {mem}%")

            # Check Disk
            disk = metrics.get("disk_percent")
            if disk is not None and disk > self.thresholds["disk_percent"]:
                score += 0.2
                anomalies.append(f"High Disk Usage: {disk}%")

            # Cap score at 1.0 and scale by sensitivity. A lower sensitivity
            # reports a smaller anomaly score (more conservative), so a
            # technician can tune how strongly the detector signals anomalies.
            raw_score = min(score, 1.0)
            final_score = min(raw_score * self.sensitivity, 1.0)

            if final_score > 0:
                logger.info(
                    f"Anomaly detected (score={final_score:.2f}): {', '.join(anomalies)}"
                )

            return final_score, anomalies

        except Exception as e:
            logger.error(f"Error checking anomalies: {e}")
            return 0.0, []
