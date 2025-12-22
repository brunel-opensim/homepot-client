"""API endpoints for managing site operating schedules."""

import logging
from datetime import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from homepot.app.models.AnalyticsModel import SiteOperatingSchedule
from homepot.database import get_database_service

logger = logging.getLogger(__name__)

router = APIRouter()


class ScheduleCreate(BaseModel):
    """Model for creating a site operating schedule."""

    site_id: str = Field(..., description="Site identifier")
    day_of_week: int = Field(
        ..., ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)"
    )
    open_time: Optional[str] = Field(
        None, description="Opening time (HH:MM:SS or HH:MM)"
    )
    close_time: Optional[str] = Field(
        None, description="Closing time (HH:MM:SS or HH:MM)"
    )
    is_closed: bool = Field(False, description="Is the site closed this day")
    is_maintenance_window: bool = Field(
        False, description="Is this a maintenance window"
    )
    expected_transaction_volume: Optional[int] = Field(
        None, description="Expected daily transactions"
    )
    peak_hours_start: Optional[str] = Field(
        None, description="Peak hours start (HH:MM:SS or HH:MM)"
    )
    peak_hours_end: Optional[str] = Field(
        None, description="Peak hours end (HH:MM:SS or HH:MM)"
    )
    notes: Optional[str] = Field(None, description="Additional notes")

    class Config:
        json_schema_extra = {
            "example": {
                "site_id": "site-001",
                "day_of_week": 0,
                "open_time": "08:00:00",
                "close_time": "22:00:00",
                "is_closed": False,
                "is_maintenance_window": False,
                "expected_transaction_volume": 500,
                "peak_hours_start": "12:00:00",
                "peak_hours_end": "14:00:00",
                "notes": "Regular weekday schedule",
            }
        }


class ScheduleUpdate(BaseModel):
    """Model for updating a site operating schedule."""

    open_time: Optional[str] = None
    close_time: Optional[str] = None
    is_closed: Optional[bool] = None
    is_maintenance_window: Optional[bool] = None
    expected_transaction_volume: Optional[int] = None
    peak_hours_start: Optional[str] = None
    peak_hours_end: Optional[str] = None
    notes: Optional[str] = None


def parse_time(time_str: Optional[str]) -> Optional[time]:
    """Parse time string to time object."""
    if not time_str:
        return None

    # Handle HH:MM or HH:MM:SS formats
    parts = time_str.split(":")
    if len(parts) == 2:
        return time(int(parts[0]), int(parts[1]))
    elif len(parts) == 3:
        return time(int(parts[0]), int(parts[1]), int(parts[2]))
    else:
        raise ValueError(f"Invalid time format: {time_str}. Use HH:MM or HH:MM:SS")


@router.post("/{site_id}/schedules", tags=["Site Schedules"])
async def create_site_schedule(
    site_id: str, schedule: ScheduleCreate
) -> Dict[str, Any]:
    """Create or update a site operating schedule for a specific day.

    This endpoint helps AI understand when sites are operational for intelligent
    job scheduling and workload prediction.
    """
    try:
        # Verify site_id matches
        if schedule.site_id != site_id:
            raise HTTPException(
                status_code=400,
                detail=f"site_id in path ({site_id}) must match site_id in body ({schedule.site_id})",
            )

        # Parse times
        open_time = parse_time(schedule.open_time)
        close_time = parse_time(schedule.close_time)
        peak_start = parse_time(schedule.peak_hours_start)
        peak_end = parse_time(schedule.peak_hours_end)

        db_service = await get_database_service()
        async with db_service.get_session() as session:
            # Check if schedule already exists for this site/day
            result = await session.execute(
                select(SiteOperatingSchedule).where(
                    SiteOperatingSchedule.site_id == site_id,
                    SiteOperatingSchedule.day_of_week == schedule.day_of_week,
                )
            )
            existing: Any = result.scalar_one_or_none()

            if existing:
                # Update existing schedule
                existing.open_time = open_time
                existing.close_time = close_time
                existing.is_closed = schedule.is_closed
                existing.is_maintenance_window = schedule.is_maintenance_window
                existing.expected_transaction_volume = (
                    schedule.expected_transaction_volume
                )
                existing.peak_hours_start = peak_start
                existing.peak_hours_end = peak_end
                existing.notes = schedule.notes

                message = "Schedule updated successfully"
            else:
                # Create new schedule
                new_schedule = SiteOperatingSchedule(
                    site_id=site_id,
                    day_of_week=schedule.day_of_week,
                    open_time=open_time,
                    close_time=close_time,
                    is_closed=schedule.is_closed,
                    is_maintenance_window=schedule.is_maintenance_window,
                    expected_transaction_volume=schedule.expected_transaction_volume,
                    peak_hours_start=peak_start,
                    peak_hours_end=peak_end,
                    notes=schedule.notes,
                )
                session.add(new_schedule)
                message = "Schedule created successfully"

            await session.commit()

        logger.info(f"{message} for {site_id}, day {schedule.day_of_week}")

        day_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        return {
            "message": message,
            "site_id": site_id,
            "day": day_names[schedule.day_of_week],
            "day_of_week": schedule.day_of_week,
            "is_closed": schedule.is_closed,
            "hours": (
                f"{schedule.open_time} - {schedule.close_time}"
                if not schedule.is_closed
                else "Closed"
            ),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create/update schedule: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to create/update schedule. Please check server logs.",
        )


