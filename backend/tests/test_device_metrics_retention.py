"""Tests for the ``device_metrics`` retention cleanup."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from homepot.app.models.AnalyticsModel import DeviceMetrics
from homepot.database import get_database_service
from homepot.models import Device, LifecycleState, Site


def _naive_utc(dt: datetime) -> datetime:
    """Return a naive-UTC datetime, matching ``AnalyticsModel.utc_now``."""
    return dt.replace(tzinfo=None)


def _make_metric(device_pk: int, timestamp: datetime) -> DeviceMetrics:
    return DeviceMetrics(
        device_id=device_pk,
        cpu_percent=10.0,
        memory_percent=20.0,
        timestamp=timestamp,
    )


@pytest.mark.asyncio
async def test_delete_old_device_metrics_only_removes_expired_rows():
    """Rows older than the retention window are deleted; recent rows survive."""
    db = await get_database_service()

    # Create a site + device for the FK.
    sync_db = __import__("homepot.database", fromlist=["SessionLocal"]).SessionLocal()
    try:
        site = Site(site_id="site-metrics-retention", name="Metrics Retention Site", location="Lab")
        sync_db.add(site)
        sync_db.commit()
        sync_db.refresh(site)
        device = Device(
            device_id="metrics-retention-device",
            name="Metrics Retention Device",
            device_type="pos_terminal",
            site_id=site.id,
            is_active=True,
            lifecycle_state=LifecycleState.ACTIVE.value,
        )
        sync_db.add(device)
        sync_db.commit()
        sync_db.refresh(device)
        device_pk = device.id
    finally:
        sync_db.close()

    old = _naive_utc(datetime.now(timezone.utc) - timedelta(days=60))
    recent = _naive_utc(datetime.now(timezone.utc) - timedelta(days=1))

    async with db.get_session() as session:
        session.add(_make_metric(device_pk, old))
        session.add(_make_metric(device_pk, recent))
        session.add(_make_metric(device_pk, old))

    deleted = await db.delete_old_device_metrics(retention_days=30)

    assert deleted >= 2

    async with db.get_session() as session:
        result = await session.execute(
            select(DeviceMetrics).where(DeviceMetrics.device_id == device_pk)
        )
        remaining = result.scalars().all()
    assert len(remaining) == 1
    assert remaining[0].timestamp == recent


@pytest.mark.asyncio
async def test_delete_old_device_metrics_disabled_when_retention_zero():
    """A retention of 0 disables trimming and deletes nothing."""
    db = await get_database_service()
    deleted = await db.delete_old_device_metrics(retention_days=0)
    assert deleted == 0
