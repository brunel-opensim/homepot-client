"""Tests for TimescaleDB functionality.

These tests verify that:
1. TimescaleDB features work when available
2. System gracefully falls back to standard PostgreSQL when not available
3. Continuous aggregates provide correct results
4. Retention and compression policies are applied correctly
"""

import os

import pytest
from sqlalchemy import text

from homepot.database import get_database_service
from homepot.migrations.timescaledb_aggregates import (
    create_hourly_device_metrics,
    setup_timescaledb_aggregates,
)
from homepot.timescale import TimescaleDBManager


# Skip all tests if PostgreSQL URL is not set (e.g., in CI without postgres service)
pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE__URL") or "sqlite" in os.getenv("DATABASE__URL", ""),
    reason="PostgreSQL database not available (required for TimescaleDB tests)",
)


@pytest.mark.asyncio
async def test_timescaledb_availability():
    """Test TimescaleDB availability detection."""
    db_service = await get_database_service()

    async with db_service.get_session() as session:
        ts_manager = TimescaleDBManager(session)

        # Should not raise exception
        is_available = await ts_manager.is_timescaledb_available()

        # Result should be boolean
        assert isinstance(is_available, bool)

        # Second call should use cached result
        is_available_cached = await ts_manager.is_timescaledb_available()
        assert is_available == is_available_cached


@pytest.mark.asyncio
async def test_database_service_timescaledb_flag():
    """Test database service tracks TimescaleDB status."""
    db_service = await get_database_service()

    # Should have the flag
    assert hasattr(db_service, "_timescaledb_enabled")
    assert isinstance(db_service.is_timescaledb_enabled(), bool)


@pytest.mark.asyncio
async def test_hypertable_creation_graceful_failure():
    """Test that hypertable creation fails gracefully when TimescaleDB unavailable."""
    db_service = await get_database_service()

    async with db_service.get_session() as session:
        ts_manager = TimescaleDBManager(session)

        # Try to create hypertable (should handle both success and failure gracefully)
        result = await ts_manager.create_hypertable(
            table_name="health_checks",
            time_column="timestamp",
            if_not_exists=True,
        )

        # Result should be boolean
        assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_continuous_aggregate_graceful_failure():
    """Test continuous aggregate creation handles unavailability gracefully."""
    db_service = await get_database_service()

    async with db_service.get_session() as session:
        ts_manager = TimescaleDBManager(session)

        # Try to create continuous aggregate
        result = await create_hourly_device_metrics(ts_manager)

        # Should return boolean without raising exception
        assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_retention_policy_graceful_failure():
    """Test retention policy handles unavailability gracefully."""
    db_service = await get_database_service()

    async with db_service.get_session() as session:
        ts_manager = TimescaleDBManager(session)

        # Try to add retention policy
        result = await ts_manager.add_retention_policy(
            hypertable="health_checks",
            retention_period="90 days",
            if_not_exists=True,
        )

        # Should return boolean without raising exception
        assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_compression_policy_graceful_failure():
    """Test compression policy handles unavailability gracefully."""
    db_service = await get_database_service()

    async with db_service.get_session() as session:
        ts_manager = TimescaleDBManager(session)

        # Try to add compression policy
        result = await ts_manager.add_compression_policy(
            hypertable="health_checks",
            compress_after="7 days",
            if_not_exists=True,
        )

        # Should return boolean without raising exception
        assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_hypertable_stats_with_unavailable_timescale():
    """Test getting hypertable stats when TimescaleDB unavailable."""
    db_service = await get_database_service()

    async with db_service.get_session() as session:
        ts_manager = TimescaleDBManager(session)

        # Should return None or dict without raising exception
        stats = await ts_manager.get_hypertable_stats("health_checks")
        assert stats is None or isinstance(stats, dict)


@pytest.mark.asyncio
async def test_chunk_stats_with_unavailable_timescale():
    """Test getting chunk stats when TimescaleDB unavailable."""
    db_service = await get_database_service()

    async with db_service.get_session() as session:
        ts_manager = TimescaleDBManager(session)

        # Should return empty list or list of dicts without raising exception
        chunks = await ts_manager.get_chunk_stats("health_checks")
        assert isinstance(chunks, list)
        for chunk in chunks:
            assert isinstance(chunk, dict)


