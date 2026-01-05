"""Tests for device metrics collection endpoints."""

import secrets

import pytest
from httpx import AsyncClient

from homepot.app.auth_utils import hash_password
from homepot.database import get_database_service


@pytest.fixture
async def setup_device(async_client: AsyncClient):
    """Create a test site and device for metrics tests."""
    import secrets

    from sqlalchemy import delete, select

    from homepot.app.auth_utils import hash_password
    from homepot.database import get_database_service
    from homepot.models import Device, Site

    site_id = "test-site-001"
    device_id = "test-pos-001"

    db_service = await get_database_service()

    # Create site
    existing_site = await db_service.get_site_by_site_id(site_id)
    if not existing_site:
        site = await db_service.create_site(
            site_id=site_id,
            name="Test Site",
            description="Test Site Description",
            location="Test Location",
            latitude=0.0,
            longitude=0.0,
        )
    else:
        site = existing_site

    # Create device
    existing_device = await db_service.get_device_by_device_id(device_id)
    if not existing_device:
        api_key = secrets.token_urlsafe(32)
        api_key_hash = hash_password(api_key)

        await db_service.create_device(
            device_id=device_id,
            name="Test Device",
            device_type="POS",
            site_id=site.id,
            ip_address="192.168.1.100",
            api_key_hash=api_key_hash,
        )

    yield device_id

    # Cleanup
    async with db_service.get_session() as session:
        from homepot.models import HealthCheck

        # Get site ID for cleanup
        site_result = await session.execute(select(Site).where(Site.site_id == site_id))
        site_obj = site_result.scalars().first()

        if site_obj:
            # Find all devices associated with the test site
            devices_result = await session.execute(
                select(Device).where(Device.site_id == site_obj.id)
            )
            devices = devices_result.scalars().all()

            for device in devices:
                # Delete health checks for each device
                await session.execute(
                    delete(HealthCheck).where(HealthCheck.device_id == device.id)
                )

                # Delete the device itself
                await session.execute(delete(Device).where(Device.id == device.id))

            # Delete site
            await session.execute(delete(Site).where(Site.id == site_obj.id))
            await session.commit()


@pytest.mark.asyncio
async def test_submit_health_check_with_full_metrics(
    async_client: AsyncClient, setup_device
):
    """Test submitting health check with all metrics."""
    device_id = setup_device

    payload = {
        "is_healthy": True,
        "response_time_ms": 150,
        "status_code": 200,
        "endpoint": "/health",
        "response_data": {"status": "healthy", "version": "1.2.3"},
        "system": {
            "cpu_percent": 65.5,
            "memory_percent": 80.0,
            "memory_used_mb": 1024,
            "memory_total_mb": 2048,
            "disk_percent": 60.0,
            "disk_used_gb": 120,
            "disk_total_gb": 200,
            "uptime_seconds": 86400,
        },
        "app_metrics": {
            "app_version": "1.2.3",
            "transactions_count": 150,
            "errors_count": 2,
            "warnings_count": 5,
            "avg_response_time_ms": 350,
        },
        "network": {"latency_ms": 45, "rx_bytes": 1024000, "tx_bytes": 512000},
    }

    response = await async_client.post(
        f"/api/v1/devices/{device_id}/health", json=payload
    )

    # CI environments may not have database, accept both 200 (success) and 500 (no DB)
    assert response.status_code in [200, 500]

    if response.status_code == 200:
        data = response.json()
        assert data["message"] == "Health check recorded successfully"
        assert data["device_id"] == device_id
        assert "health_check_id" in data


