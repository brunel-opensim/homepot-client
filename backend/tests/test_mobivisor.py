"""Tests for Mobivisor API endpoints.

This module contains unit tests for the Mobivisor device integration endpoints.
Tests mock the httpx client to avoid actual API calls during testing.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from homepot_client.app.main import app


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
        "homepot_client.app.api.API_v1.Endpoints.Mobivisor."
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
        "homepot_client.app.api.API_v1.Endpoints.Mobivisor."
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
        "homepot_client.app.api.API_v1.Endpoints.Mobivisor."
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
        "homepot_client.app.api.API_v1.Endpoints.Mobivisor."
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
        "homepot_client.app.api.API_v1.Endpoints.Mobivisor."
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
        "homepot_client.app.api.API_v1.Endpoints.Mobivisor."
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

    @patch("homepot_client.config.get_mobivisor_api_config")
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
        "homepot_client.app.api.API_v1.Endpoints.Mobivisor."
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
        "homepot_client.app.api.API_v1.Endpoints.Mobivisor."
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

        response = client.delete("/api/v1/mobivisor/devices/999")

        assert response.status_code == 404
        assert "Not Found" in response.json()["detail"]["error"]

    @patch(
        "homepot_client.app.api.API_v1.Endpoints.Mobivisor."
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
        "homepot_client.app.api.API_v1.Endpoints.Mobivisor."
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

    @patch(
        "homepot_client.app.api.API_v1.Endpoints.Mobivisor."
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
