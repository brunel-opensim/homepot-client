"""Tests for Mobivisor API endpoints.

This module contains unit tests for the Mobivisor device integration endpoints.
Tests mock the httpx client to avoid actual API calls during testing.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from homepot.app.main import app


@pytest.fixture
def client():
    """Create a test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_mobivisor_config():
    """Mock Mobivisor configuration."""
    return {
        "mobivisor_api_url": "https://test.mobivisor.com/",
        "mobivisor_api_token": "test-token-123",
    }


@pytest.fixture
def mock_httpx_response():
    """Create a mock httpx response."""

    def _create_response(status_code=200, json_data=None, text=""):
        response = MagicMock(spec=httpx.Response)
        response.status_code = status_code
        response.json.return_value = json_data or {}
        response.text = text
        response.content = b"" if not json_data else b"{}"
        return response

    return _create_response


class TestMobivisorDevicesEndpoints:
    """Test cases for Mobivisor devices endpoints."""

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_devices_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test successful device list fetch."""
        # Setup mocks
        mock_config.return_value = mock_mobivisor_config
        devices_data = {
            "devices": [
                {"id": "123", "name": "Device 1", "status": "online"},
                {"id": "456", "name": "Device 2", "status": "offline"},
            ]
        }
        mock_response = mock_httpx_response(status_code=200, json_data=devices_data)

        # Mock the async context manager
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        # Make request
        response = client.get("/api/v1/mobivisor/devices")
        # Assertions
        assert response.status_code == 200
        assert response.json() == devices_data

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    def test_fetch_devices_missing_url(self, mock_config, client):
        """Test device fetch with missing URL configuration."""
        mock_config.return_value = {
            "mobivisor_api_url": None,
            "mobivisor_api_token": "test-token",
        }

        response = client.get("/api/v1/mobivisor/devices")
        print(response.status_code, response.json(), "-------------")
        assert response.status_code == 500
        assert "Configuration Error" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    def test_fetch_devices_missing_token(self, mock_config, client):
        """Test device fetch with missing token configuration."""
        mock_config.return_value = {
            "mobivisor_api_url": "https://test.mobivisor.com/",
            "mobivisor_api_token": None,
        }

        response = client.get("/api/v1/mobivisor/devices")

        assert response.status_code == 500
        assert "Configuration Error" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_devices_unauthorized(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test device fetch with unauthorized response."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=401, json_data={"error": "Invalid token"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices")

        assert response.status_code == 401
        assert "Unauthorized" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_update_feature_controls_success(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Successful feature controls update should forward payload and return proxied response."""
        mock_config.return_value = mock_mobivisor_config
        payload = [
            {"feature": "camera", "booleanValue": True},
            {"feature": "screen_brightness", "numberValue": 100},
        ]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"ok": True})

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.put(
            "/api/v1/mobivisor/devices/123/featureControls", json=payload
        )
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    def test_update_feature_controls_missing_url(self, mock_config, client):
        """Missing Mobivisor URL should return 500 Configuration Error."""
        mock_config.return_value = {}
        response = client.put(
            "/api/v1/mobivisor/devices/123/featureControls",
            json=[{"feature": "camera", "booleanValue": True}],
        )
        assert response.status_code == 500

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    def test_update_feature_controls_missing_token(self, mock_config, client):
        """Missing Mobivisor token should return 500 Configuration Error."""
        mock_config.return_value = {"mobivisor_api_url": "https://test.mobivisor.com/"}
        response = client.put(
            "/api/v1/mobivisor/devices/123/featureControls",
            json=[{"feature": "camera", "booleanValue": True}],
        )
        assert response.status_code == 500

    def test_update_feature_controls_invalid_payload_empty(self, client):
        """Empty payload should return 422 Validation Error."""
        response = client.put("/api/v1/mobivisor/devices/123/featureControls", json=[])
        assert response.status_code == 422

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_update_feature_controls_timeout(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Upstream timeout should be translated to 504."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.put(
            "/api/v1/mobivisor/devices/123/featureControls",
            json=[{"feature": "camera", "booleanValue": True}],
        )
        assert response.status_code == 504

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_update_feature_controls_network_error(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Network errors should return 502 Bad Gateway."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.RequestError("Network")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.put(
            "/api/v1/mobivisor/devices/123/featureControls",
            json=[{"feature": "camera", "booleanValue": True}],
        )
        assert response.status_code == 502

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_update_feature_controls_upstream_404(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Upstream 404 should be translated to a local 404."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json = MagicMock(return_value={"error": "Not Found"})
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.put(
            "/api/v1/mobivisor/devices/unknown/featureControls",
            json=[{"feature": "camera", "booleanValue": True}],
        )
        assert response.status_code == 404
        assert (
            "Not Found" in response.json()["detail"]["error"]
            or response.json()["detail"]["error"] == "Not Found"
        )

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_devices_timeout(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Test device fetch with timeout."""
        mock_config.return_value = mock_mobivisor_config

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices")

        assert response.status_code == 504
        assert "Gateway Timeout" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_device_details_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test successful device details fetch."""
        mock_config.return_value = mock_mobivisor_config
        device_data = {
            "id": "123",
            "name": "Device 1",
            "status": "online",
            "last_seen": "2025-10-18T10:30:00Z",
        }
        mock_response = mock_httpx_response(status_code=200, json_data=device_data)

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices/123")

        assert response.status_code == 200
        assert response.json() == device_data

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_device_details_not_found(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test device details fetch with device not found."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=404, json_data={"error": "Device not found"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices/999")

        assert response.status_code == 404
        assert "Not Found" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_device_applications_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test successful fetch of device applications."""
        mock_config.return_value = mock_mobivisor_config
        apps_data = [
            {
                "appName": "Example App",
                "packageName": "com.example.app",
                "version": "1.0.0",
                "managed": True,
            }
        ]
        mock_response = mock_httpx_response(status_code=200, json_data=apps_data)

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices/123/applications")

        assert response.status_code == 200
        assert response.json() == apps_data

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_device_applications_not_found(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test fetching device applications when device not found."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=404, json_data={"error": "Device not found"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices/999/applications")

        assert response.status_code == 404
        assert "Not Found" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_device_applications_timeout(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Test device applications fetch with timeout."""
        mock_config.return_value = mock_mobivisor_config

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices/123/applications")

        assert response.status_code == 504
        assert "Gateway Timeout" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_delete_device_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test successful device deletion."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(status_code=204)

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.delete("/api/v1/mobivisor/devices/123")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Device deleted successfully"
        assert data["device_id"] == "123"

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_delete_device_not_found(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test device deletion with device not found."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=404, json_data={"error": "Device not found"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.delete("/api/v1/mobivisor/devices/device_not_found")

        assert response.status_code == 404
        assert "Not Found" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_delete_device_forbidden(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test device deletion with forbidden response."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=403, json_data={"error": "Forbidden"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.delete("/api/v1/mobivisor/devices/123")

        assert response.status_code == 403
        assert "Unauthorized" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_devices_network_error(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Test device fetch with network error."""
        mock_config.return_value = mock_mobivisor_config

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.RequestError("Network error")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices")

        assert response.status_code == 502
        assert "Bad Gateway" in response.json()["detail"]["error"]


class TestMobivisorGroupsCreate:
    """Tests for group creation endpoint."""

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_create_group_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test successful group creation returns created data."""
        mock_config.return_value = mock_mobivisor_config
        payload = {"name": "New Group", "description": "Test"}
        mock_response = mock_httpx_response(
            status_code=201, json_data={"id": "g-new", "name": "New Group"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.post("/api/v1/mobivisor/groups", json=payload)

        assert response.status_code == 201 or response.status_code == 200
        assert response.json()["name"] == "New Group"

    def test_create_group_missing_required_fields(self, client):
        """Missing required `name` should return 422 validation error."""
        payload = {"description": "No name"}

        response = client.post("/api/v1/mobivisor/groups", json=payload)

        assert response.status_code == 422
        assert response.json()["detail"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    def test_create_group_missing_config(self, mock_config, client):
        """Missing mobivisor URL configuration should return 500."""
        mock_config.return_value = {
            "mobivisor_api_url": None,
            "mobivisor_api_token": "t",
        }

        response = client.post("/api/v1/mobivisor/groups", json={"name": "x"})

        assert response.status_code == 500
        assert "Configuration Error" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_create_group_unauthorized(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Upstream 401 should be proxied to client."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=401, json_data={"error": "Unauthorized"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.post("/api/v1/mobivisor/groups", json={"name": "x"})

        assert response.status_code == 401
        assert "Unauthorized" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_create_group_timeout(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Upstream timeout should return 504 Gateway Timeout."""
        mock_config.return_value = mock_mobivisor_config

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.post("/api/v1/mobivisor/groups", json={"name": "x"})

        assert response.status_code == 504
        assert "Gateway Timeout" in response.json()["detail"]["error"]


class TestMobivisorGroupsUpdate:
    """Tests for group update endpoint."""

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_update_group_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Successful group update returns updated data."""
        mock_config.return_value = mock_mobivisor_config
        payload = {"name": "Updated Name"}
        mock_response = mock_httpx_response(
            status_code=200, json_data={"id": "g1", "name": "Updated Name"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.put("/api/v1/mobivisor/groups/g1", json=payload)

        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_update_group_partial(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Partial update (only name) should succeed."""
        mock_config.return_value = mock_mobivisor_config
        payload = {"name": "Partial"}
        mock_response = mock_httpx_response(
            status_code=200, json_data={"id": "g1", "name": "Partial"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.put("/api/v1/mobivisor/groups/g1", json=payload)

        assert response.status_code == 200
        assert response.json()["name"] == "Partial"

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_update_group_not_found(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Upstream 404 should return 404 to client."""
        mock_config.return_value = mock_mobivisor_config
        payload = {"name": "Doesn't Matter"}
        mock_response = mock_httpx_response(
            status_code=404, json_data={"error": "Not Found"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.put("/api/v1/mobivisor/groups/nonexistent", json=payload)

        assert response.status_code == 404
        assert "Not Found" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_update_group_unauthorized(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Upstream 401 should be proxied."""
        mock_config.return_value = mock_mobivisor_config
        payload = {"name": "Nope"}
        mock_response = mock_httpx_response(
            status_code=401, json_data={"error": "Unauthorized"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.put("/api/v1/mobivisor/groups/g1", json=payload)

        assert response.status_code == 401
        assert "Unauthorized" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_update_group_timeout(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Upstream timeout should return Gateway Timeout."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        payload = {"name": "Timeout"}
        response = client.put("/api/v1/mobivisor/groups/g1", json=payload)

        assert response.status_code == 504
        assert "Gateway Timeout" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_devices_bad_gateway(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test device fetch with upstream service error."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=500, json_data={"error": "Internal server error"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices")

        assert response.status_code == 502
        assert "Bad Gateway" in response.json()["detail"]["error"]
        assert response.json()["detail"]["upstream_status"] == 500

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_trigger_device_action_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test successfully triggering a device action."""
        mock_config.return_value = mock_mobivisor_config
        device_id = "6895b35f73796d4ff80a57a0"
        payload = {
            "deviceId": device_id,
            "commandType": "update_settings",
            "commandData": {"sendApps": False},
        }
        response_payload = {
            "__v": 0,
            "user": device_id,
            "userName": "admin",
            "commandData": "{}",
            "commandType": "Fetch System Apps",
            "commandTypeOldFormat": "fetch_system_apps",
            "environment": "Android Enterprise",
            "_id": "69328eb219a2fefab2e0d64b",
            "status": "Not Sent",
            "timeCreated": "2025-12-05T07:50:10.232Z",
        }
        mock_response = mock_httpx_response(status_code=200, json_data=response_payload)

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.put(
            f"/api/v1/mobivisor/devices/{device_id}/actions",
            json=payload,
        )

        assert response.status_code == 200
        assert response.json() == response_payload

    def test_trigger_device_action_device_id_mismatch(self, client):
        """Test payload device ID must match path parameter."""
        device_id = "6895b35f73796d4ff80a57a0"
        payload = {
            "deviceId": "mismatch",
            "commandType": "refresh_kiosk",
            "commandData": {},
        }

        response = client.put(
            f"/api/v1/mobivisor/devices/{device_id}/actions",
            json=payload,
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "Validation Error"

    def test_trigger_device_action_missing_password(self, client):
        """Test validation error when password is missing for password change."""
        device_id = "6895b35f73796d4ff80a57a0"
        payload = {
            "deviceId": device_id,
            "commandType": "change_password_now",
            "commandData": {},
        }

        response = client.put(
            f"/api/v1/mobivisor/devices/{device_id}/actions",
            json=payload,
        )

        assert response.status_code == 422
        assert any("password" in error["msg"] for error in response.json()["detail"])

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    def test_trigger_device_action_missing_token(self, mock_config, client):
        """Test configuration error when token missing for device actions."""
        mock_config.return_value = {
            "mobivisor_api_url": "https://test.mobivisor.com/",
            "mobivisor_api_token": None,
        }
        device_id = "6895b35f73796d4ff80a57a0"
        payload = {
            "deviceId": device_id,
            "commandType": "refresh_kiosk",
            "commandData": {},
        }

        response = client.put(
            f"/api/v1/mobivisor/devices/{device_id}/actions",
            json=payload,
        )

        assert response.status_code == 500
        assert response.json()["detail"]["error"] == "Configuration Error"


class TestMobivisorUserEndpoints:
    """Test cases for Mobivisor user endpoints."""

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_users_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test successful user list fetch."""
        mock_config.return_value = mock_mobivisor_config
        users_data = {
            "users": [
                {"id": "u1", "name": "User 1"},
                {"id": "u2", "name": "User 2"},
            ]
        }
        mock_response = mock_httpx_response(status_code=200, json_data=users_data)

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/users")

        assert response.status_code == 200
        assert response.json() == users_data

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_users_unauthorized(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test user fetch with unauthorized response."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=401, json_data={"error": "Invalid token"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/users")

        assert response.status_code == 401
        assert "Unauthorized" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_user_details_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test successful user details fetch."""
        mock_config.return_value = mock_mobivisor_config
        user_data = {"id": "u1", "name": "User 1", "email": "u1@example.com"}
        mock_response = mock_httpx_response(status_code=200, json_data=user_data)

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/users/u1")

        assert response.status_code == 200
        assert response.json() == user_data

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_user_details_not_found(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test user details fetch when user not found."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=404, json_data={"error": "User not found"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/users/unknown")

        assert response.status_code == 404
        assert "Not Found" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_delete_user_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test successful user deletion."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(status_code=204)

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.delete("/api/v1/mobivisor/users/u1")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "User deleted successfully"
        assert data["user_id"] == "u1"

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_delete_user_not_found(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test user deletion when user not found."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=404, json_data={"error": "User not found"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.delete("/api/v1/mobivisor/users/unknown")

        assert response.status_code == 404
        assert "Not Found" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_create_user_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test successful user creation forwarded to Mobivisor."""
        mock_config.return_value = mock_mobivisor_config

        payload = {
            "user": {
                "email": "jr.kothiya@gmail.com",
                "displayName": "Kothiya Yogesh",
                "username": "jr.kothiya",
                "phone": "7567407883",
                "password": "1234567890",
                "notes": "Test",
                "role": {"_id": "Admin", "rights": [], "displayedRights": []},
            },
            "groupInfoOfTheUser": [{"_id": "6895b47e634b34c01c2d69c4"}],
        }

        created_user = {"id": "u123", "email": payload["user"]["email"]}
        mock_response = mock_httpx_response(status_code=201, json_data=created_user)

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.post("/api/v1/mobivisor/users", json=payload)

        assert response.status_code == 201 or response.status_code == 200
        assert response.json() == created_user

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_create_user_accepts_short_tld_email(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Ensure emails with short TLDs like `a1@b.c` are accepted by EmailStr."""
        mock_config.return_value = mock_mobivisor_config

        payload = {
            "user": {
                "email": "a1@b.c",
                "displayName": "Short TLD",
                "username": "shorttld",
                "phone": "1234567890",
                "password": "secret",
            }
        }

        created_user = {"id": "u_short", "email": payload["user"]["email"]}
        mock_response = mock_httpx_response(status_code=201, json_data=created_user)

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.post("/api/v1/mobivisor/users", json=payload)

        assert response.status_code in (200, 201)
        assert response.json() == created_user

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_create_user_unauthorized(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test create user when Mobivisor returns unauthorized."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=401, json_data={"error": "Invalid token"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        payload = {
            "user": {
                "email": "a@b.com",
                "displayName": "Test User",
                "username": "testuser",
                "phone": "1234567890",
                "password": "secret",
            }
        }
        response = client.post("/api/v1/mobivisor/users", json=payload)

        assert response.status_code == 401
        assert "Unauthorized" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    def test_create_user_missing_config(self, mock_config, client):
        """Test create user with missing Mobivisor configuration."""
        mock_config.return_value = {
            "mobivisor_api_url": None,
            "mobivisor_api_token": "token",
        }

        payload = {
            "user": {
                "email": "a@b.com",
                "displayName": "Test User",
                "username": "testuser",
                "phone": "1234567890",
                "password": "secret",
            }
        }
        response = client.post("/api/v1/mobivisor/users", json=payload)

        assert response.status_code == 500
        assert "Configuration Error" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_create_user_timeout(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Test create user when upstream times out."""
        mock_config.return_value = mock_mobivisor_config

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        payload = {
            "user": {
                "email": "a@b.com",
                "displayName": "Test User",
                "username": "testuser",
                "phone": "1234567890",
                "password": "secret",
            }
        }
        response = client.post("/api/v1/mobivisor/users", json=payload)

        assert response.status_code == 504
        assert "Gateway Timeout" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    def test_create_user_missing_required_fields(
        self, mock_config, client, mock_mobivisor_config
    ):
        """Validate server returns 400 when required user fields are missing."""
        mock_config.return_value = mock_mobivisor_config

        # Only provide email, missing displayName, username, phone, password
        payload = {"user": {"email": "a@b.com"}}

        response = client.post("/api/v1/mobivisor/users", json=payload)

        # Pydantic validation should produce a 422 Unprocessable Entity
        assert response.status_code == 422
        body = response.json()
        assert isinstance(body["detail"], list)
        assert len(body["detail"]) > 0

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    def test_create_user_empty_email(self, mock_config, client, mock_mobivisor_config):
        """Validate empty email returns a 422 and points to the email field."""
        mock_config.return_value = mock_mobivisor_config

        payload = {
            "user": {
                "email": "",
                "displayName": "Test User",
                "username": "testuser",
                "phone": "1234567890",
                "password": "secret",
            }
        }

        response = client.post("/api/v1/mobivisor/users", json=payload)
        assert response.status_code == 422
        body = response.json()
        assert isinstance(body["detail"], list)
        # Ensure at least one validation error references the email field
        assert any(
            any(isinstance(loc, str) and "email" in loc for loc in err.get("loc", []))
            for err in body["detail"]
        )

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    def test_create_user_null_fields(self, mock_config, client, mock_mobivisor_config):
        """Validate null user object yields 422 pointing to user."""
        mock_config.return_value = mock_mobivisor_config

        payload = {"user": None}

        response = client.post("/api/v1/mobivisor/users", json=payload)
        assert response.status_code == 422
        body = response.json()
        assert isinstance(body["detail"], list)
        assert any(
            any(isinstance(loc, str) and "user" in loc for loc in err.get("loc", []))
            for err in body["detail"]
        )

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_update_user_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test successful user update forwarded to Mobivisor."""
        mock_config.return_value = mock_mobivisor_config

        payload = {
            "user": {
                "email": "a11@b.c",
                "displayName": "Kothiya Yogesh",
                "username": "jr11b.kothiya",
                "phone": "7567407883",
                "password": "1234567890",
                "notes": "Test",
                "_id": "6930491019a2fefab2e0b300",
                "role": {"_id": "Admin", "rights": [], "displayedRights": []},
            },
            "groupInfoOfTheUser": [{"admin": True, "_id": "6895b47e634b34c01c2d69c4"}],
        }

        updated_user = {
            "id": "6930491019a2fefab2e0b300",
            "email": payload["user"]["email"],
        }
        mock_response = mock_httpx_response(status_code=200, json_data=updated_user)

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.put(
            "/api/v1/mobivisor/users/6930491019a2fefab2e0b300", json=payload
        )

        assert response.status_code == 200
        assert response.json() == updated_user

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_update_user_unauthorized(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test update user when Mobivisor returns unauthorized."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=401, json_data={"error": "Invalid token"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        payload = {
            "user": {
                "email": "a@b.com",
                "displayName": "Test",
                "username": "t",
                "phone": "1",
                "password": "p",
            }
        }
        response = client.put("/api/v1/mobivisor/users/6930", json=payload)

        assert response.status_code == 401
        assert "Unauthorized" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    def test_update_user_missing_config(self, mock_config, client):
        """Test update user with missing Mobivisor configuration."""
        mock_config.return_value = {
            "mobivisor_api_url": None,
            "mobivisor_api_token": "token",
        }

        payload = {
            "user": {
                "email": "a@b.com",
                "displayName": "Test",
                "username": "t",
                "phone": "1",
                "password": "p",
            }
        }
        response = client.put("/api/v1/mobivisor/users/6930", json=payload)

        assert response.status_code == 500
        assert "Configuration Error" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_update_user_timeout(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Test update user when upstream times out."""
        mock_config.return_value = mock_mobivisor_config

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        payload = {
            "user": {
                "email": "a@b.com",
                "displayName": "Test",
                "username": "t",
                "phone": "1",
                "password": "p",
            }
        }
        response = client.put("/api/v1/mobivisor/users/6930", json=payload)

        assert response.status_code == 504
        assert "Gateway Timeout" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_update_user_network_error(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Test update user with network error."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.RequestError("Network error")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        payload = {
            "user": {
                "email": "a@b.com",
                "displayName": "Test",
                "username": "t",
                "phone": "1",
                "password": "p",
            }
        }
        response = client.put("/api/v1/mobivisor/users/6930", json=payload)

        assert response.status_code == 502
        assert "Bad Gateway" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_update_user_not_found(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test update user when user not found upstream."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=404, json_data={"error": "Not Found"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        payload = {
            "user": {
                "email": "a@b.com",
                "displayName": "Test",
                "username": "t",
                "phone": "1",
                "password": "p",
            }
        }
        response = client.put("/api/v1/mobivisor/users/6930", json=payload)

        assert response.status_code == 404
        assert "Not Found" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    def test_update_user_validation_errors(
        self, mock_config, client, mock_mobivisor_config
    ):
        """Validate update user payload missing required fields returns 422."""
        mock_config.return_value = mock_mobivisor_config

        # With partial-update semantics the request with only email is valid; mock upstream success.
        payload = {"user": {"email": "a@b.com"}}

        # Patch httpx AsyncClient to return success for the forwarded request
        with patch(
            "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config",
        ) as mock_cfg:
            mock_cfg.return_value = mock_mobivisor_config
            with patch("httpx.AsyncClient") as mock_async_client:
                updated_user = {"id": "6930", "email": "a@b.com"}
                mock_response = MagicMock(spec=httpx.Response)
                mock_response.status_code = 200
                mock_response.json.return_value = updated_user

                mock_client_instance = AsyncMock()
                mock_client_instance.request = AsyncMock(return_value=mock_response)
                mock_async_client.return_value.__aenter__.return_value = (
                    mock_client_instance
                )

                response = client.put("/api/v1/mobivisor/users/6930", json=payload)

        assert response.status_code == 200
        assert response.json() == updated_user

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    def test_update_user_invalid_email(
        self, mock_config, client, mock_mobivisor_config
    ):
        """Invalid email should produce 422 from Pydantic."""
        mock_config.return_value = mock_mobivisor_config

        payload = {
            "user": {
                "email": "not-an-email",
                "displayName": "T",
                "username": "u",
                "phone": "1",
                "password": "p",
            }
        }
        response = client.put("/api/v1/mobivisor/users/6930", json=payload)

        assert response.status_code == 422
        body = response.json()
        assert isinstance(body["detail"], list)


class TestMobivisorDeviceAdditionalEndpoints:
    """Tests for additional device endpoints not covered above."""

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_installed_packages_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test fetching installed packages for a device."""
        mock_config.return_value = mock_mobivisor_config
        packages = {"packages": [{"id": "p1", "name": "App"}]}
        mock_response = mock_httpx_response(status_code=200, json_data=packages)

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices/123/installed-packages")

        assert response.status_code == 200
        assert response.json() == packages

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_delete_installed_package_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test deleting an installed package from a device."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=200, json_data={"result": "deleted"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.delete(
            "/api/v1/mobivisor/devices/123/delete-installed-package/p1"
        )

        assert response.status_code == 200
        assert response.json() == {"result": "deleted"}

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_managed_apps_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test fetching managed apps for a device."""
        mock_config.return_value = mock_mobivisor_config
        apps = {"managedApps": [{"id": "a1", "name": "App"}]}
        mock_response = mock_httpx_response(status_code=200, json_data=apps)

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices/123/get-managed-apps")

        assert response.status_code == 200
        assert response.json() == apps

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_device_commands_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test fetching device commands with query params returns data."""
        mock_config.return_value = mock_mobivisor_config
        commands = {"commands": [{"id": "c1", "command": "refresh"}]}
        mock_response = mock_httpx_response(status_code=200, json_data=commands)

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get(
            "/api/v1/mobivisor/devices/commands",
            params={
                "order": "timeCreated",
                "page": 0,
                "per_page": 20,
                "reverse": "true",
                "search": "{}",
            },
        )

        assert response.status_code == 200
        assert response.json() == commands

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    def test_fetch_device_commands_missing_url(self, mock_config, client):
        """Missing mobivisor URL configuration should return 500."""
        mock_config.return_value = {
            "mobivisor_api_url": None,
            "mobivisor_api_token": "t",
        }

        response = client.get(
            "/api/v1/mobivisor/devices/commands",
            params={"order": "timeCreated", "page": 0},
        )

        assert response.status_code == 500
        assert "Configuration Error" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_device_commands_unauthorized(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Upstream unauthorized response should be proxied."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=401, json_data={"error": "Unauthorized"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get(
            "/api/v1/mobivisor/devices/commands",
            params={"order": "timeCreated"},
        )

        assert response.status_code == 401
        assert "Unauthorized" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_device_commands_timeout(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Upstream timeout should return 504 Gateway Timeout."""
        mock_config.return_value = mock_mobivisor_config

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get(
            "/api/v1/mobivisor/devices/commands", params={"order": "timeCreated"}
        )

        assert response.status_code == 504
        assert "Gateway Timeout" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_device_commands_network_error(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Network errors should return 502 Bad Gateway."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.RequestError("Network")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get(
            "/api/v1/mobivisor/devices/commands", params={"order": "timeCreated"}
        )

        assert response.status_code == 502
        assert "Bad Gateway" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_system_apps_by_model_version_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Successful fetch of system apps by model/version should return proxied JSON."""
        mock_config.return_value = mock_mobivisor_config
        data = {"systemApps": [{"package": "com.example.app", "name": "Example"}]}
        mock_response = mock_httpx_response(status_code=200, json_data=data)

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get(
            "/api/v1/mobivisor/devices/fetchSystemApps/model/SM-G998/version/1.2.3"
        )

        assert response.status_code == 200
        assert response.json() == data

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    def test_fetch_system_apps_missing_url(self, mock_config, client):
        """Missing Mobivisor URL should return 500 Configuration Error."""
        mock_config.return_value = {}
        response = client.get(
            "/api/v1/mobivisor/devices/fetchSystemApps/model/SM-G998/version/1.2.3"
        )
        assert response.status_code == 500
        assert "Configuration Error" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    def test_fetch_system_apps_missing_token(self, mock_config, client):
        """Missing Mobivisor token should return 500 Configuration Error."""
        mock_config.return_value = {"mobivisor_api_url": "https://test.mobivisor.com/"}
        response = client.get(
            "/api/v1/mobivisor/devices/fetchSystemApps/model/SM-G998/version/1.2.3"
        )
        assert response.status_code == 500
        assert "Configuration Error" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_system_apps_timeout(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Upstream timeout should return 504 Gateway Timeout."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get(
            "/api/v1/mobivisor/devices/fetchSystemApps/model/SM-G998/version/1.2.3"
        )
        assert response.status_code == 504
        assert "Gateway Timeout" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_system_apps_network_error(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Network errors should return 502 Bad Gateway."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.RequestError("Network")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get(
            "/api/v1/mobivisor/devices/fetchSystemApps/model/SM-G998/version/1.2.3"
        )
        assert response.status_code == 502
        assert "Bad Gateway" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_system_apps_not_found(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Upstream 404 should be translated to local 404."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json = MagicMock(return_value={"error": "Not Found"})
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get(
            "/api/v1/mobivisor/devices/fetchSystemApps/model/unknown/version/0"
        )
        assert response.status_code == 404
        assert (
            "Not Found" in response.json()["detail"]["error"]
            or response.json()["detail"]["error"] == "Not Found"
        )

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_system_apps_unauthorized(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Upstream 401/403 should be proxied as-is."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json = MagicMock(return_value={"error": "Unauthorized"})
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get(
            "/api/v1/mobivisor/devices/fetchSystemApps/model/SM-G998/version/1.2.3"
        )
        assert response.status_code == 401
        assert "Unauthorized" in response.json()["detail"]["error"]


class TestMobivisorUserEndpointsExtended:
    """Extended tests for Mobivisor user endpoints."""

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_users_timeout(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Test user fetch with timeout."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/users")

        assert response.status_code == 504
        assert "Gateway Timeout" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_users_network_error(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Test user fetch with network error."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.RequestError("Network error")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/users")

        assert response.status_code == 502
        assert "Bad Gateway" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_user_details_timeout(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Test user details fetch with timeout."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/users/u1")

        assert response.status_code == 504
        assert "Gateway Timeout" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_user_details_forbidden(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test user details fetch with forbidden response."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=403, json_data={"error": "Forbidden"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/users/u1")

        assert response.status_code == 403
        assert "Unauthorized" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_delete_user_forbidden(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test user deletion with forbidden response."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=403, json_data={"error": "Forbidden"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.delete("/api/v1/mobivisor/users/u1")

        assert response.status_code == 403
        assert "Unauthorized" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_delete_user_timeout(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Test user deletion with timeout."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.delete("/api/v1/mobivisor/users/u1")

        assert response.status_code == 504
        assert "Gateway Timeout" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorUserEndpoints.get_mobivisor_api_config"
    )
    def test_fetch_users_missing_config(self, mock_config, client):
        """Test fetch users with missing configuration."""
        mock_config.return_value = {
            "mobivisor_api_url": None,
            "mobivisor_api_token": "token",
        }

        response = client.get("/api/v1/mobivisor/users")

        assert response.status_code == 500
        assert "Configuration Error" in response.json()["detail"]["error"]


class TestMobivisorDevicePackagesExtended:
    """Extended tests for device package endpoints."""

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_installed_packages_not_found(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test fetching installed packages when device not found."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=404, json_data={"error": "Device not found"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices/999/installed-packages")

        assert response.status_code == 404
        assert "Not Found" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_installed_packages_timeout(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Test fetching installed packages with timeout."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices/123/installed-packages")

        assert response.status_code == 504
        assert "Gateway Timeout" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_installed_packages_forbidden(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test fetching installed packages with forbidden response."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=403, json_data={"error": "Forbidden"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices/123/installed-packages")

        assert response.status_code == 403
        assert "Unauthorized" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_delete_installed_package_not_found(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test deleting installed package when device not found."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=404, json_data={"error": "Device not found"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.delete(
            "/api/v1/mobivisor/devices/999/delete-installed-package/p1"
        )

        assert response.status_code == 404
        assert "Not Found" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_delete_installed_package_forbidden(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test deleting installed package with forbidden response."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=403, json_data={"error": "Forbidden"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.delete(
            "/api/v1/mobivisor/devices/123/delete-installed-package/p1"
        )

        assert response.status_code == 403
        assert "Unauthorized" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_delete_installed_package_timeout(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Test deleting installed package with timeout."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.delete(
            "/api/v1/mobivisor/devices/123/delete-installed-package/p1"
        )

        assert response.status_code == 504
        assert "Gateway Timeout" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_managed_apps_not_found(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test fetching managed apps when device not found."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=404, json_data={"error": "Device not found"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices/999/get-managed-apps")

        assert response.status_code == 404
        assert "Not Found" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_managed_apps_timeout(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Test fetching managed apps with timeout."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices/123/get-managed-apps")

        assert response.status_code == 504
        assert "Gateway Timeout" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_managed_apps_forbidden(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test fetching managed apps with forbidden response."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=403, json_data={"error": "Forbidden"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices/123/get-managed-apps")

        assert response.status_code == 403
        assert "Unauthorized" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_managed_apps_network_error(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Test fetching managed apps with network error."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.RequestError("Network error")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices/123/get-managed-apps")

        assert response.status_code == 502
        assert "Bad Gateway" in response.json()["detail"]["error"]


class TestMobivisorLogs:
    """Tests for the Mobivisor debug logs proxy endpoint."""

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.LogsEndpoint.get_mobivisor_api_config"
    )
    def test_fetch_debug_logs_missing_url(self, mock_config, client):
        """Missing Mobivisor API URL should return 500 Configuration Error."""
        mock_config.return_value = {"mobivisor_api_url": None}
        response = client.get("/api/v1/mobivisor/debuglogs")
        assert response.status_code == 500

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.LogsEndpoint.get_mobivisor_api_config"
    )
    def test_fetch_debug_logs_missing_token(self, mock_config, client):
        """Missing Mobivisor API token should return 500 Configuration Error."""
        mock_config.return_value = {"mobivisor_api_url": "https://test.mobivisor.com/"}
        response = client.get("/api/v1/mobivisor/debuglogs")
        assert response.status_code == 500

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.LogsEndpoint.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_debug_logs_success(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Successful fetch of debug logs should return proxied logs."""
        mock_config.return_value = {
            "mobivisor_api_url": "https://test.mobivisor.com/",
            "mobivisor_api_token": "token",
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"logs": ["line1", "line2"]})

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/debuglogs")
        assert response.status_code == 200
        assert response.json() == {"logs": ["line1", "line2"]}

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.LogsEndpoint.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_debug_logs_timeout(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Upstream timeout should be translated to 504 Gateway Timeout."""
        mock_config.return_value = {
            "mobivisor_api_url": "https://test.mobivisor.com/",
            "mobivisor_api_token": "token",
        }
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/debuglogs")
        assert response.status_code == 504

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.LogsEndpoint.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_debug_logs_network_error(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Network errors contacting Mobivisor should return 502 Bad Gateway."""
        mock_config.return_value = {
            "mobivisor_api_url": "https://test.mobivisor.com/",
            "mobivisor_api_token": "token",
        }
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.RequestError("Network")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/debuglogs")
        assert response.status_code == 502

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.LogsEndpoint.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_debug_logs_unauthorized(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Upstream 401 Unauthorized should be proxied as 401 with details."""
        mock_config.return_value = {
            "mobivisor_api_url": "https://test.mobivisor.com/",
            "mobivisor_api_token": "token",
        }
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json = MagicMock(return_value={"error": "Unauthorized"})

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/debuglogs")
        assert response.status_code == 401
        assert "Unauthorized" in response.json()["detail"]["error"]


class TestMobivisorGroupsEndpoints:
    """Test cases for Mobivisor groups endpoints."""

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_groups_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test successful groups list fetch."""
        mock_config.return_value = mock_mobivisor_config
        groups_data = {
            "groups": [
                {"id": "g1", "name": "Group 1", "device_count": 5},
                {"id": "g2", "name": "Group 2", "device_count": 3},
            ]
        }
        mock_response = mock_httpx_response(status_code=200, json_data=groups_data)

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/groups")

        assert response.status_code == 200
        assert response.json() == groups_data

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    def test_fetch_groups_missing_url(self, mock_config, client):
        """Test groups fetch with missing URL configuration."""
        mock_config.return_value = {
            "mobivisor_api_url": None,
            "mobivisor_api_token": "test-token",
        }

        response = client.get("/api/v1/mobivisor/groups")

        assert response.status_code == 500
        assert "Configuration Error" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    def test_fetch_groups_missing_token(self, mock_config, client):
        """Test groups fetch with missing token configuration."""
        mock_config.return_value = {
            "mobivisor_api_url": "https://test.mobivisor.com/",
            "mobivisor_api_token": None,
        }

        response = client.get("/api/v1/mobivisor/groups")

        assert response.status_code == 500
        assert "Configuration Error" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_groups_unauthorized(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test groups fetch with unauthorized response."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=401, json_data={"error": "Unauthorized"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/groups")

        assert response.status_code == 401
        assert "Unauthorized" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_groups_timeout(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
    ):
        """Test groups fetch with timeout error."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Request timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/groups")

        assert response.status_code == 504
        assert "Gateway Timeout" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_groups_network_error(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Test groups fetch with network error."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.RequestError("Network error")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/groups")

        assert response.status_code == 502
        assert "Bad Gateway" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_delete_group_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test successful group deletion."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(status_code=204, json_data={}, text="")

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.delete("/api/v1/mobivisor/groups/g1")

        assert response.status_code == 204 or response.status_code == 200

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    def test_delete_group_missing_url(self, mock_config, client):
        """Test group deletion with missing URL configuration."""
        mock_config.return_value = {
            "mobivisor_api_url": None,
            "mobivisor_api_token": "test-token",
        }

        response = client.delete("/api/v1/mobivisor/groups/g1")

        assert response.status_code == 500
        assert "Configuration Error" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    def test_delete_group_missing_token(self, mock_config, client):
        """Test group deletion with missing token configuration."""
        mock_config.return_value = {
            "mobivisor_api_url": "https://test.mobivisor.com/",
            "mobivisor_api_token": None,
        }

        response = client.delete("/api/v1/mobivisor/groups/g1")

        assert response.status_code == 500
        assert "Configuration Error" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_delete_group_not_found(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test group deletion with not found response."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=404, json_data={"error": "Not Found"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.delete("/api/v1/mobivisor/groups/g1")

        assert response.status_code == 404
        assert "Not Found" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_delete_group_unauthorized(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test group deletion with unauthorized response."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=401, json_data={"error": "Unauthorized"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.delete("/api/v1/mobivisor/groups/g1")

        assert response.status_code == 401
        assert "Unauthorized" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_delete_group_forbidden(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test group deletion with forbidden response."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=403, json_data={"error": "Forbidden"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.delete("/api/v1/mobivisor/groups/g1")

        assert response.status_code == 403
        assert "Unauthorized" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_delete_group_timeout(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
    ):
        """Test group deletion with timeout error."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Request timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.delete("/api/v1/mobivisor/groups/g1")

        assert response.status_code == 504
        assert "Gateway Timeout" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_delete_group_network_error(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Test group deletion with network error."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.RequestError("Network error")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.delete("/api/v1/mobivisor/groups/g1")

        assert response.status_code == 502
        assert "Bad Gateway" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_group_details_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test successful group details fetch."""
        mock_config.return_value = mock_mobivisor_config
        group_data = {"id": "g1", "name": "Store A", "device_count": 15}
        mock_response = mock_httpx_response(status_code=200, json_data=group_data)

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/groups/g1")

        assert response.status_code == 200
        assert response.json() == group_data

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_group_details_not_found(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test group details fetch with not found response."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=404, json_data={"error": "Not Found"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/groups/nonexistent")

        assert response.status_code == 404
        assert "Not Found" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_add_applications_to_group_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test successful add applications to group."""
        mock_config.return_value = mock_mobivisor_config
        payload = {"appIds": ["6895b52aefdcda141d3a8da5"], "appConfigs": []}
        mock_response = mock_httpx_response(status_code=200, json_data={"ok": True})

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.put("/api/v1/mobivisor/groups/g1/applications", json=payload)

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_add_applications_to_group_missing_appIds(self, client):
        """Missing appIds should return 422 validation error."""
        payload = {"appConfigs": []}

        response = client.put("/api/v1/mobivisor/groups/g1/applications", json=payload)

        assert response.status_code == 422
        assert response.json()["detail"]

    def test_add_applications_to_group_invalid_appIds_type(self, client):
        """When the `appIds` field is not a list, returns 422."""
        payload = {"appIds": "not-a-list", "appConfigs": []}

        response = client.put("/api/v1/mobivisor/groups/g1/applications", json=payload)

        assert response.status_code == 422
        assert response.json()["detail"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_add_applications_to_group_unauthorized(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Upstream unauthorized response should be proxied."""
        mock_config.return_value = mock_mobivisor_config
        payload = {"appIds": ["6895b52aefdcda141d3a8da5"], "appConfigs": []}
        mock_response = mock_httpx_response(
            status_code=401, json_data={"error": "Unauthorized"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.put("/api/v1/mobivisor/groups/g1/applications", json=payload)

        assert response.status_code == 401
        assert "Unauthorized" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_add_applications_to_group_timeout(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Upstream timeout should return 504 Gateway Timeout."""
        mock_config.return_value = mock_mobivisor_config

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        payload = {"appIds": ["6895b52aefdcda141d3a8da5"], "appConfigs": []}
        response = client.put("/api/v1/mobivisor/groups/g1/applications", json=payload)

        assert response.status_code == 504
        assert "Gateway Timeout" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_add_applications_to_group_network_error(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Network errors should return 502 Bad Gateway."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.RequestError("Network")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        payload = {"appIds": ["6895b52aefdcda141d3a8da5"], "appConfigs": []}
        response = client.put("/api/v1/mobivisor/groups/g1/applications", json=payload)

        assert response.status_code == 502
        assert "Bad Gateway" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_add_users_to_group_success(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test successful add users to group."""
        mock_config.return_value = mock_mobivisor_config
        payload = {
            "users": [
                "6807a5836415f4ed1ee081ea",
                "680a4cb660e6a191fc7e1d15",
            ]
        }
        mock_response = mock_httpx_response(status_code=200, json_data={"ok": True})

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.put("/api/v1/mobivisor/groups/g1/users", json=payload)

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_add_users_to_group_missing_users(self, client):
        """Missing users should return 422 validation error."""
        payload = {}

        response = client.put("/api/v1/mobivisor/groups/g1/users", json=payload)

        assert response.status_code == 422
        assert response.json()["detail"]

    def test_add_users_to_group_invalid_users_type(self, client):
        """When the `users` field is not a list, returns 422."""
        payload = {"users": "not-a-list"}

        response = client.put("/api/v1/mobivisor/groups/g1/users", json=payload)

        assert response.status_code == 422
        assert response.json()["detail"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_add_users_to_group_unauthorized(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Upstream unauthorized response should be proxied."""
        mock_config.return_value = mock_mobivisor_config
        payload = {"users": ["6807a5836415f4ed1ee081ea"]}
        mock_response = mock_httpx_response(
            status_code=401, json_data={"error": "Unauthorized"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.put("/api/v1/mobivisor/groups/g1/users", json=payload)

        assert response.status_code == 401
        assert "Unauthorized" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_add_users_to_group_timeout(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Upstream timeout should return 504 Gateway Timeout."""
        mock_config.return_value = mock_mobivisor_config

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        payload = {"users": ["6807a5836415f4ed1ee081ea"]}
        response = client.put("/api/v1/mobivisor/groups/g1/users", json=payload)

        assert response.status_code == 504
        assert "Gateway Timeout" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_add_users_to_group_network_error(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Network errors should return 502 Bad Gateway."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.RequestError("Network")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        payload = {"users": ["6807a5836415f4ed1ee081ea"]}
        response = client.put("/api/v1/mobivisor/groups/g1/users", json=payload)

        assert response.status_code == 502
        assert "Bad Gateway" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_group_details_unauthorized(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test group details fetch with unauthorized response (401)."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=401, json_data={"error": "Unauthorized"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/groups/g1")

        assert response.status_code == 401
        assert "Unauthorized" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_group_details_forbidden(
        self,
        mock_async_client,
        mock_config,
        client,
        mock_mobivisor_config,
        mock_httpx_response,
    ):
        """Test group details fetch with forbidden response (403)."""
        mock_config.return_value = mock_mobivisor_config
        mock_response = mock_httpx_response(
            status_code=403, json_data={"error": "Forbidden"}
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/groups/g1")

        assert response.status_code == 403
        assert "Unauthorized" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_group_details_timeout(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Test group details fetch with timeout (504)."""
        mock_config.return_value = mock_mobivisor_config

        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Request timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/groups/g1")

        assert response.status_code == 504
        assert "Gateway Timeout" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor."
        "MobivisorGroupsEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_group_details_network_error(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Test group details fetch with network error (502)."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.RequestError("Network error")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/groups/g1")

        assert response.status_code == 502
        assert "Bad Gateway" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_device_policies_success(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Successful fetch of device policies should return proxied JSON."""
        mock_config.return_value = mock_mobivisor_config

        mock_client_instance = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"policies": [{"id": "p1"}]})
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices/123/policies")

        assert response.status_code == 200
        assert response.json() == {"policies": [{"id": "p1"}]}

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    def test_fetch_device_policies_missing_url(self, mock_config, client):
        """Missing base URL should return 500 Configuration Error."""
        mock_config.return_value = {}
        response = client.get("/api/v1/mobivisor/devices/123/policies")
        assert response.status_code == 500
        assert "Configuration Error" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    def test_fetch_device_policies_missing_token(self, mock_config, client):
        """Missing token should return 500 Configuration Error."""
        mock_config.return_value = {"mobivisor_api_url": "https://test.mobivisor.com/"}
        response = client.get("/api/v1/mobivisor/devices/123/policies")
        assert response.status_code == 500
        assert "Configuration Error" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_device_policies_timeout(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Upstream timeout should return 504 Gateway Timeout."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices/123/policies")
        assert response.status_code == 504
        assert "Gateway Timeout" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_device_policies_network_error(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Network/request errors should return 502 Bad Gateway."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(
            side_effect=httpx.RequestError("Network")
        )
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices/123/policies")
        assert response.status_code == 502
        assert "Bad Gateway" in response.json()["detail"]["error"]

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_device_policies_not_found(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """An upstream 404 should be translated to a local 404."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json = MagicMock(return_value={"error": "Not Found"})
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices/unknown/policies")
        assert response.status_code == 404
        assert (
            "Not Found" in response.json()["detail"]["error"]
            or response.json()["detail"]["error"] == "Not Found"
        )

    @patch(
        "homepot.app.api.API_v1.Endpoints.Mobivisor.MobivisorDeviceEndpoints.get_mobivisor_api_config"
    )
    @patch("httpx.AsyncClient")
    def test_fetch_device_policies_unauthorized(
        self, mock_async_client, mock_config, client, mock_mobivisor_config
    ):
        """Upstream 401/403 should be proxied as-is."""
        mock_config.return_value = mock_mobivisor_config
        mock_client_instance = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json = MagicMock(return_value={"error": "Unauthorized"})
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        response = client.get("/api/v1/mobivisor/devices/123/policies")
        assert response.status_code == 401
        assert "Unauthorized" in response.json()["detail"]["error"]
