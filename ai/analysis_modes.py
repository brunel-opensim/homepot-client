"""Module for managing AI analysis modes."""

from enum import Enum
from typing import Dict


class AnalysisMode(Enum):
    """Enumeration of available analysis modes."""

    MAINTENANCE = "maintenance"
    PREDICTIVE = "predictive"
    EXECUTIVE = "executive"


class ModeManager:
    """Manages the current analysis mode for the AI."""

    def __init__(self) -> None:
        """Initialize the ModeManager with the default mode (MAINTENANCE)."""
        self.current_mode = AnalysisMode.MAINTENANCE
        self.prompts: Dict[AnalysisMode, str] = {
            AnalysisMode.MAINTENANCE: (
                "You are a technical systems analyst. Focus on technical details, "
                "troubleshooting steps, and root cause analysis. "
                "Provide specific metrics and fix recommendations."
            ),
            AnalysisMode.PREDICTIVE: (
                "You are a predictive maintenance expert. Focus on trend analysis "
                "and failure prediction. Identify potential risks and suggest "
                "preventative maintenance schedules."
            ),
            AnalysisMode.EXECUTIVE: (
                "You are an executive reporting assistant. Focus on high-level "
                "summaries, business impact, and KPIs. Avoid technical jargon "
                "unless necessary. Highlight uptime and cost implications."
            ),
        }

    def set_mode(self, mode: str | AnalysisMode) -> None:
        """Set the current analysis mode."""
        if isinstance(mode, str):
            try:
                mode = AnalysisMode(mode.lower())
            except ValueError:
                # Fallback or error? For now, keep current
                return
        self.current_mode = mode

    def get_system_prompt(self) -> str:
        """Get the system prompt for the current mode."""
        return self.prompts.get(
            self.current_mode, self.prompts[AnalysisMode.MAINTENANCE]
        )
