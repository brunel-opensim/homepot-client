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
DEFAULT_BATTERY_LOW_PERCENT = 20.0
DEFAULT_CPU_TEMP_C = 85.0
DEFAULT_CPU_THROTTLE_RATIO = 0.5
DEFAULT_WIFI_SIGNAL_DBM = -80.0


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
            "battery_low_percent": thresholds.get(
                "battery_low_percent", DEFAULT_BATTERY_LOW_PERCENT
            ),
            "cpu_temp_c": thresholds.get("cpu_temp_c", DEFAULT_CPU_TEMP_C),
            "cpu_throttle_ratio": thresholds.get(
                "cpu_throttle_ratio", DEFAULT_CPU_THROTTLE_RATIO
            ),
            "wifi_signal_dbm": thresholds.get(
                "wifi_signal_dbm", DEFAULT_WIFI_SIGNAL_DBM
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
                     error_rate, network_latency_ms, flapping_count, consecutive_failures,
                     battery_percent, battery_charging, cpu_temp_c, system_temp_c,
                     cpu_speed_mhz, cpu_speed_max_mhz, wifi_signal_dbm
                     Optional keys: connectivity_offline, no_telemetry, stale_telemetry

        Returns:
            tuple: (Anomaly score, List of anomaly descriptions)
        """
        score = 0.0
        anomalies = []

        try:
            # 1. Critical Stability Checks (High Impact)

            # Check Flapping (State Changes) — uses the pre-computed count of
            # healthy<->unhealthy transitions in recent health checks.
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

            # Connectivity: an active device with no recent heartbeat is offline.
            if metrics.get("connectivity_offline"):
                score += 0.4
                anomalies.append("Device offline (no recent heartbeat)")

            # Telemetry freshness: missing or stale metrics indicate the device
            # is not reporting, which is itself an anomaly.
            if metrics.get("no_telemetry"):
                score += 0.3
                anomalies.append("No telemetry available")
            elif metrics.get("stale_telemetry"):
                score += 0.3
                anomalies.append("Stale telemetry (no recent metrics)")

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

            # 3. Device Health Checks (new device-health signals)

            # Low battery (mobile/tablet POS about to lose power)
            battery = metrics.get("battery_percent")
            if (
                battery is not None
                and battery <= self.thresholds["battery_low_percent"]
            ):
                score += 0.3
                charging = " (charging)" if metrics.get("battery_charging") else ""
                anomalies.append(f"Low Battery: {battery}%{charging}")

            # High temperature (thermal throttling / failure risk)
            cpu_temp = metrics.get("cpu_temp_c")
            sys_temp = metrics.get("system_temp_c")
            if cpu_temp is not None and cpu_temp > self.thresholds["cpu_temp_c"]:
                score += 0.3
                anomalies.append(f"High Temperature: {cpu_temp}C")
            elif sys_temp is not None and sys_temp > self.thresholds["cpu_temp_c"]:
                score += 0.3
                anomalies.append(f"High System Temperature: {sys_temp}C")

            # CPU throttling (current clock well below nominal maximum)
            cpu_speed = metrics.get("cpu_speed_mhz")
            cpu_max = metrics.get("cpu_speed_max_mhz")
            if (
                cpu_speed is not None
                and cpu_max is not None
                and cpu_max > 0
                and (cpu_speed / cpu_max) < self.thresholds["cpu_throttle_ratio"]
            ):
                score += 0.2
                anomalies.append(f"CPU Throttled: {cpu_speed}MHz vs {cpu_max}MHz max")

            # Weak Wi-Fi signal (link degradation)
            wifi_signal = metrics.get("wifi_signal_dbm")
            if (
                wifi_signal is not None
                and wifi_signal < self.thresholds["wifi_signal_dbm"]
            ):
                score += 0.2
                anomalies.append(f"Weak Wi-Fi Signal: {wifi_signal}dBm")

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
