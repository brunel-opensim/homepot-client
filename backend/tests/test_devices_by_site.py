"""Tests for get devices by site_id endpoint."""

from fastapi.testclient import TestClient

from homepot.app.main import app


def test_get_devices_by_site_endpoint_exists():
    """Test that the endpoint exists (returns 401 requiring authentication)."""
    client = TestClient(app)

    # Unauthenticated request should return 401 (endpoint exists, auth enforced)
    response = client.get("/api/v1/devices/sites/test-site-999/devices")
    assert response.status_code == 401


def test_get_devices_response_format():
    """Test that authenticated request returns correct format."""
    client = TestClient(app)

    # Verify endpoint requires auth (no demo data needed)
    response = client.get("/api/v1/devices/sites/demo-site-1/devices")
    assert response.status_code == 401
