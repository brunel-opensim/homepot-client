"""Module for detecting anomalies in device metrics."""

import logging
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Detects anomalies in device metrics using rule-based thresholds."""

    def __init__(self, config_path: str = "config.yaml") -> None:
        """Initialize the AnomalyDetector with configuration."""
        try:
            with open(config_path, "r") as f:
                self.config = yaml.safe_load(f)
            self.sensitivity = self.config.get("anomaly_detection", {}).get(
                "sensitivity", 0.8
            )
        except Exception as e:
            logger.warning(f"Failed to load config: {e}. Using defaults.")
            self.sensitivity = 0.8

        # Define thresholds (could be moved to config later)
        self.thresholds = {
            "cpu_percent": 90.0,
            "memory_percent": 90.0,
            "disk_percent": 95.0,
            "error_rate": 0.1,  # 10% error rate
            "network_latency_ms": 1000.0,  # 1 second
        }

    def check_anomaly(self, metrics: Dict[str, Any]) -> float:
        """Calculate anomaly score (0.0 to 1.0) based on metrics.

        Returns:
            float: Anomaly score where 0.0 is normal and 1.0 is critical.
        """
        score = 0.0
        anomalies = []

        try:
            # Check CPU
            cpu = metrics.get("cpu_percent")
            if cpu is not None and cpu > self.thresholds["cpu_percent"]:
                score += 0.4
                anomalies.append(f"High CPU: {cpu}%")

            # Check Memory
            mem = metrics.get("memory_percent")
            if mem is not None and mem > self.thresholds["memory_percent"]:
                score += 0.3
                anomalies.append(f"High Memory: {mem}%")

            # Check Disk
            disk = metrics.get("disk_percent")
            if disk is not None and disk > self.thresholds["disk_percent"]:
                score += 0.2
                anomalies.append(f"High Disk Usage: {disk}%")

            # Check Error Rate
            err = metrics.get("error_rate")
            if err is not None and err > self.thresholds["error_rate"]:
                score += 0.5
                anomalies.append(f"High Error Rate: {err}")

            # Check Latency
            lat = metrics.get("network_latency_ms")
            if lat is not None and lat > self.thresholds["network_latency_ms"]:
                score += 0.2
                anomalies.append(f"High Latency: {lat}ms")

            # Cap score at 1.0
            final_score = min(score, 1.0)

            if final_score > 0:
                logger.info(
                    f"Anomaly detected (score={final_score}): {', '.join(anomalies)}"
                )

            return final_score

        except Exception as e:
            logger.error(f"Error checking anomalies: {e}")
            return 0.0
