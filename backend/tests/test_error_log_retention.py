"""Tests for the ``error_logs`` retention cleanup."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from homepot.app.models.AnalyticsModel import ErrorLog
from homepot.database import get_database_service


def _naive_utc(dt: datetime) -> datetime:
    """Return a naive-UTC datetime, matching ``AnalyticsModel.utc_now``."""
    return dt.replace(tzinfo=None)


def _make_log(marker: str, timestamp: datetime) -> ErrorLog:
    return ErrorLog(
        category="status",
        severity="info",
        error_message=f"{marker} status report",
        timestamp=timestamp,
        context={"original_device_id": "retention-test-device"},
    )


@pytest.mark.asyncio
async def test_delete_old_error_logs_only_removes_expired_rows():
    """Rows older than the retention window are deleted; recent rows survive."""
    db = await get_database_service()
    marker = "retention-test-error"

    old = _naive_utc(datetime.now(timezone.utc) - timedelta(days=30))
    recent = _naive_utc(datetime.now(timezone.utc) - timedelta(days=1))

    async with db.get_session() as session:
        session.add(_make_log(f"{marker}/old", old))
        session.add(_make_log(f"{marker}/recent", recent))
        session.add(_make_log(f"{marker}/old-2", old))

    deleted = await db.delete_old_error_logs(retention_days=7)

    assert deleted >= 2

    async with db.get_session() as session:
        result = await session.execute(
            select(ErrorLog.error_message).where(
                ErrorLog.error_message.like(f"{marker}/%")
            )
        )
        remaining = set(result.scalars().all())
    assert remaining == {f"{marker}/recent status report"}


@pytest.mark.asyncio
async def test_delete_old_error_logs_disabled_when_retention_zero():
    """A retention of 0 disables trimming and deletes nothing."""
    db = await get_database_service()
    deleted = await db.delete_old_error_logs(retention_days=0)
    assert deleted == 0
