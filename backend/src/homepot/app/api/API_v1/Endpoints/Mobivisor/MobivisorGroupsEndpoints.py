"""API endpoints for managing Mobivisor Device Data in the HomePot system.

This module provides proxy endpoints to interact with the external Mobivisor
device management service. All requests are forwarded to the Mobivisor API
with proper authentication and error handling.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from homepot.app.models.mobivisor_models import (
    CreateGroupPayload,
    UpdateGroupPayload,
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


class AddGroupApplicationsPayload(BaseModel):
    """Payload for adding applications to a Mobivisor group.

    Fields:
    - appIds: list of application IDs to add (required)
    - appConfigs: optional list of application configuration objects
    """

    appIds: List[str]
    appConfigs: List[Dict] = []


class AddGroupUsersPayload(BaseModel):
    """Payload for adding users to a Mobivisor group.

    Fields:
    - users: list of user IDs to add (required)
    """

    users: List[str]


@router.get("/groups", tags=["Mobivisor Groups"])
async def fetch_groups() -> Any:
    """Fetch all groups from Mobivisor API.

    This endpoint proxies the request to the external Mobivisor device management
    service and returns the list of all groups.

    Returns:
        Any: JSON response from Mobivisor API containing group list

    Raises:
        HTTPException: If configuration is missing or API request fails

    Example:
        ```python
        GET /api/v1/mobivisor/groups
        ```

        Response:
        ```json
        {
            "groups": [
                {"id": "123", "name": "Group 1"},
                {"id": "456", "name": "Group 2"}
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
    logger.info("Fetching groups from Mobivisor API")
    response = await make_mobivisor_request("GET", "groups", config=config)
    return handle_mobivisor_response(response, "fetch groups")


@router.delete("/groups/{group_id}", tags=["Mobivisor Groups"])
async def delete_group(group_id: str) -> Any:
    """Delete a specific group from the Mobivisor API.

    Args:
        group_id (str): The unique identifier of the group to delete.

    Returns:
        Dict[str, Any]: JSON response from the Mobivisor API confirming the deletion.

    Raises:
        HTTPException: If configuration is missing, the group is not found,
                       or the delete request fails.

    Example:
        ```python
        DELETE /api/v1/mobivisor/groups/123
        ```

        Response:
        ```json
        [
            {
                "ok": 1,
                "n": 1,
                "opTime": {
                    "ts": "7580234308091117575",
                    "t": 185
                },
                "electionId": "7fffffff00000000000000b9"
            }
        ]
        ```
    """
    logger.info(f"Deleting group from Mobivisor API: {group_id}")
    config = get_mobivisor_api_config()
    response = await make_mobivisor_request(
        "DELETE", f"groups/{group_id}", config=config
    )
    return handle_mobivisor_response(response, f"delete group {group_id}")


@router.get("/groups/{group_id}", tags=["Mobivisor Groups"])
async def fetch_group_details(group_id: str) -> Any:
    """Fetch details for a specific group from Mobivisor API.

    Args:
        group_id: The unique identifier of the group

    Returns:
        Any: JSON response from Mobivisor API with group details

    Raises:
        HTTPException: If configuration missing, group not found, or request fails

    Example:
        ```python
        GET /api/v1/mobivisor/groups/g1
        ```

        Response:
        ```json
        {
            "id": "g1",
            "name": "Store A - Devices",
            "device_count": 15,
            "created_at": "2025-10-01T12:00:00Z"
        }
        ```
    """
    logger.info(f"Fetching group details from Mobivisor API: {group_id}")
    config = get_mobivisor_api_config()
    response = await make_mobivisor_request("GET", f"groups/{group_id}", config=config)
    return handle_mobivisor_response(response, f"fetch group {group_id}")


@router.put("/groups/{group_id}/applications", tags=["Mobivisor Groups"])
async def add_applications_to_group(
    group_id: str, payload: AddGroupApplicationsPayload
) -> Any:
    """Add applications to a Mobivisor group.

    Proxies a PUT to Mobivisor at `/groups/{group_id}/applications`.

    Args:
        group_id: The group identifier (path param).
        payload: JSON body containing `appIds` (required) and optional `appConfigs`.

    Returns:
        JSON response from Mobivisor API.

    Validation:
    - `group_id` is required by the path.
    - `appIds` must be a non-empty list of strings.

        Example:
                ```bash
                curl -X PUT \
                    "/api/v1/mobivisor/groups/<group_id>/applications" \
                    -H "Content-Type: application/json" \
                    -d '{"appIds": ["6895b52aefdcda141d3a8da5"], "appConfigs": []}'
                ```
    """
    # Validate required fields
    if not payload.appIds or len(payload.appIds) == 0:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Validation Error",
                "message": "`appIds` is required and must be a non-empty list",
            },
        )

    config = get_mobivisor_api_config()
    body = payload.model_dump()
    response = await make_mobivisor_request(
        "PUT", f"groups/{group_id}/applications", json=body, config=config
    )
    return handle_mobivisor_response(response, f"add applications to group {group_id}")


@router.put("/groups/{group_id}/users", tags=["Mobivisor Groups"])
async def add_users_to_group(group_id: str, payload: AddGroupUsersPayload) -> Any:
    """Add users to a Mobivisor group.

    Proxies a PUT to Mobivisor at `/groups/{group_id}/users`.

    Args:
        group_id: The group identifier (path param).
        payload: JSON body containing `users` (required).

    Returns:
        JSON response from Mobivisor API.

    Validation:
    - `group_id` is required by the path.
    - `users` must be a non-empty list of user ID strings.

        Example:
                ```bash
                curl -X PUT \
                    "/api/v1/mobivisor/groups/<group_id>/users" \
                    -H "Content-Type: application/json" \
                    -d '{"users": ["6807a5836415f4ed1ee081ea"]}'
                ```
    """
    # Validate required fields
    if not payload.users or len(payload.users) == 0:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Validation Error",
                "message": "`users` is required and must be a non-empty list",
            },
        )

    config = get_mobivisor_api_config()
    body = payload.model_dump()
    response = await make_mobivisor_request(
        "PUT", f"groups/{group_id}/users", json=body, config=config
    )
    return handle_mobivisor_response(response, f"add users to group {group_id}")


@router.post("/groups", tags=["Mobivisor Groups"])
async def create_group(payload: CreateGroupPayload) -> Any:
    """Create a new Mobivisor group.

    Expects JSON body with `name` and optional `description` and `metadata`.
    """
    # Basic validation is handled by Pydantic, but check config
    config = get_mobivisor_api_config()
    if not config.get("mobivisor_api_url"):
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Configuration Error",
                "message": "Missing Mobivisor API URL.",
            },
        )

    body = payload.model_dump()
    response = await make_mobivisor_request("POST", "groups", json=body, config=config)
    return handle_mobivisor_response(response, "create group")


@router.put("/groups/{group_id}", tags=["Mobivisor Groups"])
async def update_group(group_id: str, payload: UpdateGroupPayload) -> Any:
    """Update an existing Mobivisor group (partial updates allowed).

    Uses `model_dump(exclude_none=True)` to forward only provided fields.
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

    body = payload.model_dump(exclude_none=True)
    if not body:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Validation Error",
                "message": "At least one field must be provided to update.",
            },
        )

    response = await make_mobivisor_request(
        "PUT", f"groups/{group_id}", json=body, config=config
    )
    return handle_mobivisor_response(response, f"update group {group_id}")
