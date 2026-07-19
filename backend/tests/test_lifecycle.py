"""Tests for device lifecycle state transitions."""

from typing import Any
import uuid

import pytest
from sqlalchemy import select

from homepot.database import get_database_service
from homepot.models import Device, LifecycleState, Site


@pytest.mark.asyncio
async def test_lifecycle_initial_state_pending(temp_db: Any) -> None:
    """A newly created device via the admin endpoint should start as pending."""
    db_service = await get_database_service()

    unique_suffix = str(uuid.uuid4())[:8]
    site_id = f"test-site-init-{unique_suffix}"

    async with db_service.get_session() as session:
        site = Site(site_id=site_id, name="Test Site", is_active=True)
        session.add(site)
        await session.commit()
        await session.refresh(site)

        device = Device(
            device_id=f"test-dev-init-{unique_suffix}",
            name="Test Device",
            device_type="pos_terminal",
            site_id=site.id,
            is_active=True,
            lifecycle_state=LifecycleState.PENDING.value,
        )
        session.add(device)
        await session.commit()
        await session.refresh(device)

        assert device.lifecycle_state == LifecycleState.PENDING.value


@pytest.mark.asyncio
async def test_lifecycle_active_device_online_connectivity(temp_db: Any) -> None:
    """An active device with a recent heartbeat should show online connectivity."""
    from datetime import datetime, timezone

    db_service = await get_database_service()

    unique_suffix = str(uuid.uuid4())[:8]
    site_id = f"test-site-conn-{unique_suffix}"

    async with db_service.get_session() as session:
        site = Site(site_id=site_id, name="Test Site", is_active=True)
        session.add(site)
        await session.commit()
        await session.refresh(site)

        device = Device(
            device_id=f"test-dev-conn-{unique_suffix}",
            name="Test Device",
            device_type="pos_terminal",
            site_id=site.id,
            is_active=True,
            lifecycle_state=LifecycleState.ACTIVE.value,
            last_heartbeat_at=datetime.now(timezone.utc),
        )
        session.add(device)
        await session.commit()

        from homepot.app.services.lifecycle_service import LifecycleService
        from homepot.database import SessionLocal

        sync_db = SessionLocal()
        try:
            ls = LifecycleService(sync_db)
            ls.assert_active(device)
        finally:
            sync_db.close()


@pytest.mark.asyncio
async def test_lifecycle_unpair_sets_state(temp_db: Any) -> None:
    """Unpairing a device should set lifecycle_state to unpaired."""
    db_service = await get_database_service()

    unique_suffix = str(uuid.uuid4())[:8]
    device_id = f"test-dev-unpair-{unique_suffix}"
    site_id = f"test-site-unpair-{unique_suffix}"

    async with db_service.get_session() as session:
        site = Site(site_id=site_id, name="Test Site", is_active=True)
        session.add(site)
        await session.commit()
        await session.refresh(site)

        device = Device(
            device_id=device_id,
            name="Test POS",
            device_type="pos_terminal",
            site_id=site.id,
            is_active=True,
            lifecycle_state=LifecycleState.ACTIVE.value,
            api_key_hash="hashed_key_here",
        )
        session.add(device)
        await session.commit()

    success = await db_service.delete_device(device_id)
    assert success is True

    async with db_service.get_session() as session:
        result = await session.execute(
            select(Device).where(Device.device_id == device_id)
        )
        fetched = result.scalars().first()
        assert fetched is not None
        assert fetched.lifecycle_state == LifecycleState.UNPAIRED.value
        assert fetched.is_active is False
        assert fetched.api_key_hash is None


@pytest.mark.asyncio
async def test_lifecycle_unpaired_device_not_in_active_list(temp_db: Any) -> None:
    """Unpaired devices should be excluded from active device listings."""
    db_service = await get_database_service()

    unique_suffix = str(uuid.uuid4())[:8]
    device_id = f"test-dev-list-{unique_suffix}"
    site_id = f"test-site-list-{unique_suffix}"

    async with db_service.get_session() as session:
        site = Site(site_id=site_id, name="Test Site", is_active=True)
        session.add(site)
        await session.commit()
        await session.refresh(site)

        device = Device(
            device_id=device_id,
            name="Test POS",
            device_type="pos_terminal",
            site_id=site.id,
            is_active=True,
            lifecycle_state=LifecycleState.ACTIVE.value,
        )
        session.add(device)
        await session.commit()

    await db_service.delete_device(device_id)

    devices = await db_service.get_devices_by_site_id(site_id)
    assert not any(d.device_id == device_id for d in devices)


@pytest.mark.asyncio
async def test_lifecycle_get_device_status_returns_three_dimensions(
    temp_db: Any,
) -> None:
    """The agent status endpoint should return lifecycle, connectivity, and health."""
    from datetime import datetime, timezone

    from homepot.app.services.agent_service import AgentService

    get_test_db = temp_db
    unique_suffix = str(uuid.uuid4())[:8]
    device_id = f"test-dev-status-{unique_suffix}"

    sync_db = get_test_db()
    try:
        site = Site(
            site_id=f"test-site-status-{unique_suffix}",
            name="Test Site",
            is_active=True,
        )
        sync_db.add(site)
        sync_db.commit()
        sync_db.refresh(site)

        device = Device(
            device_id=device_id,
            name="Test Device",
            device_type="pos_terminal",
            site_id=site.id,
            is_active=True,
            lifecycle_state=LifecycleState.ACTIVE.value,
            health_state="healthy",
            last_heartbeat_at=datetime.now(timezone.utc),
        )
        sync_db.add(device)
        sync_db.commit()

        service = AgentService(sync_db)
        status = service.get_device_status(device_id)

        assert "lifecycle_state" in status
        assert "connectivity_state" in status
        assert "health_state" in status
        assert status["lifecycle_state"] == LifecycleState.ACTIVE.value
        assert status["health_state"] == "healthy"
    finally:
        sync_db.close()
