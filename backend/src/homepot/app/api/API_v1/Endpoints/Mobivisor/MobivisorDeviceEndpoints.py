"""API endpoints for managing Mobivisor Device Data in the HomePot system.

This module provides proxy endpoints to interact with the external Mobivisor
device management service. All requests are forwarded to the Mobivisor API
with proper authentication and error handling.
"""

import logging
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from homepot.app.models.mobivisor_models import (
    FeatureControlItem,
    FeatureControlsPayload,
)
from homepot.app.utils.mobivisor_request import (
    _handle_mobivisor_response as handle_mobivisor_response,
)
from homepot.app.utils.mobivisor_request import (
    _make_mobivisor_request as make_mobivisor_request,
)
from homepot.config import get_mobivisor_api_config

# Configure logging
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


@router.delete("/devices/{device_id}/logins", tags=["Mobivisor Devices"])
async def delete_device_logins(device_id: str) -> Dict[str, Any]:
    """Delete all login records for a device in Mobivisor.

    This endpoint proxies a DELETE request to Mobivisor's
    `/devices/{device_id}/logins` endpoint.

    Args:
        device_id: The unique identifier of the device (required).

    Returns:
        Dict[str, Any]: Proxied JSON response from Mobivisor.
        When Mobivisor returns `204 No Content`, this endpoint returns an empty
        JSON object `{}`.

    Raises:
        HTTPException: For configuration issues, validation errors, or mapped
        upstream failures (401/403/404/5xx).

    Example:
        ```python
        DELETE /api/v1/mobivisor/devices/123/logins
        ```

        Response:
        ```json
        {}
        ```
    """
    if not device_id or not device_id.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Validation Error",
                "message": "device_id is required",
            },
        )

    logger.info("Deleting device logins via Mobivisor API: %s", device_id)
    config = get_mobivisor_api_config()
    response = await make_mobivisor_request(
        "DELETE", f"devices/{device_id}/logins", config=config
    )
    return handle_mobivisor_response(response, f"delete device logins {device_id}")


@router.get("/devices/{device_id}/mdmProfileUrl", tags=["Mobivisor Devices"])
async def fetch_device_mdm_profile_url(device_id: str) -> Dict[str, Any]:
    """Fetch the MDM profile URL for a device from Mobivisor.

    This endpoint proxies a GET request to Mobivisor's
    `/devices/{device_id}/mdmProfileUrl` endpoint.

    Args:
        device_id: The unique identifier of the device (required).

    Returns:
        Dict[str, Any]: Proxied JSON response from Mobivisor containing the
        MDM profile URL.

    Raises:
        HTTPException: For configuration issues, validation errors, or mapped
        upstream failures (401/403/404/5xx).

    Example:
        ```python
        GET /api/v1/mobivisor/devices/123/mdmProfileUrl
        ```

        Response:
        ```json
        {"mdmProfileUrl": "https://example.com/profile.mobileconfig"}
        ```
    """
    if not device_id or not device_id.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Validation Error",
                "message": "device_id is required",
            },
        )

    logger.info("Fetching MDM profile URL via Mobivisor API: %s", device_id)
    config = get_mobivisor_api_config()
    response = await make_mobivisor_request(
        "GET", f"devices/{device_id}/mdmProfileUrl", config=config
    )

    # Mobivisor may return a plain string (URL) for this endpoint instead of a
    # JSON object. Normalize successful responses into a JSON object.
    if 200 <= response.status_code < 300:
        try:
            parsed = response.json() if response.content else None
        except Exception:
            parsed = None

        if isinstance(parsed, dict):
            return parsed

        if isinstance(parsed, str) and parsed.strip():
            return {"mdmProfileUrl": parsed.strip()}

        text = (response.text or "").strip()
        if text.startswith('"') and text.endswith('"') and len(text) >= 2:
            text = text[1:-1]
        return {"mdmProfileUrl": text}

    return handle_mobivisor_response(
        response, f"fetch mdmProfileUrl for device {device_id}"
    )


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


