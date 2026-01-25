"""Integration tests for AI NLP context injection."""

import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

# We need to mock the imports in api.py that might fail if dependencies aren't perfect
# But assuming the environment is set up:
from ai.api import ChatMessage, QueryRequest, query_ai  # noqa: E402


class TestAINLPIntegration(unittest.IsolatedAsyncioTestCase):
    """Test cases for AI NLP integration."""

    async def asyncSetUp(self):
        """Set up the test environment."""
        self.device_id = "test-device-nlp"

    @patch("ai.api.llm_service")
    @patch("ai.api.failure_predictor")
    @patch("ai.api.event_store")
    @patch("ai.api.memory_service")
    async def test_query_injects_live_context(
        self, mock_memory, mock_store, mock_predictor, mock_llm
    ):
        """Test that live context is injected into the LLM prompt when device_id is present."""
        # 1. Setup Mocks
        mock_memory.query_similar.return_value = [{"content": "Old memory"}]
        mock_store.get_recent_events.return_value = [
            {"event": "metrics", "value": {"cpu": 99}}
        ]

        # Configure AsyncMock for async method
        mock_predictor.predict_device_failure = AsyncMock(
            return_value={
                "risk_level": "CRITICAL",
                "score": 0.95,
                "reasons": ["CPU Overheating"],
                "risk_factors": [{"name": "CPU Overheating"}],
            }
        )

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

    @patch("ai.api.llm_service")
    @patch("ai.api.failure_predictor")
    async def test_query_without_device_id(self, mock_predictor, mock_llm):
        """Test that live context is NOT injected when device_id is missing."""
        # Configure AsyncMock
        mock_predictor.predict_device_failure = AsyncMock()

        request = QueryRequest(query="General question", device_id=None)

        await query_ai(request)

        call_args = mock_llm.generate_response.call_args
        context_passed = call_args[1]["context"]

        # Should have global context but NOT specific device context
        self.assertIn("[CURRENT SYSTEM STATUS]", context_passed)
        self.assertNotIn(f"Device ID: {self.device_id}", context_passed)
        mock_predictor.predict_device_failure.assert_not_called()


if __name__ == "__main__":
    unittest.main()
