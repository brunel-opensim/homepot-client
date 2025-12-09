"""API endpoints for managing Mobivisor User Data in the HomePot system.

This module provides proxy endpoints to interact with the external Mobivisor
user management service. All requests are forwarded to the Mobivisor API
with proper authentication and error handling.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from homepot.app.models.mobivisor_models import (
    CreateUserPayload,
    UpdateUserPayload,
)
from homepot.app.utils.mobivisor_request import (
    _handle_mobivisor_response as handle_mobivisor_response,
)
from homepot.app.utils.mobivisor_request import (
    _make_mobivisor_request as make_mobivisor_request,
)
from homepot.config import get_mobivisor_api_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


# Models moved to `homepot.app.models.mobivisor_models` to keep them
# separate from the application's DB model definitions (no SQLAlchemy here).


@router.get("/users", tags=["Mobivisor Users"])
async def fetch_mobivisor_users() -> Any:
    """Fetch all users from Mobivisor API.

    This endpoint proxies the request to the external Mobivisor user management
    service and returns the list of all users.

    Returns:
        Any: JSON response from Mobivisor API containing user list

    Raises:
        HTTPException: If configuration is missing or API request fails

    Example:
        ```python
        GET /api/v1/mobivisor/users
        ```

        Response:
        ```json
        {
            "users": [
                {"id": "123", "name": "User 1", "status": "online"},
                {"id": "456", "name": "User 2", "status": "offline"}
            ]
        }
        ```
    """
    config = get_mobivisor_api_config()
    if not config.get("mobivisor_api_url"):
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Configuration Error",
                "message": "Missing Mobivisor API URL.",
            },
        )

    auth_token = config.get("mobivisor_api_token")
    if not auth_token:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Configuration Error",
                "message": "Mobivisor API token is not configured",
            },
        )
    logger.info("Fetching users from Mobivisor API")
    response = await make_mobivisor_request("GET", "users", config=config)
    return handle_mobivisor_response(response, "fetch users")


@router.get("/users/{user_id}", tags=["Mobivisor Users"])
async def fetch_user_details(user_id: str) -> Dict[str, Any]:
    """Fetch details for a specific User from Mobivisor API.

    Args:
        user_id: The unique identifier of the user

    Returns:
        Dict[str, Any]: JSON response from Mobivisor API with user details

    Raises:
        HTTPException: If configuration missing, user not found, or request fails

    Example:
        ```python
        GET /api/v1/mobivisor/users/123
        ```

        Response:
        ```json
        {
            "id": "123",
            "name": "User 1",
            "status": "online",
            "last_seen": "2025-10-18T10:30:00Z"
        }
        ```
    """
    logger.info(f"Fetching user details from Mobivisor API: {user_id}")
    config = get_mobivisor_api_config()
    response = await make_mobivisor_request("GET", f"users/{user_id}", config=config)
    return handle_mobivisor_response(response, f"fetch user {user_id}")


@router.delete("/users/{user_id}", tags=["Mobivisor Users"])
async def delete_user(user_id: str) -> Dict[str, Any]:
    """Delete a specific user from Mobivisor API.

    Args:
        user_id: The unique identifier of the user to delete

    Returns:
        Dict[str, Any]: Success message with deleted user ID

    Raises:
        HTTPException: If configuration missing, user not found, or request fails

    Example:
        ```python
        DELETE /api/v1/mobivisor/users/123
        ```

        Response:
        ```json
        {
            "message": "User deleted successfully",
            "user_id": "123"
        }
        ```
    """
    logger.info(f"Deleting user from Mobivisor API: {user_id}")
    config = get_mobivisor_api_config()
    response = await make_mobivisor_request("DELETE", f"users/{user_id}", config=config)
    handle_mobivisor_response(response, f"delete user {user_id}")

    return {"message": "User deleted successfully", "user_id": user_id}


@router.post("/users", tags=["Mobivisor Users"])
async def create_user(payload: CreateUserPayload) -> Any:
    """Create a new user in Mobivisor.

    Proxies a POST to the Mobivisor `/users` endpoint. The request body should
    include a `user` object and optionally `groupInfoOfTheUser` as shown below.

    Args:
        payload: The JSON body to forward to Mobivisor. Expected shape:

        {
            "user": {
                "email": "jr.kothiya@gmail.com",
                "displayName": "Kothiya Yogesh",
                "username": "jr.kothiya",
                "phone": "7567407883",
                "password": "1234567890",
                "notes": "Test",
                "role": {"_id": "Admin", "rights": [], "displayedRights": []}
            },
            "groupInfoOfTheUser": [{"_id": "6895b47e634b34c01c2d69c4"}]
        }

    Returns:
        Any: The JSON response from Mobivisor (typically the created user or
        an acknowledgement).

    Raises:
        HTTPException: If configuration is missing or the upstream request
        fails; upstream errors are mapped to appropriate HTTP status codes.

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/mobivisor/users" \
          -H "Content-Type: application/json" \
          -d '{"user": {...}, "groupInfoOfTheUser": [...] }'
        ```
    """
    logger.info("Creating user in Mobivisor API")
    config = get_mobivisor_api_config()

    if not config.get("mobivisor_api_url"):
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Configuration Error",
                "message": "Missing Mobivisor API URL.",
            },
        )

    auth_token = config.get("mobivisor_api_token")
    if not auth_token:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Configuration Error",
                "message": "Mobivisor API token is not configured",
            },
        )

    response = await make_mobivisor_request(
        "POST", "users", json=payload.model_dump(), config=config
    )
    return handle_mobivisor_response(response, "create user")


@router.put("/users/{user_id}", tags=["Mobivisor Users"])
async def update_user(user_id: str, payload: UpdateUserPayload) -> Any:
    """Update an existing user in Mobivisor.

    This endpoint proxies a PUT to the Mobivisor `/users/{user_id}` endpoint.
    The request body should include a `user` object and optionally
    `groupInfoOfTheUser` (same shape as the create endpoint).

    Args:
        user_id: The user's unique identifier to update.
        payload: The JSON body to forward to Mobivisor.

    Returns:
        Any: The JSON response from Mobivisor (typically the updated user).

    Raises:
        HTTPException: If configuration is missing or the upstream request
        fails; upstream errors are mapped to appropriate HTTP status codes.
    """
    logger.info(f"Updating user in Mobivisor API: {user_id}")
    config = get_mobivisor_api_config()

    if not config.get("mobivisor_api_url"):
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Configuration Error",
                "message": "Missing Mobivisor API URL.",
            },
        )

    auth_token = config.get("mobivisor_api_token")
    if not auth_token:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Configuration Error",
                "message": "Mobivisor API token is not configured",
            },
        )

    # Only forward fields provided by the client to the upstream API.
    body = payload.model_dump(exclude_none=True)
    response = await make_mobivisor_request(
        "PUT", f"users/{user_id}", json=body, config=config
    )
    return handle_mobivisor_response(response, f"update user {user_id}")
