"""Test script to verify error logging functionality."""

import asyncio
import sys
from pathlib import Path

# Add backend src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from homepot.error_logger import log_error


async def test_error_logging():
    """Test various error logging scenarios."""
    print("Testing error logging functionality...")

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
        print("✓ Logged database error")

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
        print("✓ Logged API validation error")

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
        print("✓ Logged external service error")

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
    print("✓ Logged validation info")

    print("\n✅ All error logging tests completed!")
    print("\nChecking error_logs table...")

    # Query the database to verify
    from homepot.database import get_database_service

    db_service = await get_database_service()
    async with db_service.get_session() as session:
        from sqlalchemy import select

        from homepot.app.models.AnalyticsModel import ErrorLog

        result = await session.execute(
            select(ErrorLog).order_by(ErrorLog.timestamp.desc()).limit(10)
        )
        logs = result.scalars().all()

        print(f"\nFound {len(logs)} recent error logs:")
        for log in logs:
            print(f"  - [{log.severity.upper()}] {log.category}: {log.error_message}")
            if log.error_code:
                print(f"    Code: {log.error_code}")
            if log.device_id:
                print(f"    Device: {log.device_id}")
            print()


if __name__ == "__main__":
    asyncio.run(test_error_logging())
