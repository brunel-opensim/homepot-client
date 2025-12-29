"""Smart Data Filtering Utility.

This module provides logic to filter device metrics before storage,
ensuring that only significant changes or periodic snapshots are saved.
This prevents database overload in high-traffic environments.
"""

import logging
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


class SmartDataFilter:
    """Filters device metrics based on significance and time intervals."""

    def __init__(
        self,
        snapshot_interval: int = 300,  # 5 minutes
        change_threshold: float = 0.05,  # 5% change
    ) -> None:
        """Initialize the SmartDataFilter.

        Args:
            snapshot_interval: Time in seconds to force a new snapshot.
            change_threshold: Percentage change (0.0-1.0) to consider significant.
        """
        self.snapshot_interval = snapshot_interval
        self.change_threshold = change_threshold
        # In-memory cache: {device_id: {"timestamp": float, "metrics": dict}}
        # Note: In a distributed environment, this should be replaced by Redis.
        self._last_states: Dict[str, Dict[str, Any]] = {}
        # Error cache: {device_id_error_signature: timestamp}
        self._last_errors: Dict[str, float] = {}

    def should_store(self, device_id: str, metrics: Dict[str, Any]) -> bool:
        """Determine if the given metrics should be stored.

        Args:
            device_id: The unique identifier of the device.
            metrics: The dictionary of metric values.

        Returns:
            True if data should be stored, False otherwise.
        """
        current_time = time.time()

        # 1. New Device (or first time seeing it since restart)
        if device_id not in self._last_states:
            logger.debug(f"Device {device_id}: First data point. Storing.")
            self._update_state(device_id, metrics, current_time)
            return True

        last_state = self._last_states[device_id]
        last_time = last_state["timestamp"]
        last_metrics = last_state["metrics"]

        # 2. Snapshot Interval (Heartbeat)
        time_diff = current_time - last_time
        if time_diff >= self.snapshot_interval:
            logger.debug(
                f"Device {device_id}: Snapshot interval reached ({time_diff:.1f}s). Storing."
            )
            self._update_state(device_id, metrics, current_time)
            return True

        # 3. Significant Change
        if self._has_significant_change(last_metrics, metrics):
            logger.debug(f"Device {device_id}: Significant change detected. Storing.")
            self._update_state(device_id, metrics, current_time)
            return True

        # 4. Error/Anomaly Check (Always store if error_rate is high)
        if metrics.get("error_rate", 0) > 0.0:
            # If error rate changed or is non-zero, we might want to store it.
            # For now, let's rely on significant change, but maybe force store if error > 0?
            # Let's stick to significant change for error_rate too.
            pass

        return False

    def should_store_error(
        self, device_id: str, error_code: str, error_message: str
    ) -> bool:
        """Determine if an error should be stored (deduplication).

        Prevents 'error storms' where the same error is logged hundreds of times
        per minute. We only store the same error once every 'snapshot_interval'.

        Args:
            device_id: The device identifier.
            error_code: The error code (e.g., 'AUTH_001').
            error_message: The error message.

        Returns:
            True if the error should be stored, False if it's a duplicate.
        """
        current_time = time.time()
        # Create a signature for this specific error on this device
        signature = f"{device_id}:{error_code}:{error_message}"

        last_time = self._last_errors.get(signature)

        # If never seen, or seen longer ago than the interval
        if last_time is None or (current_time - last_time) >= self.snapshot_interval:
            self._last_errors[signature] = current_time
            return True

        return False

    def _update_state(
        self, device_id: str, metrics: Dict[str, Any], timestamp: float
    ) -> None:
        """Update the internal state cache."""
        self._last_states[device_id] = {
            "timestamp": timestamp,
            "metrics": metrics.copy(),
        }

    def _has_significant_change(self, old: Dict[str, Any], new: Dict[str, Any]) -> bool:
        """Check if any key metric has changed significantly."""
        # Metrics to monitor for changes
        keys_to_check = [
            "cpu_percent",
            "memory_percent",
            "disk_percent",
            "network_latency_ms",
            "error_rate",
        ]

        for key in keys_to_check:
            old_val = old.get(key)
            new_val = new.get(key)

            # If metric was missing and now present (or vice versa), that's a change
            if (old_val is None) != (new_val is None):
                return True

            if old_val is None or new_val is None:
                continue

            # Ensure values are numbers
            if not isinstance(old_val, (int, float)) or not isinstance(
                new_val, (int, float)
            ):
                continue

            # Absolute difference for small values (like error rate)
            if key == "error_rate":
                if abs(new_val - old_val) > 0.01:  # 1% absolute change in error rate
                    return True
                continue

            # Relative difference for larger values
            # Handle zero case
            if old_val == 0:
                if abs(new_val) > 1.0:  # If it goes from 0 to > 1, that's significant
                    return True
                continue

            change = abs(new_val - old_val) / abs(old_val)
            if change >= self.change_threshold:
                return True

        return False
