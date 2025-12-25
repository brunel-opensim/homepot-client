"""Module for managing AI analysis modes."""

from enum import Enum


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

    def set_mode(self, mode: AnalysisMode) -> None:
        """Set the current analysis mode."""
        self.current_mode = mode
