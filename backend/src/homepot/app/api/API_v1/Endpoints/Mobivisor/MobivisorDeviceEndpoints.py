"""API endpoints for managing Mobivisor Device Data in the HomePot system.

This module provides proxy endpoints to interact with the external Mobivisor
device management service. All requests are forwarded to the Mobivisor API
with proper authentication and error handling.
"""

import logging
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

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


class DeviceCommandData(BaseModel):
    """Represents the dynamic payload Mobivisor expects for device actions."""

    password: Optional[str] = Field(default=None, min_length=1)
    sendApps: Optional[bool] = None
    userId: Optional[str] = None
    userSwitched: Optional[bool] = None


CommandTypeLiteral = Literal[
    "change_password_now",
    "update_settings",
    "refresh_kiosk",
    "pref_update",
    "location_request",
    "status_request",
    "password_token_request",
    "fetch_system_apps",
]


class DeviceCommandPayload(BaseModel):
    """Top level payload for triggering downstream Mobivisor device actions."""

    deviceId: str = Field(..., min_length=1)
    commandType: CommandTypeLiteral
    commandData: DeviceCommandData

    @model_validator(mode="after")
    def validate_command_requirements(self) -> "DeviceCommandPayload":
        """Ensure commandData contains the required keys per command type."""
        if self.commandType == "change_password_now" and not self.commandData.password:
            raise ValueError(
                "commandData.password is required when commandType"
                " is change_password_now"
            )

        if self.commandType == "update_settings" and self.commandData.sendApps is None:
            raise ValueError(
                "commandData.sendApps is required when commandType is update_settings"
            )

        return self


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
    logger.info("Fetching devices from Mobivisor API")
    response = await make_mobivisor_request("GET", "devices", config=config)
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
    config = get_mobivisor_api_config()
    response = await make_mobivisor_request(
        "GET", f"devices/{device_id}", config=config
    )
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
    config = get_mobivisor_api_config()
    response = await make_mobivisor_request(
        "DELETE", f"devices/{device_id}", config=config
    )
    handle_mobivisor_response(response, f"delete device {device_id}")

    return {"message": "Device deleted successfully", "device_id": device_id}


@router.get("/devices/{device_id}/installed-packages", tags=["Mobivisor Devices"])
async def fetch_device_installed_packages(device_id: str) -> Any:
    """Fetch installed packages for a specific device from Mobivisor API.

    Args:
        device_id: The unique identifier of the device

    Returns:
        Dict[str, Any]: JSON response from Mobivisor API with installed packages

    Raises:
        HTTPException: If configuration missing, device not found, or request fails

    Example:
        ```python
        GET /api/v1/mobivisor/devices/123/installed-packages
        ```

        Response:
        ```json
        [
            {
                "installTime": "2023-08-03T16:01:14.664Z",
                "versionName": "1.285.822202599",
                "versionCode": "601746",
                "isSystemApp": false,
                "name": "Google One",
                "package": "com.google.android.apps.subscriptions.red",
                "_id": "6903d2b05aec0b9fd9e18ad0"
            }
        ]
        ```
    """
    logger.info(f"Fetching installed-packages from Mobivisor API: {device_id}")
    config = get_mobivisor_api_config()
    response = await make_mobivisor_request(
        "GET",
        f"devices/{device_id}/" "allInstalledPackages",
        config=config,
    )
    return handle_mobivisor_response(response, f"fetch device {device_id}")


@router.delete(
    "/devices/{device_id}/delete-installed-package/{package_id}",
    tags=["Mobivisor Devices"],
)
async def delete_device_installed_packages(device_id: str, package_id: str) -> Any:
    """Delete installed packages from specific devices from Mobivisor API.

    Args:
        device_id: The unique identifier of the device
        package_id: The unique identifier of the package to delete

    Returns:
        Dict[str, Any]: Success message with other installed packages

    Raises:
        HTTPException: If configuration missing, device not found, or request fails

    Example:
        ```python
        DELETE /api/v1/mobivisor/devices/123/delete-installed-package/com.example.app
        ```

        Response:
        ```json
        {
            "message": "Installed package deleted successfully",
            "device_id": "123",
            "package_id": "com.example.app"
        }
        ```

    """
    logger.info(f"Delete device installed packages from Mobivisor API: {device_id}")
    config = get_mobivisor_api_config()
    response = await make_mobivisor_request(
        "DELETE", f"devices/{device_id}/enterpriseApp/{package_id}", config=config
    )
    return handle_mobivisor_response(
        response, f"delete installed package {device_id} {package_id}"
    )


