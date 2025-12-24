from enum import Enum

class AnalysisMode(Enum):
    MAINTENANCE = "maintenance"
    PREDICTIVE = "predictive"
    EXECUTIVE = "executive"

class ModeManager:
    """Manages the current analysis mode for the AI."""
    
    def __init__(self):
        self.current_mode = AnalysisMode.MAINTENANCE
    
    def set_mode(self, mode: AnalysisMode):
        self.current_mode = mode
