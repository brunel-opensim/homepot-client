"""
Utility functions for making requests to the Mobivisor API.

This module provides helper functions to interact with the Mobivisor API,
including request handling, authentication, and error mapping.
"""

import logging
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException

import homepot.config as config_module

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_TIMEOUT_TOTAL = 10.0
DEFAULT_TIMEOUT_CONNECT = 5.0


async def _make_mobivisor_request(
    method: str, endpoint: str, config: Optional[Dict[str, Any]] = None, **kwargs: Any
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
    # Allow callers to provide a pre-fetched config to make unit-testing/mocking
    # easier and avoid calling the global `get_mobivisor_api_config` twice.
    # Prefer an explicitly provided config (useful for tests). If not provided
    # call through the `homepot.config` module so that tests which patch
    # `homepot.config.get_mobivisor_api_config` will be effective.
    mobivisor_config = config or config_module.get_mobivisor_api_config()
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
