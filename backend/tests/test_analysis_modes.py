"""Unit tests for the Analysis Modes module."""

import os
import sys
import unittest

# Add ai directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../ai")))

from analysis_modes import AnalysisMode, ModeManager  # noqa: E402


class TestAnalysisModes(unittest.TestCase):
    """Test cases for the ModeManager class."""

    def setUp(self):
        """Set up the test environment."""
        self.manager = ModeManager()

    def test_default_mode(self):
        """Test that the default mode is MAINTENANCE."""
        self.assertEqual(self.manager.current_mode, AnalysisMode.MAINTENANCE)

    def test_set_mode_valid(self):
        """Test setting a valid mode."""
        self.manager.set_mode("predictive")
        self.assertEqual(self.manager.current_mode, AnalysisMode.PREDICTIVE)

        self.manager.set_mode("executive")
        self.assertEqual(self.manager.current_mode, AnalysisMode.EXECUTIVE)

    def test_set_mode_invalid(self):
        """Test setting an invalid mode (should remain unchanged)."""
        self.manager.set_mode("predictive")
        self.manager.set_mode("invalid_mode")
        self.assertEqual(self.manager.current_mode, AnalysisMode.PREDICTIVE)

    def test_prompts_contain_context_instructions(self):
        """Test that all prompts contain the [CURRENT SYSTEM STATUS] instruction."""
        for mode in AnalysisMode:
            self.manager.set_mode(mode)
            prompt = self.manager.get_system_prompt()
            self.assertIn("[CURRENT SYSTEM STATUS]", prompt)
            self.assertIn("CRITICAL RULE", prompt)


if __name__ == "__main__":
    unittest.main()
