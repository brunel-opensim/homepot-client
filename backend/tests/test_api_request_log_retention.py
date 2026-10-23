"""Tests for the ``api_request_logs`` retention cleanup."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from homepot.app.models.AnalyticsModel import APIRequestLog
from homepot.database import get_database_service


def _naive_utc(dt: datetime) -> datetime:
    """Return a naive-UTC datetime, matching ``AnalyticsModel.utc_now``."""
    return dt.replace(tzinfo=None)


def _make_log(endpoint: str, timestamp: datetime) -> APIRequestLog:
    return APIRequestLog(
        endpoint=endpoint,
        method="GET",
        status_code=200,
        response_time_ms=10.0,
        timestamp=timestamp,
    )


@pytest.mark.asyncio
async def test_delete_old_api_request_logs_only_removes_expired_rows():
    """Rows older than the retention window are deleted; recent rows survive."""
    db = await get_database_service()

    old = _naive_utc(datetime.now(timezone.utc) - timedelta(days=60))
    recent = _naive_utc(datetime.now(timezone.utc) - timedelta(days=1))

    async with db.get_session() as session:
        session.add(_make_log("/old", old))
        session.add(_make_log("/recent", recent))
        session.add(_make_log("/old-2", old))

    deleted = await db.delete_old_api_request_logs(retention_days=30)

    assert deleted == 2

    async with db.get_session() as session:
        remaining = await session.execute(select(APIRequestLog))
        rows = remaining.scalars().all()
        endpoints = {row.endpoint for row in rows}
        assert endpoints == {"/recent"}


@pytest.mark.asyncio
async def test_delete_old_api_request_logs_batches_large_backlogs():
    """A backlog larger than one batch is cleared across multiple batches."""
    db = await get_database_service()

    old = _naive_utc(datetime.now(timezone.utc) - timedelta(days=60))
    async with db.get_session() as session:
        for i in range(15):
            session.add(_make_log(f"/old-{i}", old))

    deleted = await db.delete_old_api_request_logs(
        retention_days=30, batch_size=5, max_batches=10
    )

    assert deleted == 15