@router.get("/{site_id}/schedules", tags=["Site Schedules"])
async def get_site_schedules(site_id: str) -> Dict[str, Any]:
    """Get all operating schedules for a site.

    Returns the weekly schedule including operating hours, peak times,
    and expected transaction volumes for AI analysis.
    """
    try:
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            result = await session.execute(
                select(SiteOperatingSchedule)
                .where(SiteOperatingSchedule.site_id == site_id)
                .order_by(SiteOperatingSchedule.day_of_week)
            )
            schedules = result.scalars().all()

            day_names = [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]

            schedule_list = []
            for schedule in schedules:
                schedule_list.append(
                    {
                        "id": schedule.id,
                        "day_of_week": schedule.day_of_week,
                        "day_name": day_names[schedule.day_of_week],
                        "open_time": (
                            str(schedule.open_time) if schedule.open_time else None
                        ),
                        "close_time": (
                            str(schedule.close_time) if schedule.close_time else None
                        ),
                        "is_closed": schedule.is_closed,
                        "is_maintenance_window": schedule.is_maintenance_window,
                        "expected_transaction_volume": schedule.expected_transaction_volume,
                        "peak_hours_start": (
                            str(schedule.peak_hours_start)
                            if schedule.peak_hours_start
                            else None
                        ),
                        "peak_hours_end": (
                            str(schedule.peak_hours_end)
                            if schedule.peak_hours_end
                            else None
                        ),
                        "notes": schedule.notes,
                    }
                )

            return {"site_id": site_id, "schedules": schedule_list}

    except Exception as e:
        logger.error(f"Failed to get schedules for {site_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve schedules. Please check server logs.",
        )


@router.delete("/{site_id}/schedules/{day_of_week}", tags=["Site Schedules"])
async def delete_site_schedule(site_id: str, day_of_week: int) -> Dict[str, str]:
    """Delete a site operating schedule for a specific day."""
    try:
        if day_of_week < 0 or day_of_week > 6:
            raise HTTPException(
                status_code=400,
                detail="day_of_week must be between 0 (Monday) and 6 (Sunday)",
            )

        db_service = await get_database_service()
        async with db_service.get_session() as session:
            result = await session.execute(
                delete(SiteOperatingSchedule).where(
                    SiteOperatingSchedule.site_id == site_id,
                    SiteOperatingSchedule.day_of_week == day_of_week,
                )
            )
            await session.commit()

            if getattr(result, "rowcount", 0) == 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"No schedule found for {site_id} on day {day_of_week}",
                )

        logger.info(f"Deleted schedule for {site_id}, day {day_of_week}")

        day_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        return {
            "message": "Schedule deleted successfully",
            "site_id": site_id,
            "day": day_names[day_of_week],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete schedule: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to delete schedule. Please check server logs.",
        )
