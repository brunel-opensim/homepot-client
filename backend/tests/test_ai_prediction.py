"""Unit tests for the AI failure predictor module."""

import os
import sys
import unittest
from unittest.mock import MagicMock

# Add ai directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../ai")))

from failure_predictor import FailurePredictor  # noqa: E402


class TestFailurePredictor(unittest.TestCase):
    """Test cases for the FailurePredictor class."""

    def setUp(self):
        """Set up the test environment."""
        self.mock_event_store = MagicMock()
        self.predictor = FailurePredictor(self.mock_event_store)
        self.device_id = "test-device-123"

    def test_no_data(self):
        """Test prediction when no data is available."""
        self.mock_event_store.get_recent_events.return_value = []
        result = self.predictor.predict_failure_risk(self.device_id)

        self.assertEqual(result["risk_level"], "UNKNOWN")
        self.assertEqual(result["score"], 0.0)

    def test_healthy_device(self):
        """Test prediction for a healthy device."""
        events = [
            {
                "event": "metrics_update",
                "value": {"cpu_percent": 20, "memory_percent": 30, "disk_percent": 40},
            }
            for _ in range(10)
        ]
        self.mock_event_store.get_recent_events.return_value = events

        result = self.predictor.predict_failure_risk(self.device_id)
        self.assertEqual(result["risk_level"], "HEALTHY")
        self.assertEqual(result["score"], 0.0)

    def test_high_cpu_risk(self):
        """Test prediction for high CPU usage."""
        events = [
            {
                "event": "metrics_update",
                "value": {"cpu_percent": 95, "memory_percent": 30, "disk_percent": 40},
            }
            for _ in range(10)
        ]
        self.mock_event_store.get_recent_events.return_value = events

        result = self.predictor.predict_failure_risk(self.device_id)
        self.assertIn("CRITICAL", result["risk_level"])
        self.assertGreater(result["score"], 0.4)
        self.assertTrue(any("CPU" in r for r in result["reasons"]))

    def test_cpu_trend_risk(self):
        """Test prediction for increasing CPU trend."""
        # Increasing CPU usage: 10, 20, 30, 40, 50, 60
        events = [
            {
                "event": "metrics_update",
                "value": {
                    "cpu_percent": i * 10,
                    "memory_percent": 30,
                    "disk_percent": 40,
                },
            }
            for i in range(1, 7)
        ]
        self.mock_event_store.get_recent_events.return_value = events

        result = self.predictor.predict_failure_risk(self.device_id)
        # Should detect trend
        self.assertTrue(any("trending" in r for r in result["reasons"]))


if __name__ == "__main__":
    unittest.main()
