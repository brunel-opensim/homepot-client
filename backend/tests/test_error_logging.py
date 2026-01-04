"""Test script to verify error logging functionality."""

import pytest
from sqlalchemy import select

from homepot.app.models.AnalyticsModel import ErrorLog
from homepot.database import get_database_service
from homepot.error_logger import log_error


@pytest.mark.asyncio
async def test_error_logging():
    """Test various error logging scenarios."""
    # Test 1: Database error
    try:
        raise Exception("Simulated database connection failure")
    except Exception as e:
        await log_error(
            category="database",
            severity="error",
            error_message="Database connection failed during query execution",
            exception=e,
            error_code="DB_CONN_001",
            context={"query": "SELECT * FROM test_table", "retry_count": 3},
        )

    # Test 2: API error
    try:
        raise ValueError("Invalid request parameter")
    except Exception as e:
        await log_error(
            category="api",
            severity="warning",
            error_message="Invalid parameter in API request",
            exception=e,
            error_code="API_VALIDATION_001",
            endpoint="/api/v1/test",
            user_id="test-user-123",
            context={"parameter": "invalid_value", "expected": "string"},
        )

    # Test 3: External service error
    try:
        raise ConnectionError("Payment gateway timeout")
    except Exception as e:
        await log_error(
            category="external_service",
            severity="critical",
            error_message="Payment gateway connection timeout",
            exception=e,
            error_code="EXT_SERVICE_TIMEOUT",
            device_id="pos-terminal-001",
            context={
                "service": "payment_gateway",
                "timeout_seconds": 30,
                "endpoint": "https://payment-gateway.example.com/charge",
            },
        )

    # Test 4: Validation error (no exception)
    await log_error(
        category="validation",
        severity="info",
        error_message="Configuration validation warning",
        error_code="CONFIG_VAL_001",
        context={
            "config_key": "max_retries",
            "provided_value": 100,
            "max_allowed": 10,
            "action": "using_default",
        },
    )

    # Query the database to verify
    db_service = await get_database_service()
    async with db_service.get_session() as session:
        result = await session.execute(
            select(ErrorLog).order_by(ErrorLog.timestamp.desc()).limit(10)
        )
        logs = result.scalars().all()

        # Verify we have logs
        assert len(logs) > 0

        # Verify specific logs exist (checking the most recent ones)
        messages = [log.error_message for log in logs]
        assert "Configuration validation warning" in messages
        assert "Payment gateway connection timeout" in messages