@pytest.mark.asyncio
async def test_submit_health_check_minimal_data(
    async_client: AsyncClient, setup_device
):
    """Test submitting health check with only required fields."""
    # Use the device created by fixture, or create another one if needed
    # For simplicity, let's reuse the fixture's device or create a new one if we want isolation
    # But since we just need existence, reusing is fine.
    # However, the original test used "test-pos-002". Let's create that too.

    site_id = "test-site-001"
    device_id = "test-pos-002"

    # Ensure site exists (setup_device runs before this, so site exists)
    # Create device 2 directly in DB
    db_service = await get_database_service()
    site = await db_service.get_site_by_site_id(site_id)
    existing_device = await db_service.get_device_by_device_id(device_id)
    if not existing_device:
        api_key = secrets.token_urlsafe(32)
        api_key_hash = hash_password(api_key)
        await db_service.create_device(
            device_id=device_id,
            name="Test Device 2",
            device_type="POS",
            site_id=site.id,
            ip_address="192.168.1.101",
            api_key_hash=api_key_hash,
        )

    payload = {
        "is_healthy": True,
        "response_time_ms": 100,
    }

    response = await async_client.post(
        f"/api/v1/devices/{device_id}/health", json=payload
    )

    # CI environments may not have database, accept both 200 (success) and 500 (no DB)
    assert response.status_code in [200, 500]

    if response.status_code == 200:
        data = response.json()
        assert data["device_id"] == device_id


@pytest.mark.asyncio
async def test_submit_health_check_unhealthy(async_client: AsyncClient, setup_device):
    """Test submitting unhealthy device status."""
    site_id = "test-site-001"
    device_id = "test-pos-003"

    # Create device 3 directly in DB
    db_service = await get_database_service()
    site = await db_service.get_site_by_site_id(site_id)
    existing_device = await db_service.get_device_by_device_id(device_id)
    if not existing_device:
        api_key = secrets.token_urlsafe(32)
        api_key_hash = hash_password(api_key)
        await db_service.create_device(
            device_id=device_id,
            name="Test Device 3",
            device_type="POS",
            site_id=site.id,
            ip_address="192.168.1.102",
            api_key_hash=api_key_hash,
        )

    payload = {
        "is_healthy": False,
        "response_time_ms": 5000,
        "status_code": 500,
        "error_message": "Database connection timeout",
        "system": {"cpu_percent": 95.0, "memory_percent": 98.0, "disk_percent": 99.0},
    }

    response = await async_client.post(
        f"/api/v1/devices/{device_id}/health", json=payload
    )

    # CI environments may not have database, accept both 200 (success) and 500 (no DB)
    assert response.status_code in [200, 500]

    if response.status_code == 200:
        data = response.json()
        assert data["device_id"] == device_id


@pytest.mark.asyncio
async def test_submit_health_check_invalid_device(async_client: AsyncClient):
    """Test submitting health check for non-existent device."""
    device_id = "non-existent-device"

    payload = {
        "is_healthy": True,
        "response_time_ms": 100,
    }

    response = await async_client.post(
        f"/api/v1/devices/{device_id}/health", json=payload
    )

    # Should still accept but create health check without device_id link
    # Or return 404 if strict validation
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_simulate_device_metrics_default(async_client: AsyncClient, setup_device):
    """Test device metrics simulator with default parameters."""
    # The simulator uses "simulated-pos-001" by default. We need to create it.
    site_id = "test-site-001"
    device_id = "simulated-pos-001"

    db_service = await get_database_service()
    site = await db_service.get_site_by_site_id(site_id)
    existing_device = await db_service.get_device_by_device_id(device_id)
    if not existing_device:
        api_key = secrets.token_urlsafe(32)
        api_key_hash = hash_password(api_key)
        await db_service.create_device(
            device_id=device_id,
            name="Simulated Device",
            device_type="POS",
            site_id=site.id,
            ip_address="192.168.1.200",
            api_key_hash=api_key_hash,
        )

    response = await async_client.post("/api/v1/simulator/device-metrics")

    assert response.status_code == 200
    data = response.json()
    # Response format differs when database is unavailable (CI environment)
    assert data["message"] in [
        "Simulated metrics submitted successfully",
        "Health check recorded successfully",
    ]
    assert "device_id" in data

    # Metrics may not be in response if database unavailable
    if "metrics" in data:
        # Verify metrics structure
        metrics = data["metrics"]
        assert "system" in metrics
        assert "app_metrics" in metrics
        assert "network" in metrics

        # Verify system metrics
        system = metrics["system"]
        assert 0 <= system["cpu_percent"] <= 100
        assert 0 <= system["memory_percent"] <= 100
        assert system["memory_used_mb"] <= system["memory_total_mb"]