@router.get("/devices/{device_id}/policies", tags=["Mobivisor Devices"])
async def fetch_device_policies(device_id: str) -> Any:
    """Fetch policies applied to a specific device from Mobivisor API.

    This endpoint proxies to the Mobivisor `/devices/{device_id}/policies`
    endpoint and returns the policy objects associated with the provided
    device id.

    Args:
        device_id: The unique identifier of the device

    Returns:
        Any: JSON response from Mobivisor API with device policies

    Raises:
        HTTPException: If configuration is missing, device not found, or the
        upstream request fails (mapped to appropriate HTTP status codes)

    Example:
        ```python
        GET /api/v1/mobivisor/devices/123/policies
        ```

        Response (200 OK):
        ```json
        {
            "policies": [
                {"id": "p1", "name": "KioskPolicy", "enabled": true}
            ]
        }
        ```
    """
    logger.info(f"Fetching device policies from Mobivisor API: {device_id}")
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
        "GET", f"devices/{device_id}/policies", config=config
    )
    return handle_mobivisor_response(response, f"fetch device policies {device_id}")


@router.get(
    "/devices/fetchSystemApps/model/{model_number}/version/{version_number}",
    tags=["Mobivisor Devices"],
)
async def fetch_system_apps_by_model_version(
    model_number: str, version_number: str
) -> Any:
    """Fetch system apps for a specific device model and version from Mobivisor.

    This endpoint proxies to Mobivisor's
    `/devices/fetchSystemApps/model/{model_number}/version/{version_number}`
    endpoint and returns the list of system apps for the given model/version.

    Args:
        model_number: The device model identifier (required)
        version_number: The device version identifier (required)

    Returns:
        Any: JSON response from Mobivisor API with system apps

    Raises:
        HTTPException: If configuration is missing, resource not found, or the
        upstream request fails (mapped to appropriate HTTP status codes)

    Example:
        ```python
        GET /api/v1/mobivisor/devices/fetchSystemApps/model/SM-G998/version/1.2.3
        ```

        Response (200 OK):
        ```json
        {
            "systemApps": [
                {"package": "com.example.app", "name": "Example App", "version": "1.0"}
            ]
        }
        ```
    """
    logger.info(
        "Fetching system apps from Mobivisor for model=%s version=%s",
        model_number,
        version_number,
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

    response = await make_mobivisor_request(
        "GET",
        f"devices/fetchSystemApps/model/{model_number}/version/{version_number}",
        config=config,
    )
    return handle_mobivisor_response(
        response, f"fetch system apps for model {model_number} version {version_number}"
    )


@router.put("/devices/{device_id}/featureControls", tags=["Mobivisor Devices"])
async def update_device_feature_controls(device_id: str, payload: list[dict]) -> Any:
    """Update feature controls for a specific device in Mobivisor.

    This endpoint accepts a JSON array of feature control objects and proxies
    the PUT request to Mobivisor's `/devices/{device_id}/featureControls`
    endpoint. Each item must contain a `feature` key and at least one of
    `booleanValue` or `numberValue`.

    Args:
        device_id: The unique identifier of the device
        payload: JSON array of feature control objects

    Returns:
        Any: JSON response from Mobivisor API

    Raises:
        HTTPException: For configuration issues, validation errors, or mapped
        upstream errors.

    Example:
        ```bash
        PUT /api/v1/mobivisor/devices/6895b35f73796d4ff80a57a0/featureControls
        [
          {"feature": "camera", "booleanValue": true},
          {"feature": "screen_brightness", "numberValue": 100}
        ]
        ```
    """
    # Validate payload shape (expecting a non-empty array) before checking config
    try:
        wrapper = FeatureControlsPayload(
            items=[FeatureControlItem(**it) for it in payload]
        )
    except Exception as e:
        raise HTTPException(
            status_code=422, detail={"error": "Validation Error", "message": str(e)}
        )

    if not wrapper.is_non_empty:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Validation Error",
                "message": "At least one feature control is required",
            },
        )

    # Ensure each item has at least one value
    for item in wrapper.items:
        if not item.has_value:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "Validation Error",
                    "message": (
                        f"Feature '{item.feature}' must include booleanValue or "
                        "numberValue"
                    ),
                },
            )

    # Validate config after payload validation so clients receive validation
    # errors even when the upstream configuration is missing.
    config = get_mobivisor_api_config()
    if not config.get("mobivisor_api_url"):
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Configuration Error",
                "message": "Missing Mobivisor API URL.",
            },
        )

    if not config.get("mobivisor_api_token"):
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Configuration Error",
                "message": "Mobivisor API token is not configured",
            },
        )

    response = await make_mobivisor_request(
        "PUT",
        f"devices/{device_id}/featureControls",
        json=payload,
        config=config,
    )
    return handle_mobivisor_response(
        response, f"update feature controls for device {device_id}"
    )


