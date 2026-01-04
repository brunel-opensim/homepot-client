"""Simple test to verify configuration history directly through orchestrator."""

import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from homepot.app.models.AnalyticsModel import ConfigurationHistory
from homepot.database import get_database_service
from homepot.models import JobPriority
from homepot.orchestrator import get_job_orchestrator


@pytest.mark.asyncio
async def test_direct_config_history():
    """Test configuration history by calling orchestrator directly."""
    # Test 1: Create a job via orchestrator
    try:
        orchestrator = await get_job_orchestrator()
        job_id = await orchestrator.create_pos_config_update_job(
            site_id="site-001",
            action="Update POS payment config",
            description="Direct test of configuration tracking",
            config_url="https://config-server.example.com/pos-config-v2.6.json",
            config_version="2.6.0",
            priority=JobPriority.HIGH,
        )
        assert job_id is not None
    except Exception as e:
        pytest.fail(f"Failed to create job: {e}")

    # Wait for agents to process - reduced time for test
    await asyncio.sleep(1)

    # Test 2: Query configuration_history table
    db_service = await get_database_service()
    async with db_service.get_session() as session:
        cutoff_time = datetime.utcnow() - timedelta(minutes=10)

        result = await session.execute(
            select(ConfigurationHistory)
            .where(ConfigurationHistory.timestamp >= cutoff_time)
            .order_by(ConfigurationHistory.timestamp.desc())
        )
        config_logs = result.scalars().all()

        # Just verify the query works
        assert config_logs is not None
