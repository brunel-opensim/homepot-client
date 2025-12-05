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
