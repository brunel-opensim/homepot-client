"""Simple test to verify configuration history directly through orchestrator."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def test_direct_config_history():
    """Test configuration history by calling orchestrator directly."""
    from sqlalchemy import select

    from homepot.app.models.AnalyticsModel import ConfigurationHistory
    from homepot.database import get_database_service
    from homepot.models import JobPriority
    from homepot.orchestrator import get_job_orchestrator

    print("Testing Configuration History - Direct Method")
    print("=" * 60)

    # Test 1: Create a job via orchestrator
    print("\n1. Creating config update job via orchestrator...")
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
        print(f"✓ Job created: {job_id}")
    except Exception as e:
        print(f"✗ Failed to create job: {e}")
        import traceback

        traceback.print_exc()
        return

    # Wait for agents to process
    print("\n2. Waiting for agents to process configuration update (20 seconds)...")
    await asyncio.sleep(20)

    # Test 2: Query configuration_history table
    print("\n3. Checking configuration_history table...")
    db_service = await get_database_service()
    async with db_service.get_session() as session:
        cutoff_time = datetime.utcnow() - timedelta(minutes=10)

        result = await session.execute(
            select(ConfigurationHistory)
            .where(ConfigurationHistory.timestamp >= cutoff_time)
            .order_by(ConfigurationHistory.timestamp.desc())
        )
        config_logs = result.scalars().all()

        print(f"\n   Found {len(config_logs)} configuration changes:\n")

        if not config_logs:
            print("   ⚠ No configuration history entries found!")
            print(
                "   This might mean the job hasn't processed yet or tracking failed."
            )
            return

        for log in config_logs:
            print(f"   [{log.timestamp}] {log.entity_type.upper()}: {log.entity_id}")
            print(f"      Parameter: {log.parameter_name}")
            if log.old_value:
                print(f"      Old value: {log.old_value}")
            print(f"      New value: {log.new_value}")
            print(f"      Changed by: {log.changed_by} ({log.change_type})")
            if log.change_reason:
                print(f"      Reason: {log.change_reason}")
            if log.performance_before:
                print(f"      Performance before: {log.performance_before}")
            print()

    print("\n✅ Configuration history tracking verified!")
    print("\nSummary:")
    print(f"  - Total config changes logged: {len(config_logs)}")
    site_changes = [l for l in config_logs if l.entity_type == "site"]
    device_changes = [l for l in config_logs if l.entity_type == "device"]
    print(f"  - Site-level changes: {len(site_changes)}")
    print(f"  - Device-level changes: {len(device_changes)}")


if __name__ == "__main__":
    asyncio.run(test_direct_config_history())
