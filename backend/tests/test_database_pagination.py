"""Test database pagination functionality."""

import pytest

from homepot.database import get_database_service


@pytest.mark.asyncio
async def test_get_devices_by_site_and_segment_paginated():
    """Test pagination for device fetching."""
    db_service = await get_database_service()
    await db_service.initialize()

    # Create a test site
    site = await db_service.create_site(
        site_id="site-pagination-test", name="Pagination Test Site"
    )

    # Create 15 test devices
    devices = []
    for i in range(15):
        device = await db_service.create_device(
            device_id=f"device-p-{i}",
            name=f"Device {i}",
            device_type="pos_terminal",
            site_id=site.id,
        )
        devices.append(device)

    # Test fetching first page (limit 10)
    page1 = await db_service.get_devices_by_site_and_segment_paginated(
        site_id="site-pagination-test", segment="pos-terminals", limit=10, offset=0
    )
    assert len(page1) == 10
    assert page1[0].device_id == "device-p-0"
    assert page1[9].device_id == "device-p-9"

    # Test fetching second page (limit 10, offset 10)
    page2 = await db_service.get_devices_by_site_and_segment_paginated(
        site_id="site-pagination-test", segment="pos-terminals", limit=10, offset=10
    )
    assert len(page2) == 5
    assert page2[0].device_id == "device-p-10"
    assert page2[4].device_id == "device-p-14"

    # Test fetching empty page
    page3 = await db_service.get_devices_by_site_and_segment_paginated(
        site_id="site-pagination-test", segment="pos-terminals", limit=10, offset=20
    )
    assert len(page3) == 0