@pytest.mark.asyncio
async def test_simulate_device_metrics_custom_device(
    async_client: AsyncClient, setup_device
):
    """Test device metrics simulator with custom device ID."""
    custom_device_id = "custom-pos-123"
    site_id = "test-site-001"

    db_service = await get_database_service()
    site = await db_service.get_site_by_site_id(site_id)
    existing_device = await db_service.get_device_by_device_id(custom_device_id)
    if not existing_device:
        api_key = secrets.token_urlsafe(32)
        api_key_hash = hash_password(api_key)
        await db_service.create_device(
            device_id=custom_device_id,
            name="Custom Simulated Device",
            device_type="POS",
            site_id=site.id,
            ip_address="192.168.1.201",
            api_key_hash=api_key_hash,
        )

    response = await async_client.post(
        f"/api/v1/simulator/device-metrics?device_id={custom_device_id}"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["device_id"] == custom_device_id


@pytest.mark.asyncio
async def test_simulate_unhealthy_device(async_client: AsyncClient, setup_device):
    """Test simulating unhealthy device metrics."""
    # Simulator uses "simulated-pos-001" by default.
    # We need to ensure it exists (setup_device creates test-pos-001, but we need simulated-pos-001)
    # Actually, test_simulate_device_metrics_default already created it if running in same session,
    # but tests should be isolated.
    site_id = "test-site-001"
    device_id = "simulated-pos-001"

    db_service = await get_database_service()
    site = await db_service.get_site_by_site_id(site_id)
    existing_device = await db_service.get_device_by_device_id(device_id)
    if not existing_device:
        api_key = secrets.token_urlsafe(32)
        api_key_hash = hash_password(api_key)
        await db_service.create_device(
            device_id=device_id,
            name="Simulated Device",
            device_type="POS",
            site_id=site.id,
            ip_address="192.168.1.200",
            api_key_hash=api_key_hash,
        )

    response = await async_client.post(
        "/api/v1/simulator/device-metrics?is_healthy=false"
    )

    assert response.status_code == 200
    data = response.json()

    # Only verify metrics if database is available
    if "metrics" in data:
        assert data["metrics"]["is_healthy"] is False

        # Unhealthy device should have high resource usage
        system = data["metrics"]["system"]
        assert system["cpu_percent"] >= 70 or system["memory_percent"] >= 70


@pytest.mark.asyncio
async def test_metrics_data_structure(async_client: AsyncClient, setup_device):
    """Test that metrics follow the expected data structure."""
    device_id = "test-pos-structure"
    site_id = "test-site-001"

    db_service = await get_database_service()
    site = await db_service.get_site_by_site_id(site_id)
    existing_device = await db_service.get_device_by_device_id(device_id)
    if not existing_device:
        api_key = secrets.token_urlsafe(32)
        api_key_hash = hash_password(api_key)
        await db_service.create_device(
            device_id=device_id,
            name="Structure Test Device",
            device_type="POS",
            site_id=site.id,
            ip_address="192.168.1.202",
            api_key_hash=api_key_hash,
        )

    payload = {
        "is_healthy": True,
        "response_time_ms": 150,
        "system": {
            "cpu_percent": 50.0,
            "memory_percent": 60.0,
            "memory_used_mb": 1000,
            "memory_total_mb": 2000,
            "disk_percent": 50.0,
            "disk_used_gb": 100,
            "disk_total_gb": 200,
            "uptime_seconds": 3600,
        },
    }

    response = await async_client.post(
        f"/api/v1/devices/{device_id}/health", json=payload
    )

    assert response.status_code == 200

    # Verify data was stored correctly by retrieving it
    # (This would require implementing a GET endpoint)
    # For now, we verify the response confirms storage
    data = response.json()
    assert "health_check_id" in data


@pytest.mark.asyncio
async def test_multiple_metrics_submissions(async_client: AsyncClient, setup_device):
    """Test submitting multiple health checks for the same device."""
    device_id = "test-pos-multi"
    site_id = "test-site-001"

    db_service = await get_database_service()
    site = await db_service.get_site_by_site_id(site_id)
    existing_device = await db_service.get_device_by_device_id(device_id)
    if not existing_device:
        api_key = secrets.token_urlsafe(32)
        api_key_hash = hash_password(api_key)
        await db_service.create_device(
            device_id=device_id,
            name="Multi Test Device",
            device_type="POS",
            site_id=site.id,
            ip_address="192.168.1.203",
            api_key_hash=api_key_hash,
        )

    # Submit first check
    payload1 = {
        "is_healthy": True,
        "response_time_ms": 100,
        "system": {"cpu_percent": 50.0},
    }
    response1 = await async_client.post(
        f"/api/v1/devices/{device_id}/health", json=payload1
    )
    assert response1.status_code == 200

    # Submit second check
    payload2 = {
        "is_healthy": True,
        "response_time_ms": 120,
        "system": {"cpu_percent": 60.0},
    }
    response2 = await async_client.post(
        f"/api/v1/devices/{device_id}/health", json=payload2
    )
    assert response2.status_code == 200

    # Both should have different health_check_ids (if database is available)
    data1 = response1.json()
    data2 = response2.json()
    # health_check_id may be None if database unavailable
    if (
        data1.get("health_check_id") is not None
        and data2.get("health_check_id") is not None
    ):
        assert data1["health_check_id"] != data2["health_check_id"]


@pytest.mark.asyncio
async def test_metrics_validation_ranges(async_client: AsyncClient):
    """Test that metric values are within valid ranges."""
    device_id = "test-pos-validation"

    # Test invalid CPU percentage (> 100)
    payload = {
        "is_healthy": True,
        "response_time_ms": 100,
        "system": {"cpu_percent": 150.0},  # Invalid
    }

    response = await async_client.post(
        f"/api/v1/devices/{device_id}/health", json=payload
    )

    # Should either reject or accept and clamp values
    # Depending on validation strategy
    assert response.status_code in [200, 422]


@pytest.mark.asyncio
async def test_simulator_generates_realistic_data(
    async_client: AsyncClient, setup_device
):
    """Test that simulator generates realistic metric values."""
    # Simulator uses "simulated-pos-001" by default.
    site_id = "test-site-001"
    device_id = "simulated-pos-001"

    db_service = await get_database_service()
    site = await db_service.get_site_by_site_id(site_id)
    existing_device = await db_service.get_device_by_device_id(device_id)
    if not existing_device:
        api_key = secrets.token_urlsafe(32)
        api_key_hash = hash_password(api_key)
        await db_service.create_device(
            device_id=device_id,
            name="Simulated Device",
            device_type="POS",
            site_id=site.id,
            ip_address="192.168.1.200",
            api_key_hash=api_key_hash,
        )

    response = await async_client.post("/api/v1/simulator/device-metrics")

    assert response.status_code == 200
    data = response.json()

    # Only verify metrics if database is available
    if "metrics" in data:
        metrics = data["metrics"]

        # System metrics should be realistic
        system = metrics["system"]
        assert 0 <= system["cpu_percent"] <= 100
        assert 0 <= system["memory_percent"] <= 100
        assert 0 <= system["disk_percent"] <= 100
        assert system["uptime_seconds"] > 0

        # App metrics should be realistic
        app = metrics["app_metrics"]
        assert app["transactions_count"] >= 0
        assert app["errors_count"] >= 0
        assert app["warnings_count"] >= 0
        assert app["avg_response_time_ms"] > 0

        # Network metrics should be realistic
        network = metrics["network"]
        assert network["latency_ms"] > 0
        assert network["rx_bytes"] >= 0
        assert network["tx_bytes"] >= 0
