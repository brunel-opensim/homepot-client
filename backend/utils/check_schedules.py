"""Check site operating schedules data."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def check_schedules():
    """Check existing site operating schedules."""
    from sqlalchemy import select

    from homepot.app.models.AnalyticsModel import SiteOperatingSchedule
    from homepot.database import get_database_service

    db_service = await get_database_service()
    async with db_service.get_session() as session:
        result = await session.execute(select(SiteOperatingSchedule))
        schedules = result.scalars().all()

        print(f"Found {len(schedules)} schedule entries:\n")

        if not schedules:
            print("  No schedule data exists yet")
            return

        for schedule in schedules:
            day_names = [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]
            day = day_names[schedule.day_of_week]

            print(f"Site: {schedule.site_id} - {day}")
            if schedule.is_closed:
                print("  Status: CLOSED")
            else:
                print(f"  Hours: {schedule.open_time} - {schedule.close_time}")
                if schedule.peak_hours_start:
                    print(
                        f"  Peak: {schedule.peak_hours_start} - {schedule.peak_hours_end}"
                    )
                if schedule.expected_transaction_volume:
                    print(f"  Expected Volume: {schedule.expected_transaction_volume}")
            if schedule.is_maintenance_window:
                print("    Maintenance Window")
            print()


if __name__ == "__main__":
    asyncio.run(check_schedules())
