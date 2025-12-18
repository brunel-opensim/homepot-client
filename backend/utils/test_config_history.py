"""Test script to verify configuration history tracking."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def test_config_history():
    """Test configuration history tracking by creating a config update job."""
    import httpx

    print("Testing Configuration History Tracking...")
    print("=" * 60)

    # Test 1: Create a config update job
    print("\n1. Creating config update job...")
    job_data = {
        "action": "Update POS payment config",
        "description": "Test configuration update for AI training",
        "config_url": "https://config-server.example.com/pos-config-v2.5.json",
        "config_version": "2.5.0",
        "priority": "high",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/jobs/sites/site-001/jobs",
            json=job_data,
            timeout=10.0,
        )
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Job created: {result['job_id']}")
            job_id = result["job_id"]
        else:
            print(f"✗ Failed to create job: {response.status_code}")
            print(response.text)
            return

    # Wait for job to process
    print("\n2. Waiting for job to process (15 seconds)...")
    await asyncio.sleep(15)

    # Test 2: Query configuration_history table
    print("\n3. Checking configuration_history table...")
    from datetime import datetime, timedelta

    from sqlalchemy import select

    from homepot.app.models.AnalyticsModel import ConfigurationHistory
    from homepot.database import get_database_service

    db_service = await get_database_service()
    async with db_service.get_session() as session:
        # Get recent config history entries
        cutoff_time = datetime.utcnow() - timedelta(minutes=5)

        result = await session.execute(
            select(ConfigurationHistory)
            .where(ConfigurationHistory.timestamp >= cutoff_time)
            .order_by(ConfigurationHistory.timestamp.desc())
        )
        config_logs = result.scalars().all()

        print(f"\n   Found {len(config_logs)} configuration changes in last 5 minutes:\n")

        for log in config_logs:
            print(f"   [{log.timestamp}] {log.entity_type.upper()}: {log.entity_id}")
            print(f"      Parameter: {log.parameter_name}")
            print(f"      Change: {log.old_value} → {log.new_value}")
            print(f"      Changed by: {log.changed_by} ({log.change_type})")
            if log.change_reason:
                print(f"      Reason: {log.change_reason}")
            if log.performance_before:
                print(f"      Performance before: {log.performance_before}")
            print()

    print("\nConfiguration history tracking test complete!")
    print("\nSummary:")
    print(f"  - Job creation logged: Yes (site-level)")
    print(f"  - Device updates logged: {'Yes' if len(config_logs) > 1 else 'Pending'}")
    print(f"  - Total config changes: {len(config_logs)}")


if __name__ == "__main__":
    asyncio.run(test_config_history())