@router.get("/devices/{device_id}/get-managed-apps", tags=["Mobivisor Devices"])
async def fetch_managed_apps_from_device(device_id: str) -> Any:
    """Fetch list of managed apps for a specific devices from Mobivisor API.

    Args:
        device_id: The unique identifier of the devices

    Returns:
        List: JSON response from Mobivisor API with device apps

    Raises:
        HTTPException: If configuration missing, device not found, or request fails
    Example:
        ```python
        GET /api/v1/mobivisor/devices/123/get-managed-apps
        ```

        Response:
        ```json
        [
            {
                "appName": "App 1",
                "packageName": "com.example.app1",
                "version": "1.0.0"
            },
            {
                "appName": "App 2",
                "packageName": "com.example.app2",
                "version": "2.3.4"
            }
        ]
        ```
    """
    logger.info(f"Fetching device details from Mobivisor API: {device_id}")
    config = get_mobivisor_api_config()
    response = await make_mobivisor_request(
        "GET", f"devices/{device_id}/" "managedApps", config=config
    )
    return handle_mobivisor_response(response, f"fetch device {device_id}")


@router.get("/devicescommands", tags=["Mobivisor Devices"])
async def fetch_device_commands(
    order: str = "timeCreated",
    page: int = 0,
    per_page: int = 20,
    reverse: bool = True,
    search: str = "{}",
) -> Any:
    """Fetch device commands from Mobivisor with pagination and search.

    The endpoint proxies requests to the Mobivisor `/devicescommands` API and
    accepts common query parameters: `order`, `page`, `per_page`, `reverse`,
    and `search` (JSON string).
    """
    logger.info("Fetching device commands from Mobivisor API")
    config = get_mobivisor_api_config()
    if not config.get("mobivisor_api_url"):
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Configuration Error",
                "message": "Missing Mobivisor API URL.",
            },
        )

    # Format params for upstream request
    params = {
        "order": order,
        "page": page,
        "per_page": per_page,
        "reverse": str(reverse).lower(),
        "search": search,
    }

    response = await make_mobivisor_request(
        "GET", "devicescommands", params=params, config=config
    )
    return handle_mobivisor_response(response, "fetch device commands")


@router.get("/devices/{device_id}/applications", tags=["Mobivisor Devices"])
async def fetch_device_applications(device_id: str) -> Any:
    """Fetch the applications installed or available for a device in Mobivisor.

    This endpoint proxies the request to the Mobivisor API's
    `/devices/{device_id}/applications` endpoint and returns the applications
    associated with the specified device.

    Args:
        device_id: The unique identifier of the device

    Returns:
        Any: JSON response from Mobivisor API containing application data

    Raises:
        HTTPException: If configuration is missing, device not found, or the
        upstream request fails (mapped to appropriate HTTP status codes)

    Example:
        ```python
        GET /api/v1/mobivisor/devices/123/applications
        ```

        Response (200 OK):
        ```json
        [
            {
                "appName": "Example App",
                "packageName": "com.example.app",
                "version": "1.0.0",
                "managed": true
            }
        ]
        ```
    """
    logger.info(f"Fetching device applications from Mobivisor API: {device_id}")
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
        "GET", f"devices/{device_id}/applications", config=config
    )
    return handle_mobivisor_response(response, f"fetch device applications {device_id}")


@router.put("/devices/{device_id}/actions", tags=["Mobivisor Devices"])
async def trigger_device_action(
    device_id: str, payload: DeviceCommandPayload
) -> Dict[str, Any]:
    """Trigger a Mobivisor command for a specific device.

    This endpoint proxies a PUT request to `/devices/{device_id}/actions` and
    supports the following `commandType` values: `change_password_now`,
    `update_settings`, `refresh_kiosk`, `pref_update`, `location_request`,
    `status_request`, `password_token_request`, and `fetch_system_apps`.
    Validation ensures required fields exist in `commandData` before the
    request is forwarded to Mobivisor.

    Args:
        device_id: The device path parameter targeted by the command.
        payload: Validated request body forwarded to Mobivisor.

    Returns:
        Dict[str, Any]: Mobivisor response describing the command status.

    Raises:
        HTTPException: On configuration issues, validation errors, or errors
        returned from Mobivisor (translated by `handle_mobivisor_response`).
    """
    if payload.deviceId != device_id:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Validation Error",
                "message": "deviceId in payload must match the path parameter",
            },
        )

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

    logger.info(
        "Triggering '%s' command for device %s via Mobivisor API",
        payload.commandType,
        device_id,
    )

    response = await make_mobivisor_request(
        "PUT",
        f"devices/{device_id}/actions",
        json=payload.model_dump(),
        config=config,
    )
    return handle_mobivisor_response(
        response, f"trigger {payload.commandType} for device {device_id}"
    )
