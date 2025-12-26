"""Failure prediction module for analyzing device metrics and assessing risk."""

import statistics
from datetime import datetime
from typing import Dict

from event_store import EventStore


class FailurePredictor:
    """Predicts device failure risks based on historical metrics."""

    def __init__(self, event_store: EventStore) -> None:
        """Initialize the FailurePredictor with an event store."""
        self.event_store = event_store

    def predict_failure_risk(self, device_id: str) -> Dict:
        """Analyzes metrics to predict potential failures.

        Returns a risk assessment dictionary.
        """
        # Get recent events from the store
        events = self.event_store.get_recent_events(device_id, limit=100)

        # Filter for device metrics (EventStore returns events for specific device)
        # We just need to ensure they are metrics updates
        device_events = [e for e in events if e.get("event") == "metrics_update"]

        if not device_events:
            return {
                "risk_level": "UNKNOWN",
                "score": 0.0,
                "reasons": ["No recent data available for analysis"],
                "timestamp": datetime.now().isoformat(),
            }

        # Extract metrics safely
        cpu_readings = []
        memory_readings = []
        disk_readings = []

        for e in device_events:
            data = e.get("value", {})
            if "cpu_percent" in data:
                cpu_readings.append(float(data["cpu_percent"]))
            if "memory_percent" in data:
                memory_readings.append(float(data["memory_percent"]))
            if "disk_percent" in data:
                disk_readings.append(float(data["disk_percent"]))

        risk_score = 0.0
        reasons = []

        # CPU Analysis
        if cpu_readings:
            avg_cpu = statistics.mean(cpu_readings)
            if avg_cpu > 90:
                risk_score += 0.7
                reasons.append(f"Critical average CPU usage ({avg_cpu:.1f}%)")
            elif avg_cpu > 75:
                risk_score += 0.3
                reasons.append(f"High average CPU usage ({avg_cpu:.1f}%)")

            # Simple trend detection (comparing last 3 vs first 3 if enough data)
            if len(cpu_readings) >= 6:
                recent_avg = statistics.mean(cpu_readings[-3:])
                older_avg = statistics.mean(cpu_readings[:3])
                if recent_avg > older_avg * 1.2:  # 20% increase
                    risk_score += 0.2
                    reasons.append("CPU usage is trending upwards significantly")

        # Memory Analysis
        if memory_readings:
            avg_mem = statistics.mean(memory_readings)
            if avg_mem > 90:
                risk_score += 0.5
                reasons.append(f"Critical average Memory usage ({avg_mem:.1f}%)")
            elif avg_mem > 80:
                risk_score += 0.3
                reasons.append(f"High average Memory usage ({avg_mem:.1f}%)")

        # Disk Analysis
        if disk_readings:
            max_disk = max(disk_readings)
            if max_disk > 95:
                risk_score += 0.6
                reasons.append(f"Critical Disk usage detected ({max_disk:.1f}%)")
            elif max_disk > 85:
                risk_score += 0.3
                reasons.append(f"High Disk usage detected ({max_disk:.1f}%)")

        # Cap score at 1.0
        risk_score = min(risk_score, 1.0)

        # Determine Risk Level
        if risk_score >= 0.7:
            risk_level = "CRITICAL"
        elif risk_score >= 0.4:
            risk_level = "WARNING"
        else:
            risk_level = "HEALTHY"

        return {
            "device_id": device_id,
            "risk_level": risk_level,
            "score": round(risk_score, 2),
            "reasons": reasons,
            "analyzed_samples": len(device_events),
            "timestamp": datetime.now().isoformat(),
        }
