"""Quick script to check error logs."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))


async def check_error_logs():
    """Check recent error logs."""
    from datetime import datetime, timedelta

    from sqlalchemy import select

    from homepot.app.models.AnalyticsModel import ErrorLog
    from homepot.database import get_database_service

    db_service = await get_database_service()
    async with db_service.get_session() as session:
        # Get all error logs from the last hour
        cutoff_time = datetime.utcnow() - timedelta(hours=1)

        result = await session.execute(
            select(ErrorLog)
            .where(ErrorLog.timestamp >= cutoff_time)
            .order_by(ErrorLog.timestamp.desc())
        )
        logs = result.scalars().all()

        print(f"Found {len(logs)} error logs in the last hour:\n")

        for log in logs:
            print(f"[{log.timestamp}] {log.severity.upper()} - {log.category}")
            print(f"  Message: {log.error_message}")
            if log.error_code:
                print(f"  Code: {log.error_code}")
            if log.device_id:
                print(f"  Device: {log.device_id}")
            if log.endpoint:
                print(f"  Endpoint: {log.endpoint}")
            if log.context:
                print(f"  Context: {log.context}")
            print()


if __name__ == "__main__":
    asyncio.run(check_error_logs())
