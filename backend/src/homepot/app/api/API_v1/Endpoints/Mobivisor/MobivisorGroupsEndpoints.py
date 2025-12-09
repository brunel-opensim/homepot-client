"""API endpoints for managing Mobivisor Device Data in the HomePot system.

This module provides proxy endpoints to interact with the external Mobivisor
device management service. All requests are forwarded to the Mobivisor API
with proper authentication and error handling.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

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
            "devices": [
                {"id": "123", "name": "Device 1", "status": "online"},
                {"id": "456", "name": "Device 2", "status": "offline"}
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
    print(response.text, "response")
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
