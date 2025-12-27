"""Tests for AI Context Builder."""

import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the workspace root to sys.path so we can import 'ai' as a package
current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from ai.context_builder import ContextBuilder  # noqa: E402

from homepot.app.models.AnalyticsModel import (  # noqa: E402
    APIRequestLog,
    ConfigurationHistory,
    DeviceStateHistory,
    ErrorLog,
    JobOutcome,
    PushNotificationLog,
    UserActivity,
)
from homepot.models import AuditLog, User  # noqa: E402


@pytest.mark.asyncio
async def test_get_job_context_specific_id():
    """Test retrieving context for a specific job ID."""
    # Mock the database service and session
    mock_db_service = MagicMock()
    mock_session = AsyncMock()
    mock_db_service.get_session.return_value.__aenter__.return_value = mock_session

    # Mock the result
    mock_job = JobOutcome(
        job_id="job-123",
        job_type="update",
        status="failed",
        error_message="Timeout",
        duration_ms=5000,
    )

    # Setup the execute result
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_job
    mock_session.execute.return_value = mock_result

    with patch(
        "ai.context_builder.get_database_service",
        new=AsyncMock(return_value=mock_db_service),
    ):
        context = await ContextBuilder.get_job_context(job_id="job-123")

        assert "[JOB DETAILS]" in context
        assert "ID: job-123" in context
        assert "Error: Timeout" in context


@pytest.mark.asyncio
async def test_get_job_context_recent_failures():
    """Test retrieving context for recent failed jobs."""
    # Mock the database service and session
    mock_db_service = MagicMock()
    mock_session = AsyncMock()
    mock_db_service.get_session.return_value.__aenter__.return_value = mock_session

    # Mock the result
    mock_job = JobOutcome(
        timestamp=datetime.utcnow(),
        job_type="update",
        status="failed",
        error_message="Connection refused",
    )

    # Setup the execute result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_job]
    mock_session.execute.return_value = mock_result

    with patch(
        "ai.context_builder.get_database_service",
        new=AsyncMock(return_value=mock_db_service),
    ):
        context = await ContextBuilder.get_job_context()

        assert "[RECENT FAILED JOBS]" in context
        assert "Connection refused" in context


@pytest.mark.asyncio
async def test_get_job_context_no_failures():
    """Test retrieving context when there are no failed jobs."""
    # Mock the database service and session
    mock_db_service = MagicMock()
    mock_session = AsyncMock()
    mock_db_service.get_session.return_value.__aenter__.return_value = mock_session

    # Setup the execute result (empty list)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    with patch(
        "ai.context_builder.get_database_service",
        new=AsyncMock(return_value=mock_db_service),
    ):
        context = await ContextBuilder.get_job_context()

        assert "No failed jobs" in context


@pytest.mark.asyncio
async def test_get_error_context():
    """Test retrieving context for system errors."""
    # Mock the database service and session
    mock_db_service = MagicMock()
    mock_session = AsyncMock()
    mock_db_service.get_session.return_value.__aenter__.return_value = mock_session

    # Mock the result
    mock_error = ErrorLog(
        timestamp=datetime.utcnow(),
        severity="critical",
        category="database",
        error_message="Deadlock detected",
    )

    # Setup the execute result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_error]
    mock_session.execute.return_value = mock_result

    with patch(
        "ai.context_builder.get_database_service",
        new=AsyncMock(return_value=mock_db_service),
    ):
        context = await ContextBuilder.get_error_context(device_id="device-123")

        assert "[RECENT SYSTEM ERRORS]" in context
        assert "Deadlock detected" in context


@pytest.mark.asyncio
async def test_get_error_context_no_errors():
    """Test retrieving context when there are no errors."""
    # Mock the database service and session
    mock_db_service = MagicMock()
    mock_session = AsyncMock()
    mock_db_service.get_session.return_value.__aenter__.return_value = mock_session

    # Setup the execute result (empty list)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    with patch(
        "ai.context_builder.get_database_service",
        new=AsyncMock(return_value=mock_db_service),
    ):
        context = await ContextBuilder.get_error_context(device_id="device-123")

        assert "No recent system errors" in context


@pytest.mark.asyncio
async def test_get_config_context():
    """Test retrieving context for configuration changes."""
    # Mock the database service and session
    mock_db_service = MagicMock()
    mock_session = AsyncMock()
    mock_db_service.get_session.return_value.__aenter__.return_value = mock_session

    # Mock the result
    mock_change = ConfigurationHistory(
        timestamp=datetime.utcnow(),
        parameter_name="max_connections",
        changed_by="admin",
        change_type="manual",
    )

    # Setup the execute result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_change]
    mock_session.execute.return_value = mock_result

    with patch(
        "ai.context_builder.get_database_service",
        new=AsyncMock(return_value=mock_db_service),
    ):
        context = await ContextBuilder.get_config_context(device_id="device-123")

        assert "[RECENT CONFIG CHANGES]" in context
        assert "max_connections" in context
        assert "admin" in context


