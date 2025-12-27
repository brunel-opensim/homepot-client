"""Unit tests for the AI failure predictor module."""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from ai.failure_predictor import FailurePredictor  # noqa: E402


class TestFailurePredictor(unittest.IsolatedAsyncioTestCase):
    """Test cases for the FailurePredictor class."""

    async def asyncSetUp(self):
        """Set up the test environment."""
        self.mock_event_store = MagicMock()
        # We patch the class so that when FailurePredictor instantiates it, it gets a mock
        self.analytics_patcher = patch("ai.failure_predictor.AIAnalyticsService")
        self.MockAnalyticsService = self.analytics_patcher.start()
        self.mock_analytics = self.MockAnalyticsService.return_value

        # Configure async methods
        self.mock_analytics.get_device_performance_trends = AsyncMock()
        self.mock_analytics.get_error_frequency_analysis = AsyncMock()
        self.mock_analytics.get_state_stability_analysis = AsyncMock()
        self.mock_analytics.get_health_score_history = AsyncMock()

        self.predictor = FailurePredictor(self.mock_event_store)
        self.device_id = "test-device-123"

    async def asyncTearDown(self):
        """Clean up the test environment."""
        self.analytics_patcher.stop()

    async def test_no_data(self):
        """Test prediction when no data is available."""
        # Setup mock to return "no_data" or empty
        self.mock_analytics.get_device_performance_trends.return_value = {
            "status": "no_data"
        }
        self.mock_analytics.get_error_frequency_analysis.return_value = {
            "status": "no_data"
        }
        self.mock_analytics.get_state_stability_analysis.return_value = {
            "status": "no_data"
        }
        self.mock_analytics.get_health_score_history.return_value = {
            "status": "no_data"
        }

        result = await self.predictor.predict_device_failure(self.device_id)

        self.assertEqual(result["risk_level"], "low")
        self.assertEqual(result["failure_probability"], 0.0)

    async def test_healthy_device(self):
        """Test prediction for a healthy device."""
        self.mock_analytics.get_device_performance_trends.return_value = {
            "metrics": {"avg_cpu_percent": 20, "avg_memory_percent": 30},
            "trends": {"cpu": "stable"},
        }
        self.mock_analytics.get_error_frequency_analysis.return_value = {
            "error_rate_per_day": 0
        }
        self.mock_analytics.get_state_stability_analysis.return_value = {
            "stability_score": 1.0
        }
        self.mock_analytics.get_health_score_history.return_value = {
            "avg_health_score": 95
        }

        result = await self.predictor.predict_device_failure(self.device_id)
        self.assertEqual(result["risk_level"], "low")
        self.assertEqual(result["failure_probability"], 0.0)

    async def test_high_cpu_risk(self):
        """Test prediction for high CPU usage."""
        self.mock_analytics.get_device_performance_trends.return_value = {
            "metrics": {"avg_cpu_percent": 95, "avg_memory_percent": 30},
            "trends": {"cpu": "increasing"},
        }
        # Mock other calls to avoid errors
        self.mock_analytics.get_error_frequency_analysis.return_value = {}
        self.mock_analytics.get_state_stability_analysis.return_value = {}
        self.mock_analytics.get_health_score_history.return_value = {}

        result = await self.predictor.predict_device_failure(self.device_id)

        # Check that High CPU Usage is identified as a risk factor
        risk_factors = [f["name"] for f in result["risk_factors"]]
        self.assertIn("High CPU Usage", risk_factors)


if __name__ == "__main__":
    unittest.main()
