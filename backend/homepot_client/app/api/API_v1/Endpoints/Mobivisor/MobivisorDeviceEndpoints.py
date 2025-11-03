"""API endpoints for managing Mobivisor Device Data in the HomePot system.

This module provides proxy endpoints to interact with the external Mobivisor
device management service. All requests are forwarded to the Mobivisor API
with proper authentication and error handling.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter

from homepot_client.app.utils.mobivisor_request import (
    _handle_mobivisor_response as handle_mobivisor_response,
)
from homepot_client.app.utils.mobivisor_request import (
    _make_mobivisor_request as make_mobivisor_request,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


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
    response = await make_mobivisor_request("GET", "devices")
    return handle_mobivisor_response(response, "fetch devices")


@router.get("/devices/{device_id}", tags=["Mobivisor Devices"])
async def fetch_device_details(device_id: str) -> Dict[str, Any]:
    """Fetch details for a specific device from Mobivisor API.

    Args:
        device_id: The unique identifier of the device

    Returns:
        Dict[str, Any]: JSON response from Mobivisor API with device details

    Raises:
        HTTPException: If configuration missing, device not found, or request fails

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
    response = await make_mobivisor_request("GET", f"devices/{device_id}")
    return handle_mobivisor_response(response, f"fetch device {device_id}")


@router.delete("/devices/{device_id}", tags=["Mobivisor Devices"])
async def delete_device(device_id: str) -> Dict[str, Any]:
    """Delete a specific device from Mobivisor API.

    Args:
        device_id: The unique identifier of the device to delete

    Returns:
        Dict[str, Any]: Success message with deleted device ID

    Raises:
        HTTPException: If configuration missing, device not found, or request fails

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
    response = await make_mobivisor_request("DELETE", f"devices/{device_id}")
    handle_mobivisor_response(response, f"delete device {device_id}")

    return {"message": "Device deleted successfully", "device_id": device_id}