@pytest.mark.asyncio
async def test_get_config_context_no_changes():
    """Test retrieving context when there are no config changes."""
    # Mock the database service and session
    mock_db_service = MagicMock()
    mock_session = AsyncMock()
    mock_db_service.get_session.return_value.__aenter__.return_value = mock_session

    # Setup the execute result (empty list)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    with patch(
        "ai.context_builder.get_database_service",
        new=AsyncMock(return_value=mock_db_service),
    ):
        context = await ContextBuilder.get_config_context(device_id="device-123")

        assert "No recent configuration changes" in context


@pytest.mark.asyncio
async def test_get_audit_context():
    """Test retrieving context for audit logs."""
    # Mock the database service and session
    mock_db_service = MagicMock()
    mock_session = AsyncMock()
    mock_db_service.get_session.return_value.__aenter__.return_value = mock_session

    # Mock the result
    mock_log = AuditLog(
        created_at=datetime.utcnow(),
        event_type="user_login",
        description="User logged in successfully",
    )

    # Setup the execute result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_log]
    mock_session.execute.return_value = mock_result

    with patch(
        "ai.context_builder.get_database_service",
        new=AsyncMock(return_value=mock_db_service),
    ):
        context = await ContextBuilder.get_audit_context(device_id="device-123")

        assert "[RECENT AUDIT LOGS]" in context
        assert "user_login" in context
        assert "User logged in successfully" in context


@pytest.mark.asyncio
async def test_get_audit_context_no_logs():
    """Test retrieving context when there are no audit logs."""
    # Mock the database service and session
    mock_db_service = MagicMock()
    mock_session = AsyncMock()
    mock_db_service.get_session.return_value.__aenter__.return_value = mock_session

    # Setup the execute result (empty list)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    with patch(
        "ai.context_builder.get_database_service",
        new=AsyncMock(return_value=mock_db_service),
    ):
        context = await ContextBuilder.get_audit_context(device_id="device-123")

        assert "No recent audit logs" in context


@pytest.mark.asyncio
async def test_get_api_context():
    """Test retrieving context for API errors."""
    # Mock the database service and session
    mock_db_service = MagicMock()
    mock_session = AsyncMock()
    mock_db_service.get_session.return_value.__aenter__.return_value = mock_session

    # Mock the result
    mock_log = APIRequestLog(
        timestamp=datetime.utcnow(),
        method="POST",
        endpoint="/api/v1/sync",
        status_code=500,
        response_time_ms=120.5,
    )

    # Setup the execute result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_log]
    mock_session.execute.return_value = mock_result

    with patch(
        "ai.context_builder.get_database_service",
        new=AsyncMock(return_value=mock_db_service),
    ):
        context = await ContextBuilder.get_api_context()

        assert "[RECENT API ERRORS]" in context
        assert "POST /api/v1/sync" in context
        assert "(500)" in context


@pytest.mark.asyncio
async def test_get_api_context_no_errors():
    """Test retrieving context when there are no API errors."""
    # Mock the database service and session
    mock_db_service = MagicMock()
    mock_session = AsyncMock()
    mock_db_service.get_session.return_value.__aenter__.return_value = mock_session

    # Setup the execute result (empty list)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    with patch(
        "ai.context_builder.get_database_service",
        new=AsyncMock(return_value=mock_db_service),
    ):
        context = await ContextBuilder.get_api_context()

        assert "No recent API errors" in context


@pytest.mark.asyncio
async def test_get_state_context():
    """Test retrieving context for device state changes."""
    # Mock the database service and session
    mock_db_service = MagicMock()
    mock_session = AsyncMock()
    mock_db_service.get_session.return_value.__aenter__.return_value = mock_session

    # Mock the result
    mock_change = DeviceStateHistory(
        timestamp=datetime.utcnow(),
        previous_state="online",
        new_state="offline",
        reason="Heartbeat timeout",
    )

    # Setup the execute result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_change]
    mock_session.execute.return_value = mock_result

    with patch(
        "ai.context_builder.get_database_service",
        new=AsyncMock(return_value=mock_db_service),
    ):
        context = await ContextBuilder.get_state_context(device_id="device-123")

        assert "[RECENT STATE CHANGES]" in context
        assert "online -> offline" in context
        assert "Heartbeat timeout" in context


