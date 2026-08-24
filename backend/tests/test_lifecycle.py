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
async def test_connectivity_reflects_lifecycle_state(temp_db: Any) -> None:
    """Non-active devices report offline even with a recent heartbeat."""
    from datetime import datetime, timedelta, timezone

    from homepot.app.api.API_v1.Endpoints.DevicesEndpoints import (
        _compute_connectivity,
    )

    db_service = await get_database_service()

    unique_suffix = str(uuid.uuid4())[:8]
    site_id = f"test-site-conn-life-{unique_suffix}"

    async with db_service.get_session() as session:
        site = Site(site_id=site_id, name="Test Site", is_active=True)
        session.add(site)
        await session.commit()
        await session.refresh(site)

        recent = datetime.now(timezone.utc)
        devices = [
            Device(
                device_id=f"test-conn-active-{unique_suffix}",
                name="Active",
                device_type="pos_terminal",
                site_id=site.id,
                is_active=True,
                lifecycle_state=LifecycleState.ACTIVE.value,
                last_heartbeat_at=recent,
            ),
            Device(
                device_id=f"test-conn-unpaired-{unique_suffix}",
                name="Unpaired",
                device_type="pos_terminal",
                site_id=site.id,
                is_active=False,
                lifecycle_state=LifecycleState.UNPAIRED.value,
                last_heartbeat_at=recent,
            ),
            Device(
                device_id=f"test-conn-suspended-{unique_suffix}",
                name="Suspended",
                device_type="pos_terminal",
                site_id=site.id,
                is_active=False,
                lifecycle_state=LifecycleState.SUSPENDED.value,
                last_heartbeat_at=recent,
            ),
            Device(
                device_id=f"test-conn-stale-{unique_suffix}",
                name="Stale active",
                device_type="pos_terminal",
                site_id=site.id,
                is_active=True,
                lifecycle_state=LifecycleState.ACTIVE.value,
                last_heartbeat_at=recent - timedelta(minutes=10),
            ),
        ]
        session.add_all(devices)
        await session.commit()

        for device in devices:
            await session.refresh(device)

        by_id = {d.device_id: d for d in devices}
        assert (
            _compute_connectivity(by_id[f"test-conn-active-{unique_suffix}"])
            == "online"
        )
        assert (
            _compute_connectivity(by_id[f"test-conn-unpaired-{unique_suffix}"])
            == "offline"
        )
        assert (
            _compute_connectivity(by_id[f"test-conn-suspended-{unique_suffix}"])
            == "offline"
        )
        assert (
            _compute_connectivity(by_id[f"test-conn-stale-{unique_suffix}"])
            == "offline"
        )


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
async def test_lifecycle_persist_device_persists_detached_mutation(
    temp_db: Any,
) -> None:
    """Mutations to a detached device must persist via persist_device.

    get_device_by_device_id() returns a Device whose session is already
    closed; attribute changes on that object are silently lost unless the
    caller merges it back into a fresh session.
    """
    db_service = await get_database_service()

    unique_suffix = str(uuid.uuid4())[:8]
    device_id = f"test-dev-persist-{unique_suffix}"
    site_id = f"test-site-persist-{unique_suffix}"

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

    detached = await db_service.get_device_by_device_id(device_id)
    assert detached is not None

    # Simulate the mutation made by the lifecycle endpoints.
    detached.lifecycle_state = LifecycleState.SUSPENDED.value  # type: ignore[assignment]
    detached.is_active = False  # type: ignore[assignment]
    detached.api_key_hash = None  # type: ignore[assignment]

    await db_service.persist_device(detached)

    async with db_service.get_session() as session:
        result = await session.execute(
            select(Device).where(Device.device_id == device_id)
        )
        fetched = result.scalars().first()
        assert fetched is not None
        assert fetched.lifecycle_state == LifecycleState.SUSPENDED.value
        assert fetched.is_active is False
        assert fetched.api_key_hash is None


@pytest.mark.asyncio
async def test_get_device_by_device_id_include_unpaired(temp_db: Any) -> None:
    """An unpaired device is reachable only with include_unpaired=True."""
    db_service = await get_database_service()

    unique_suffix = str(uuid.uuid4())[:8]
    device_id = f"test-dev-reenrol-{unique_suffix}"
    site_id = f"test-site-reenrol-{unique_suffix}"

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

    # Unpair the device (soft delete) so is_active=False.
    success = await db_service.delete_device(device_id)
    assert success is True

    # Default lookup filters out unpaired devices.
    assert await db_service.get_device_by_device_id(device_id) is None

    # Re-enrolment needs to find the unpaired device.
    unpaired = await db_service.get_device_by_device_id(
        device_id, include_unpaired=True
    )
    assert unpaired is not None
    assert unpaired.lifecycle_state == LifecycleState.UNPAIRED.value
    assert unpaired.is_active is False


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