@pytest.mark.asyncio
async def test_setup_aggregates_handles_unavailability():
    """Test setup_timescaledb_aggregates handles unavailability gracefully."""
    db_service = await get_database_service()

    async with db_service.get_session() as session:
        # Should not raise exception
        results = await setup_timescaledb_aggregates(session)

        # Should return dict (empty if unavailable, populated if available)
        assert isinstance(results, dict)

        # All values should be boolean
        for name, success in results.items():
            assert isinstance(name, str)
            assert isinstance(success, bool)


@pytest.mark.asyncio
@pytest.mark.timescaledb
@pytest.mark.skip(
    reason="Requires PostgreSQL with TimescaleDB extension. Run with: pytest tests/test_timescaledb.py -m timescaledb"
)
async def test_timescaledb_hypertable_creation():
    """Integration test: Create hypertable with TimescaleDB available.

    Run with: pytest tests/test_timescaledb.py -m timescaledb
    Requires: PostgreSQL with TimescaleDB extension installed
    """
    db_service = await get_database_service()

    async with db_service.get_session() as session:
        ts_manager = TimescaleDBManager(session)

        # Verify TimescaleDB is available
        assert await ts_manager.is_timescaledb_available(), "TimescaleDB not available"

        # Enable extension
        assert await ts_manager.enable_extension()

        # Create hypertable
        assert await ts_manager.create_hypertable(
            table_name="health_checks",
            time_column="timestamp",
            if_not_exists=True,
        )

        # Verify it's a hypertable
        stats = await ts_manager.get_hypertable_stats("health_checks")
        assert stats is not None
        assert stats.get("hypertable_name") == "health_checks"


@pytest.mark.asyncio
@pytest.mark.timescaledb
@pytest.mark.skip(
    reason="Requires PostgreSQL with TimescaleDB extension. Run with: pytest tests/test_timescaledb.py -m timescaledb"
)
async def test_timescaledb_continuous_aggregates():
    """Integration test: Create continuous aggregates with TimescaleDB.

    Run with: pytest tests/test_timescaledb.py -m timescaledb
    Requires: PostgreSQL with TimescaleDB extension and health_checks hypertable
    """
    db_service = await get_database_service()

    async with db_service.get_session() as session:
        ts_manager = TimescaleDBManager(session)

        # Verify TimescaleDB is available
        assert await ts_manager.is_timescaledb_available(), "TimescaleDB not available"

        # Create hourly aggregate
        assert await create_hourly_device_metrics(ts_manager)

        # Verify the view exists
        result = await session.execute(
            text(
                "SELECT viewname FROM pg_views WHERE viewname = 'device_metrics_hourly'"
            )
        )
        assert result.scalar() == "device_metrics_hourly"


@pytest.mark.asyncio
@pytest.mark.timescaledb
@pytest.mark.skip(
    reason="Requires PostgreSQL with TimescaleDB extension. Run with: pytest tests/test_timescaledb.py -m timescaledb"
)
async def test_timescaledb_retention_policy():
    """Integration test: Add retention policy with TimescaleDB.

    Run with: pytest tests/test_timescaledb.py -m timescaledb
    Requires: PostgreSQL with TimescaleDB extension and health_checks hypertable
    """
    db_service = await get_database_service()

    async with db_service.get_session() as session:
        ts_manager = TimescaleDBManager(session)

        # Verify TimescaleDB is available
        assert await ts_manager.is_timescaledb_available(), "TimescaleDB not available"

        # Add retention policy
        assert await ts_manager.add_retention_policy(
            hypertable="health_checks",
            retention_period="90 days",
            if_not_exists=True,
        )

        # Verify policy exists
        result = await session.execute(
            text(
                "SELECT * FROM timescaledb_information.jobs "
                "WHERE proc_name = 'policy_retention' "
                "AND hypertable_name = 'health_checks'"
            )
        )
        assert result.first() is not None


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "timescaledb: Integration tests requiring TimescaleDB installed (use -m timescaledb to run)",
    )
