"""Test and populate site operating schedules."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def populate_schedules():
    """Create a complete weekly schedule for site-001."""
    from datetime import time

    from homepot.app.models.AnalyticsModel import SiteOperatingSchedule
    from homepot.database import get_database_service

    print("Populating Site Operating Schedules for AI Training")
    print("=" * 60)

    # Define a realistic weekly schedule
    weekly_schedule = [
        {  # Monday
            "day_of_week": 0,
            "open_time": time(8, 0),
            "close_time": time(22, 0),
            "is_closed": False,
            "is_maintenance_window": False,
            "expected_transaction_volume": 500,
            "peak_hours_start": time(12, 0),
            "peak_hours_end": time(14, 0),
            "notes": "Regular weekday - high traffic",
        },
        {  # Tuesday
            "day_of_week": 1,
            "open_time": time(8, 0),
            "close_time": time(22, 0),
            "is_closed": False,
            "is_maintenance_window": False,
            "expected_transaction_volume": 450,
            "peak_hours_start": time(12, 0),
            "peak_hours_end": time(14, 0),
            "notes": "Regular weekday",
        },
        {  # Wednesday
            "day_of_week": 2,
            "open_time": time(8, 0),
            "close_time": time(22, 0),
            "is_closed": False,
            "is_maintenance_window": True,  # Maintenance window
            "expected_transaction_volume": 420,
            "peak_hours_start": time(12, 0),
            "peak_hours_end": time(14, 0),
            "notes": "Regular weekday - maintenance window 2-4 AM",
        },
        {  # Thursday
            "day_of_week": 3,
            "open_time": time(8, 0),
            "close_time": time(23, 0),  # Late night
            "is_closed": False,
            "is_maintenance_window": False,
            "expected_transaction_volume": 550,
            "peak_hours_start": time(18, 0),  # Evening peak
            "peak_hours_end": time(21, 0),
            "notes": "Late night shopping - extended hours",
        },
        {  # Friday
            "day_of_week": 4,
            "open_time": time(8, 0),
            "close_time": time(23, 30),  # Latest
            "is_closed": False,
            "is_maintenance_window": False,
            "expected_transaction_volume": 700,
            "peak_hours_start": time(17, 0),
            "peak_hours_end": time(21, 0),
            "notes": "Busiest day - weekend shopping starts",
        },
        {  # Saturday
            "day_of_week": 5,
            "open_time": time(9, 0),  # Open later
            "close_time": time(23, 0),
            "is_closed": False,
            "is_maintenance_window": False,
            "expected_transaction_volume": 650,
            "peak_hours_start": time(11, 0),
            "peak_hours_end": time(17, 0),  # Longer peak
            "notes": "Weekend - steady traffic all day",
        },
        {  # Sunday
            "day_of_week": 6,
            "open_time": time(10, 0),  # Latest opening
            "close_time": time(18, 0),  # Early close
            "is_closed": False,
            "is_maintenance_window": True,  # Evening maintenance
            "expected_transaction_volume": 200,
            "peak_hours_start": time(13, 0),
            "peak_hours_end": time(15, 0),
            "notes": "Sunday - reduced hours, evening maintenance",
        },
    ]

    db_service = await get_database_service()
    async with db_service.get_session() as session:
        day_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        for schedule_data in weekly_schedule:
            # Check if exists
            from sqlalchemy import select

            result = await session.execute(
                select(SiteOperatingSchedule).where(
                    SiteOperatingSchedule.site_id == "site-001",
                    SiteOperatingSchedule.day_of_week == schedule_data["day_of_week"],
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update
                for key, value in schedule_data.items():
                    setattr(existing, key, value)
                existing.site_id = "site-001"  # Ensure site_id is set
                action = "Updated"
            else:
                # Create
                new_schedule = SiteOperatingSchedule(
                    site_id="site-001", **schedule_data
                )
                session.add(new_schedule)
                action = "Created"

            day = day_names[schedule_data["day_of_week"]]
            status = "CLOSED" if schedule_data["is_closed"] else "OPEN"
            hours = f"{schedule_data['open_time']} - {schedule_data['close_time']}"
            
            print(f"✓ {action} {day}: {status} {hours}")
            if schedule_data["is_maintenance_window"]:
                print(f"       Maintenance window scheduled")
            print(f"    Expected volume: {schedule_data['expected_transaction_volume']} txn/day")

        await session.commit()

    print("\nWeekly schedule populated successfully!")
    print("\nSchedule Summary:")
    print("  - Total days: 7")
    print("  - Operating days: 7")
    print("  - Maintenance windows: 2 (Wednesday, Sunday)")
    print("  - Busiest day: Friday (700 txn)")
    print("  - Quietest day: Sunday (200 txn)")


async def verify_via_api():
    """Verify schedules via API endpoint."""
    import httpx

    print("\n" + "=" * 60)
    print("Verifying via API Endpoint")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/api/v1/sites/site-001/schedules", timeout=10.0
        )

        if response.status_code == 200:
            data = response.json()
            schedules = data.get("schedules", [])
            print(f"\n✓ API returned {len(schedules)} schedules\n")

            for schedule in schedules:
                print(f"{schedule['day_name']}:")
                if schedule["is_closed"]:
                    print("  Status: CLOSED")
                else:
                    print(f"  Hours: {schedule['open_time']} - {schedule['close_time']}")
                    if schedule["peak_hours_start"]:
                        print(
                            f"  Peak: {schedule['peak_hours_start']} - {schedule['peak_hours_end']}"
                        )
                    print(f"  Expected Volume: {schedule['expected_transaction_volume']}")
                if schedule["is_maintenance_window"]:
                    print("     Maintenance Window")
                print()
        else:
            print(f"✗ API request failed: {response.status_code}")
            print(response.text)


if __name__ == "__main__":
    asyncio.run(populate_schedules())
    asyncio.run(verify_via_api())