@pytest.mark.asyncio
async def test_get_state_context_no_changes():
    """Test retrieving context when there are no state changes."""
    # Mock the database service and session
    mock_db_service = MagicMock()
    mock_session = AsyncMock()
    mock_db_service.get_session.return_value.__aenter__.return_value = mock_session

    # Setup the execute result (empty list)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    with patch(
        "ai.context_builder.get_database_service",
        new=AsyncMock(return_value=mock_db_service),
    ):
        context = await ContextBuilder.get_state_context(device_id="device-123")

        assert "No recent device state changes" in context


@pytest.mark.asyncio
async def test_get_push_context():
    """Test retrieving context for push notifications."""
    # Mock the database service and session
    mock_db_service = MagicMock()
    mock_session = AsyncMock()
    mock_db_service.get_session.return_value.__aenter__.return_value = mock_session

    # Mock the result
    mock_log = PushNotificationLog(
        sent_at=datetime.utcnow(),
        provider="fcm",
        status="failed",
        error_message="Invalid token",
    )

    # Setup the execute result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_log]
    mock_session.execute.return_value = mock_result

    with patch(
        "ai.context_builder.get_database_service",
        new=AsyncMock(return_value=mock_db_service),
    ):
        context = await ContextBuilder.get_push_context(device_id="device-123")

        assert "[RECENT PUSH NOTIFICATIONS]" in context
        assert "fcm -> (FAILED: Invalid token)" in context


@pytest.mark.asyncio
async def test_get_push_context_no_logs():
    """Test retrieving context when there are no push logs."""
    # Mock the database service and session
    mock_db_service = MagicMock()
    mock_session = AsyncMock()
    mock_db_service.get_session.return_value.__aenter__.return_value = mock_session

    # Setup the execute result (empty list)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    with patch(
        "ai.context_builder.get_database_service",
        new=AsyncMock(return_value=mock_db_service),
    ):
        context = await ContextBuilder.get_push_context(device_id="device-123")

        assert "No recent push notifications" in context


@pytest.mark.asyncio
async def test_get_user_context():
    """Test retrieving context for user activity."""
    # Mock the database service and session
    mock_db_service = MagicMock()
    mock_session = AsyncMock()
    mock_db_service.get_session.return_value.__aenter__.return_value = mock_session

    # Mock the user metadata result
    mock_user = User(
        id=1,
        username="testuser",
        is_admin=True,
        is_active=True,
    )

    # Mock the activity result
    mock_activity = UserActivity(
        timestamp=datetime.utcnow(),
        activity_type="page_view",
        page_url="/dashboard",
        user_id="1",
    )

    # Setup the execute results
    # First call is for User metadata (scalar_one_or_none)
    # Second call is for UserActivity (scalars().all())
    mock_result_user = MagicMock()
    mock_result_user.scalar_one_or_none.return_value = mock_user

    mock_result_activity = MagicMock()
    mock_result_activity.scalars.return_value.all.return_value = [mock_activity]

    # We need to mock execute to return different results based on the query
    # Or simply return a sequence of results
    mock_session.execute.side_effect = [mock_result_user, mock_result_activity]

    with patch(
        "ai.context_builder.get_database_service",
        new=AsyncMock(return_value=mock_db_service),
    ):
        context = await ContextBuilder.get_user_context(user_id="1")

        assert "[USER PROFILE]" in context
        assert "Username: testuser" in context
        assert "Role: Admin" in context
        assert "[RECENT USER ACTIVITY]" in context
        assert "page_view on /dashboard" in context


@pytest.mark.asyncio
async def test_get_user_context_no_activity():
    """Test retrieving context when there is no user activity."""
    # Mock the database service and session
    mock_db_service = MagicMock()
    mock_session = AsyncMock()
    mock_db_service.get_session.return_value.__aenter__.return_value = mock_session

    # Mock the user metadata result
    mock_user = User(
        id=1,
        username="testuser",
        is_admin=False,
        is_active=True,
    )

    # Setup the execute results
    mock_result_user = MagicMock()
    mock_result_user.scalar_one_or_none.return_value = mock_user

    mock_result_activity = MagicMock()
    mock_result_activity.scalars.return_value.all.return_value = []

    mock_session.execute.side_effect = [mock_result_user, mock_result_activity]

    with patch(
        "ai.context_builder.get_database_service",
        new=AsyncMock(return_value=mock_db_service),
    ):
        context = await ContextBuilder.get_user_context(user_id="1")

        assert "[USER PROFILE]" in context
        assert "Role: User" in context
        assert "No recent user activity" not in context  # It just returns the profile
