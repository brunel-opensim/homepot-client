"""Tests for Google Login (SSO) integration."""

import os
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

# Set environment variables
os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"
os.environ["GOOGLE_REDIRECT_URI"] = "http://localhost:5173/auth/callback"
os.environ["FRONTEND_URL"] = "http://localhost:5173"

import homepot.app.auth_utils  # noqa: E402

# Force constants
homepot.app.auth_utils.GOOGLE_CLIENT_ID = "test-client-id"
homepot.app.auth_utils.GOOGLE_CLIENT_SECRET = "test-client-secret"
homepot.app.auth_utils.GOOGLE_REDIRECT_URI = "http://localhost:5173/auth/callback"
homepot.app.auth_utils.FRONTEND_URL = "http://localhost:5173"

from homepot.app.auth_utils import (  # noqa: E402
    exchange_google_code,
    get_or_create_google_user,
    verify_google_token,
)
from homepot.main import app  # noqa: E402


def test_google_login_url_generation():
    """Test that the login endpoint returns a valid Google OAuth URL."""
    client = TestClient(app)
    with (
        patch(
            "homepot.app.api.API_v1.Endpoints.UserRegisterEndpoint.GOOGLE_CLIENT_ID",
            "test-client-id",
        ),
        patch(
            "homepot.app.api.API_v1.Endpoints.UserRegisterEndpoint.GOOGLE_REDIRECT_URI",
            "http://localhost:5173/auth/callback",
        ),
    ):
        response = client.get("/api/v1/auth/login")
        assert response.status_code == 200
        data = response.json()
        assert "auth_url" in data
        assert data["auth_url"].startswith(
            "https://accounts.google.com/o/oauth2/v2/auth"
        )
        assert "client_id=test-client-id" in data["auth_url"]


@patch("homepot.app.auth_utils.requests.post")
def test_exchange_google_code_success(mock_post):
    """Test exchanging an authorization code for a Google token."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id_token": "fake-id-token"}
    mock_post.return_value = mock_response

    tokens = exchange_google_code("valid-auth-code")
    assert tokens["id_token"] == "fake-id-token"


@patch("homepot.app.auth_utils.id_token.verify_oauth2_token")
@patch("homepot.app.auth_utils.google_requests.Request")
def test_verify_google_token_success(mock_request, mock_verify):
    """Test verifying a Google ID token."""
    mock_verify.return_value = {
        "email": "testuser@example.com",
        "name": "Test User",
        "sub": "google-123",
    }
    info = verify_google_token("fake-token")
    assert info["email"] == "testuser@example.com"


def test_get_or_create_google_user_logic(temp_db):
    """Test user creation and retrieval logic directly in DB."""
    db = temp_db()

    # 1. Test New User Creation
    idinfo = {"email": "sso-new@example.com", "name": "New User"}
    user = get_or_create_google_user(db, idinfo)
    assert user.email == "sso-new@example.com"

    # 2. Test Existing User Retrieval
    user2 = get_or_create_google_user(db, idinfo)
    assert user.id == user2.id

    db.close()


@patch("homepot.app.api.API_v1.Endpoints.UserRegisterEndpoint.exchange_google_code")
@patch("homepot.app.api.API_v1.Endpoints.UserRegisterEndpoint.verify_google_token")
@patch(
    "homepot.app.api.API_v1.Endpoints.UserRegisterEndpoint.get_or_create_google_user"
)
def test_google_callback_endpoint_flow(mock_get_user, mock_verify, mock_exchange):
    """Test the full callback endpoint flow by mocking logic layers."""
    mock_exchange.return_value = {"id_token": "fake-id"}
    mock_verify.return_value = {
        "email": "callback@example.com",
        "name": "Callback User",
    }

    # Mock the DB user object response
    mock_user = MagicMock()
    mock_user.email = "callback@example.com"
    mock_user.is_admin = False
    mock_get_user.return_value = mock_user

    client = TestClient(app)

    with patch(
        "homepot.app.api.API_v1.Endpoints.UserRegisterEndpoint.FRONTEND_URL",
        "http://localhost:5173",
    ):
        response = client.get(
            "/api/v1/auth/callback?code=fake-code", follow_redirects=False
        )

    # Verify response
    assert response.status_code == 307
    assert "http://localhost:5173/dashboard" in response.headers["location"]
    assert "access_token" in response.cookies

    # Verify the logic was called correctly
    mock_exchange.assert_called_once_with("fake-code")
    mock_verify.assert_called_once_with("fake-id")
    mock_get_user.assert_called_once()
