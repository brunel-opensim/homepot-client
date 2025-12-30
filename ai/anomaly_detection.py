"""Module for detecting anomalies in device metrics."""

import logging
import os
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Detects anomalies in device metrics using rule-based thresholds."""

    def __init__(self, config_path: str | None = None) -> None:
        """Initialize the AnomalyDetector with configuration."""
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        try:
            with open(config_path, "r") as f:
                self.config = yaml.safe_load(f)
            self.sensitivity = self.config.get("anomaly_detection", {}).get(
                "sensitivity", 0.8
            )
        except Exception as e:
            logger.warning(f"Failed to load config: {e}. Using defaults.")
            self.config = {}
            self.sensitivity = 0.8

        # Load thresholds from config or use defaults
        config_thresholds = self.config.get("anomaly_detection", {}).get(
            "thresholds", {}
        )
        self.thresholds = {
            "cpu_percent": config_thresholds.get("cpu_percent", 90.0),
            "memory_percent": config_thresholds.get("memory_percent", 90.0),
            "disk_percent": config_thresholds.get("disk_percent", 95.0),
            "error_rate": config_thresholds.get("max_error_rate", 0.05),
            "network_latency_ms": config_thresholds.get("max_latency_ms", 500.0),
            "flapping_count": config_thresholds.get("max_flapping_count", 5),
            "consecutive_failures": config_thresholds.get("consecutive_failures", 3),
        }

    def check_anomaly(self, metrics: Dict[str, Any]) -> float:
        """Calculate anomaly score (0.0 to 1.0) based on metrics.

        Args:
            metrics: Dictionary containing device metrics.
                     Expected keys: cpu_percent, memory_percent, disk_percent,
                     error_rate, network_latency_ms, flapping_count, consecutive_failures

        Returns:
            float: Anomaly score where 0.0 is normal and 1.0 is critical.
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

            # Cap score at 1.0
            final_score = min(score, 1.0)

            if final_score > 0:
                logger.info(
                    f"Anomaly detected (score={final_score:.2f}): {', '.join(anomalies)}"
                )

            return final_score

        except Exception as e:
            logger.error(f"Error checking anomalies: {e}")
            return 0.0
