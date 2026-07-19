"""Tests for device unpair."""

from typing import Any
import uuid

import pytest
from sqlalchemy import select

from homepot.database import get_database_service
from homepot.models import AuditLog, Device, DeviceStatus, LifecycleState, Site


@pytest.mark.asyncio
async def test_device_unpair_soft_delete(temp_db: Any) -> None:
    """Test soft deletion logic for unpairing a device."""
    db_service = await get_database_service()

    unique_suffix = str(uuid.uuid4())[:8]
    device_id = f"test-device-unpair-{unique_suffix}"
    site_id = f"test-site-unpair-{unique_suffix}"

    async with db_service.get_session() as session:
        site = Site(site_id=site_id, name="Test Company", is_active=True)
        session.add(site)
        await session.commit()
        await session.refresh(site)

        device = Device(
            device_id=device_id,
            name="Test POS",
            device_type="pos_terminal",
            site_id=site.id,
            is_active=True,
            status=DeviceStatus.ONLINE,
            api_key_hash="hashed_key_here",
        )
        session.add(device)
        await session.commit()

    devices = await db_service.get_devices_by_site_id(site_id)
    assert len(devices) > 0
    assert any(d.device_id == device_id for d in devices)

    success = await db_service.delete_device(device_id)
    assert success is True

    updated_devices = await db_service.get_devices_by_site_id(site_id)
    assert not any(d.device_id == device_id for d in updated_devices)

    async with db_service.get_session() as session:
        result = await session.execute(
            select(Device).where(Device.device_id == device_id)
        )
        fetched_device = result.scalars().first()

        assert fetched_device is not None
        assert fetched_device.is_active is False
        assert fetched_device.lifecycle_state == LifecycleState.UNPAIRED.value
        assert fetched_device.api_key_hash is None

        audit_result = await session.execute(
            select(AuditLog).where(
                AuditLog.device_id == device.id,
                AuditLog.event_type == "device_unpaired",
            )
        )
        audit_log = audit_result.scalars().first()
        assert audit_log is not None
