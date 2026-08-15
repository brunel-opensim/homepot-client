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


class TestErrorLogContract:
    """Frontend-to-backend error analytics contract.

    The frontend posts {category, severity, error_message, context} to
    /api/v1/analytics/error. The backend must persist error_message and
    context unchanged. The legacy frontend fields `message`/`extra_data`
    must not be accepted as substitutes.
    """

    PAYLOAD = {
        "category": "external_service",
        "severity": "error",
        "error_message": "Payment gateway timeout",
        "context": {"page_url": "/checkout"},
    }

    def _auth_header(self, email: str = "analytics-test@example.com") -> dict:
        from homepot.app.auth_utils import create_access_token

        token = create_access_token({"sub": email})
        return {"Authorization": f"Bearer {token}"}

    def _ensure_tables(self) -> None:
        from homepot.app.models.AnalyticsModel import ErrorLog  # noqa: F401
        from homepot.database import sync_engine
        from homepot.models import Base

        Base.metadata.create_all(bind=sync_engine)

    def test_error_message_and_context_persist(self, client) -> None:
        from homepot.app.models.AnalyticsModel import ErrorLog
        from homepot.database import SessionLocal

        self._ensure_tables()

        resp = client.post(
            "/api/v1/analytics/error",
            json=self.PAYLOAD,
            headers=self._auth_header(),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["success"] is True

        db = SessionLocal()
        log = None
        try:
            log = (
                db.query(ErrorLog)
                .filter(ErrorLog.error_message == self.PAYLOAD["error_message"])
                .order_by(ErrorLog.id.desc())
                .first()
            )
            assert log is not None
            assert log.error_message == "Payment gateway timeout"
            assert log.category == "external_service"
            assert log.severity == "error"
            assert log.context == {"page_url": "/checkout"}
        finally:
            if log is not None:
                db.delete(log)
                db.commit()
            db.close()

    def test_legacy_message_and_extra_data_are_not_persisted(self, client) -> None:
        from homepot.app.models.AnalyticsModel import ErrorLog
        from homepot.database import SessionLocal

        self._ensure_tables()

        # Old frontend payload using message/extra_data must not be treated
        # as the error_message/context fields.
        legacy_payload = {
            "category": "client_error",
            "severity": "error",
            "message": "Should not be stored as error_message",
            "extra_data": {"page_url": "/legacy"},
        }

        resp = client.post(
            "/api/v1/analytics/error",
            json=legacy_payload,
            headers=self._auth_header(),
        )
        assert resp.status_code == 201, resp.text

        db = SessionLocal()
        log = None
        try:
            log = (
                db.query(ErrorLog)
                .filter(ErrorLog.category == "client_error")
                .order_by(ErrorLog.id.desc())
                .first()
            )
            assert log is not None
            # The legacy fields must not leak into the canonical columns.
            assert log.error_message != legacy_payload["message"]
            assert log.context != legacy_payload["extra_data"]
        finally:
            if log is not None:
                db.delete(log)
                db.commit()
            db.close()
