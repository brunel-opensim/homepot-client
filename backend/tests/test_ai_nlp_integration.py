"""Integration tests for AI NLP context injection."""

import os
import sys
import unittest
from unittest.mock import patch

# Add ai directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../ai")))

# We need to mock the imports in api.py that might fail if dependencies aren't perfect
# But assuming the environment is set up:
from api import ChatMessage, QueryRequest, query_ai  # noqa: E402


class TestAINLPIntegration(unittest.IsolatedAsyncioTestCase):
    """Test cases for AI NLP integration."""

    async def asyncSetUp(self):
        """Set up the test environment."""
        self.device_id = "test-device-nlp"

    @patch("api.llm_service")
    @patch("api.failure_predictor")
    @patch("api.event_store")
    @patch("api.memory_service")
    async def test_query_injects_live_context(
        self, mock_memory, mock_store, mock_predictor, mock_llm
    ):
        """Test that live context is injected into the LLM prompt when device_id is present."""
        # 1. Setup Mocks
        mock_memory.query_similar.return_value = [{"content": "Old memory"}]
        mock_store.get_recent_events.return_value = [
            {"event": "metrics", "value": {"cpu": 99}}
        ]

        mock_predictor.predict_failure_risk.return_value = {
            "risk_level": "CRITICAL",
            "score": 0.95,
            "reasons": ["CPU Overheating"],
        }

        mock_llm.generate_response.return_value = "Analysis complete."

        # 2. Execute
        request = QueryRequest(
            query="What is the status?",
            device_id=self.device_id,
            history=[ChatMessage(role="user", content="Hi")],
        )

        response = await query_ai(request)

        # 3. Verify
        # Check that generate_response was called
        self.assertTrue(mock_llm.generate_response.called)

        # Check arguments passed to LLM
        call_args = mock_llm.generate_response.call_args
        context_passed = call_args[1]["context"]

        # Assertions on the context content
        self.assertIn("[CURRENT SYSTEM STATUS]", context_passed)
        self.assertIn(f"Device ID: {self.device_id}", context_passed)
        self.assertIn("Risk Level: CRITICAL", context_passed)
        self.assertIn("CPU Overheating", context_passed)
        self.assertIn("Old memory", context_passed)  # Long term memory

        # Check return value
        self.assertTrue(response["context_used"]["live_context_injected"])

    @patch("api.llm_service")
    @patch("api.failure_predictor")
    async def test_query_without_device_id(self, mock_predictor, mock_llm):
        """Test that live context is NOT injected when device_id is missing."""
        request = QueryRequest(query="General question", device_id=None)

        await query_ai(request)

        call_args = mock_llm.generate_response.call_args
        context_passed = call_args[1]["context"]

        self.assertNotIn("[CURRENT SYSTEM STATUS]", context_passed)
        mock_predictor.predict_failure_risk.assert_not_called()


if __name__ == "__main__":
    unittest.main()
