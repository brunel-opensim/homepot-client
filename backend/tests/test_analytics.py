"""
Tests for Analytics Infrastructure.

Basic tests for analytics models, endpoints, and middleware functionality.
These tests verify the structure and basic functionality without deep integration.
"""

from homepot.app.models.AnalyticsModel import (
    APIRequestLog,
    DeviceStateHistory,
    ErrorLog,
    JobOutcome,
    UserActivity,
)


class TestAnalyticsModels:
    """Test analytics data models can be imported and have correct table names."""

    def test_api_request_log_table(self):
        """Test APIRequestLog model table name."""
        assert APIRequestLog.__tablename__ == "api_request_logs"

    def test_device_state_history_table(self):
        """Test DeviceStateHistory model table name."""
        assert DeviceStateHistory.__tablename__ == "device_state_history"

    def test_job_outcome_table(self):
        """Test JobOutcome model table name."""
        assert JobOutcome.__tablename__ == "job_outcomes"

    def test_error_log_table(self):
        """Test ErrorLog model table name."""
        assert ErrorLog.__tablename__ == "error_logs"

    def test_user_activity_table(self):
        """Test UserActivity model table name."""
        assert UserActivity.__tablename__ == "user_activities"


class TestAnalyticsEndpointStructure:
    """Test analytics endpoint structure and imports."""

    def test_analytics_endpoint_imports(self):
        """Test that analytics endpoints can be imported."""
        from homepot.app.api.API_v1.Endpoints import AnalyticsEndpoint

        assert hasattr(AnalyticsEndpoint, "router")
        assert AnalyticsEndpoint.router is not None

    def test_analytics_models_imports(self):
        """Test that all analytics models can be imported."""
        from homepot.app.models.AnalyticsModel import (
            APIRequestLog,
            DeviceStateHistory,
            ErrorLog,
            JobOutcome,
            UserActivity,
        )

        assert APIRequestLog is not None
        assert DeviceStateHistory is not None
        assert JobOutcome is not None
        assert ErrorLog is not None
        assert UserActivity is not None

    def test_middleware_imports(self):
        """Test that analytics middleware can be imported."""
        from homepot.app.middleware.analytics import AnalyticsMiddleware

        assert AnalyticsMiddleware is not None
        assert hasattr(AnalyticsMiddleware, "dispatch")
