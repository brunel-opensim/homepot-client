"""API endpoints for managing Mobivisor Device Data in the HomePot system.

This module provides proxy endpoints to interact with the external Mobivisor
device management service. All requests are forwarded to the Mobivisor API
with proper authentication and error handling.
"""

import logging
from typing import Any, Dict

import httpx
from fastapi import APIRouter, HTTPException

from homepot_client.config import get_mobivisor_api_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Constants
DEFAULT_TIMEOUT_TOTAL = 10.0
DEFAULT_TIMEOUT_CONNECT = 5.0


async def _make_mobivisor_request(
    method: str, endpoint: str, **kwargs: Any
) -> httpx.Response:
    """Make HTTP request to Mobivisor API with proper authentication.

    Args:
        method: HTTP method (GET, POST, DELETE, etc.)
        endpoint: API endpoint path (e.g., "devices" or "devices/123")
        **kwargs: Additional arguments to pass to httpx request

    Returns:
        httpx.Response: The response from Mobivisor API

    Raises:
        HTTPException: If configuration is missing or request fails
    """
    mobivisor_config = get_mobivisor_api_config()
    base_url = mobivisor_config.get("mobivisor_api_url")
    auth_token = mobivisor_config.get("mobivisor_api_token")

    # Validate configuration
    if not base_url:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Configuration Error",
                "message": "Mobivisor API URL is not configured",
            },
        )

    if not auth_token:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Configuration Error",
                "message": "Mobivisor API token is not configured",
            },
        )

    # Ensure base_url ends with /
    if not base_url.endswith("/"):
        base_url += "/"

    upstream_url = f"{base_url}{endpoint}"
    headers = {"Authorization": f"Bearer {auth_token}"}
    timeout = httpx.Timeout(DEFAULT_TIMEOUT_TOTAL, connect=DEFAULT_TIMEOUT_CONNECT)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=method, url=upstream_url, headers=headers, **kwargs
            )
        return response

    except httpx.TimeoutException:
        logger.error(f"Timeout contacting Mobivisor API: {upstream_url}")
        raise HTTPException(
            status_code=504,
            detail={
                "error": "Gateway Timeout",
                "message": "Mobivisor API did not respond in time",
            },
        )
    except httpx.RequestError as e:
        logger.error(f"Network error contacting Mobivisor API: {e}")
        raise HTTPException(
            status_code=502,
            detail={
                "error": "Bad Gateway",
                "message": "Failed to contact Mobivisor API",
            },
        )


def _handle_mobivisor_response(
    response: httpx.Response, operation: str = "operation"
) -> Dict[str, Any]:
    """Handle Mobivisor API response with consistent error mapping.

    Args:
        response: The HTTP response from Mobivisor API
        operation: Description of the operation (for error messages)

    Returns:
        Dict[str, Any]: JSON response data

    Raises:
        HTTPException: If the response indicates an error
    """
    if response.status_code in (200, 204):
        try:
            return response.json() if response.content else {}
        except Exception:
            return {}

    # Handle error responses
    error_detail = {
        "error": "Unknown Error",
        "message": f"Mobivisor API {operation} failed",
    }

    try:
        upstream_error = response.json()
        error_detail.update(upstream_error)
    except Exception:
        error_detail["message"] = response.text or error_detail["message"]

    if response.status_code in (401, 403):
        raise HTTPException(
            status_code=response.status_code,
            detail={
                "error": "Unauthorized",
                "message": "Invalid or missing Bearer token for Mobivisor API",
                "upstream_status": response.status_code,
            },
        )
    elif response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Not Found",
                "message": "Resource not found on Mobivisor API",
                "upstream_error": error_detail,
            },
        )
    else:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "Bad Gateway",
                "message": f"Mobivisor API returned error {response.status_code}",
                "upstream_status": response.status_code,
                "upstream_error": error_detail,
            },
        )


@router.get("/devices", tags=["Mobivisor Devices"])
async def fetch_external_devices() -> Any:
    """Fetch all devices from Mobivisor API.

    This endpoint proxies the request to the external Mobivisor device management
    service and returns the list of all devices.

    Returns:
        Any: JSON response from Mobivisor API containing device list

    Raises:
        HTTPException: If configuration is missing or API request fails

    Example:
        ```python
        GET /api/v1/mobivisor/devices
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
    logger.info("Fetching devices from Mobivisor API")
    response = await _make_mobivisor_request("GET", "devices")
    return _handle_mobivisor_response(response, "fetch devices")


@router.get("/devices/{device_id}", tags=["Mobivisor Devices"])
async def fetch_device_details(device_id: str) -> Dict[str, Any]:
    """Fetch details for a specific device from Mobivisor API.

    Args:
        device_id: The unique identifier of the device

    Returns:
        Dict[str, Any]: JSON response from Mobivisor API containing device details

    Raises:
        HTTPException: If configuration is missing, device not found, or API request fails

    Example:
        ```python
        GET /api/v1/mobivisor/devices/123
        ```

        Response:
        ```json
        {
            "id": "123",
            "name": "Device 1",
            "status": "online",
            "last_seen": "2025-10-18T10:30:00Z"
        }
        ```
    """
    logger.info(f"Fetching device details from Mobivisor API: {device_id}")
    response = await _make_mobivisor_request("GET", f"devices/{device_id}")
    return _handle_mobivisor_response(response, f"fetch device {device_id}")


@router.delete("/devices/{device_id}", tags=["Mobivisor Devices"])
async def delete_device(device_id: str) -> Dict[str, Any]:
    """Delete a specific device from Mobivisor API.

    Args:
        device_id: The unique identifier of the device to delete

    Returns:
        Dict[str, Any]: Success message with deleted device ID

    Raises:
        HTTPException: If configuration is missing, device not found, or API request fails

    Example:
        ```python
        DELETE /api/v1/mobivisor/devices/123
        ```

        Response:
        ```json
        {
            "message": "Device deleted successfully",
            "device_id": "123"
        }
        ```
    """
    logger.info(f"Deleting device from Mobivisor API: {device_id}")
    response = await _make_mobivisor_request("DELETE", f"devices/{device_id}")
    _handle_mobivisor_response(response, f"delete device {device_id}")

    return {"message": "Device deleted successfully", "device_id": device_id}
