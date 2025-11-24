"""Tests for get devices by site_id endpoint."""

from fastapi.testclient import TestClient

from homepot.app.main import app


def test_get_devices_by_site_endpoint_exists():
    """Test that the endpoint exists and returns proper format."""
    client = TestClient(app)

    # Try to access the endpoint - should either return 404 for non-existent site or work
    response = client.get("/api/v1/devices/sites/test-site-999/devices")

    # Should get either 404 (site not found) or 200 with empty list
    # But NOT 404 with "Not Found" (endpoint doesn't exist)
    assert response.status_code in [200, 404]

    if response.status_code == 404:
        # Should be our custom 404 message about site not found
        detail = response.json()["detail"]
        assert "not found" in detail.lower()
        assert "site" in detail.lower()


def test_get_devices_response_format():
    """Test that response has correct format when site exists."""
    client = TestClient(app)

    # The response should be a list of dictionaries with specific fields
    # This test verifies the data structure without needing actual data
    # We'll use the demo site if it exists
    response = client.get("/api/v1/devices/sites/demo-site-1/devices")

    # If site exists, should return 200 with list
    if response.status_code == 200:
        devices = response.json()
        assert isinstance(devices, list)

        # If there are devices, check structure
        if len(devices) > 0:
            device = devices[0]
            required_fields = [
                "site_id",
                "device_id",
                "name",
                "device_type",
                "status",
                "ip_address",
                "created_at",
                "updated_at",
            ]
            for field in required_fields:
                assert field in device, f"Missing field: {field}"

            # Verify IDs are strings (not integers)
            assert isinstance(device["site_id"], str)
            assert isinstance(device["device_id"], str)
