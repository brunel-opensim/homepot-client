"""Tests for site delete."""

from typing import Any
import uuid

import pytest

from homepot.models import Device, DeviceStatus, Site


@pytest.mark.asyncio
async def test_api_site_delete(temp_db: Any) -> None:
    """Test backend site cascade deletion logic."""
    from homepot.database import get_database_service

    db_service = await get_database_service()

    unique_suffix = str(uuid.uuid4())[:8]
    site_id = f"test-site-deletion-{unique_suffix}"

    async with db_service.get_session() as session:
        site = Site(site_id=site_id, name="Test Company Delete", is_active=True)
        session.add(site)
        await session.commit()
        await session.refresh(site)

        device = Device(
            device_id=f"dev-delete-{unique_suffix}",
            name="Test POS",
            device_type="pos_terminal",
            site_id=site.id,
            is_active=False,
            status=DeviceStatus.UNPAIRED,
        )
        session.add(device)
        await session.commit()

    from homepot.app.api.API_v1.Endpoints.SitesEndpoint import delete_site

    await delete_site(site_id)