@router.put("/devices/{device_id}/description", tags=["Mobivisor Devices"])
async def update_device_description(device_id: str, payload: dict) -> Any:
    """Update the device description in Mobivisor.

    This endpoint accepts a JSON object with a single `description` field and
    proxies a PUT request to Mobivisor's
    `/devices/{device_id}/description` endpoint.

    Validation:
        - `description` must be present and be a non-empty string.

    Args:
        device_id: The unique identifier of the device.
        payload: JSON body containing `description` key.

    Returns:
        Any: JSON response from the proxied Mobivisor API.

    Raises:
        HTTPException: For validation, configuration, or upstream errors.

    Example:
        ```bash
        PUT /api/v1/mobivisor/devices/6895b35f73796d4ff80a57a0/description
        {"description": "Test"}
        ```
    """
    # Basic payload validation before contacting upstream
    if not isinstance(payload, dict) or "description" not in payload:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Validation Error",
                "message": "Missing 'description' field",
            },
        )

    desc = payload.get("description")
    if not isinstance(desc, str) or not desc.strip():
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Validation Error",
                "message": "'description' must be a non-empty string",
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

    if not config.get("mobivisor_api_token"):
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Configuration Error",
                "message": "Mobivisor API token is not configured",
            },
        )

    logger.info("Updating description for device %s via Mobivisor", device_id)
    response = await make_mobivisor_request(
        "PUT", f"devices/{device_id}/description", json=payload, config=config
    )
    return handle_mobivisor_response(
        response, f"update description for device {device_id}"
    )


@router.put("/devices/{device_id}/imei", tags=["Mobivisor Devices"])
async def update_device_imei(device_id: str, payload: dict) -> Any:
    """Update the device IMEI in Mobivisor.

    Proxies a PUT to Mobivisor's `/devices/{device_id}/imei` endpoint. The
    request body must be a JSON object with an `imei` field containing a
    non-empty string.

    Args:
        device_id: The unique identifier of the device.
        payload: JSON body containing `imei` key.

    Returns:
        Any: JSON response from the proxied Mobivisor API.

    Raises:
        HTTPException: For validation, configuration, or upstream errors.
    """
    # Basic payload validation before contacting upstream
    if not isinstance(payload, dict) or "imei" not in payload:
        raise HTTPException(
            status_code=422,
            detail={"error": "Validation Error", "message": "Missing 'imei' field"},
        )

    imei_val = payload.get("imei")
    if not isinstance(imei_val, str) or not imei_val.strip():
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Validation Error",
                "message": "'imei' must be a non-empty string",
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

    if not config.get("mobivisor_api_token"):
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Configuration Error",
                "message": "Mobivisor API token is not configured",
            },
        )

    logger.info("Updating IMEI for device %s via Mobivisor", device_id)
    response = await make_mobivisor_request(
        "PUT", f"devices/{device_id}/imei", json=payload, config=config
    )
    return handle_mobivisor_response(response, f"update imei for device {device_id}")


@router.put("/devices/{device_id}/extraVariables", tags=["Mobivisor Devices"])
async def update_device_extra_variables(device_id: str, payload: dict) -> Any:
    """Update device extra variables in Mobivisor.

    Proxies a PUT to Mobivisor's `/devices/{device_id}/extraVariables` endpoint.

    Validation:
        - `extraVariables` must be present and be an object/dictionary with at
          least one key/value pair.

    Args:
        device_id: The unique identifier of the device (path parameter).
        payload: JSON body containing `extraVariables` key.

    Returns:
        Any: JSON response from the proxied Mobivisor API.

    Raises:
        HTTPException: For validation, configuration, or upstream errors.
    """
    # Basic payload validation before contacting upstream
    if not isinstance(payload, dict) or "extraVariables" not in payload:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Validation Error",
                "message": "Missing 'extraVariables' field",
            },
        )

    vars_val = payload.get("extraVariables")
    if not isinstance(vars_val, dict):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Validation Error",
                "message": "'extraVariables' must be an object/dictionary",
            },
        )

    if len(vars_val) == 0:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Validation Error",
                "message": "At least one extra variable is required",
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

    if not config.get("mobivisor_api_token"):
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Configuration Error",
                "message": "Mobivisor API token is not configured",
            },
        )

    logger.info("Updating extra variables for device %s via Mobivisor", device_id)
    response = await make_mobivisor_request(
        "PUT", f"devices/{device_id}/extraVariables", json=payload, config=config
    )
    return handle_mobivisor_response(
        response, f"update extra variables for device {device_id}"
    )


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
