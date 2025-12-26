"""AI Services for HOMEPOT Client.

This module provides intelligent analytics and predictive capabilities:
- Job scheduling optimization
- Device failure prediction
- Resource allocation recommendations
- Performance trend analysis

The AI system learns from 8 analytics tables:
1. device_metrics - Real-time resource usage
2. job_outcomes - Historical success/failure patterns
3. device_state_history - State transition patterns
4. error_logs - Error categorization and trends
5. configuration_history - Config change impacts
6. site_analytics - Site-level performance
7. device_analytics - Device-level statistics
8. site_operating_schedules - Operating hours and peak times
"""

from .analytics_service import AIAnalyticsService
from .failure_predictor import FailurePredictor
from .job_scheduler import PredictiveJobScheduler
from .llm_service import LLMService

__all__ = [
    "AIAnalyticsService",
    "PredictiveJobScheduler",
    "FailurePredictor",
    "LLMService",
]
