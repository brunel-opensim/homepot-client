"""API endpoints for managing agents in the HomePot system."""

import logging
from typing import Any, Dict, Optional
from fastapi import (
    HTTPException,
    Request,
)
import httpx
from fastapi import APIRouter, HTTPException
from homepot_client.config import get_mobivisor_api_config
from homepot_client.client import HomepotClient

client_instance: Optional[HomepotClient] = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


router = APIRouter()


# External Devices API (Mobivisor)
@router.get("/devices", tags=["Devices"])
async def fetch_external_devices(request: Request) -> Any:
    print("Hello")
    """Fetch device data from Mobivisor endpoint.

    - Reads Bearer token from Authorization header or optional token query param
    - Proxies GET request to https://mydd.mobivisor.com/devices
    - Returns upstream JSON or maps errors appropriately
    """
    mobivisorConfig = get_mobivisor_api_config()
    base_url = mobivisorConfig.get("mobivisor_api_url") or ""
    upstream_url = base_url + "devices"
    # "https://mydd.mobivisor.com/devices"

    # Resolve bearer token
    auth_header = mobivisorConfig["mobivisor_api_token"]
    # bearer_token = None
    if not auth_header:
        raise HTTPException(
            status_code=401,
            detail="Missing Bearer token.Provide Authorization header.",
        )

    if upstream_url is None:
        raise HTTPException(
            status_code=401,
            detail="Missing Mobivisor URL",
        )

    headers = {"Authorization": f"Bearer {auth_header}"}

    timeout = httpx.Timeout(10.0, connect=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(upstream_url, headers=headers)

        if resp.status_code == 200:
            # Return upstream JSON transparently
            return resp.json()
        elif resp.status_code in (401, 403):
            raise HTTPException(
                status_code=resp.status_code,
                detail="Unauthorized to access upstream devices endpoint",
            )
        elif resp.status_code == 404:
            raise HTTPException(
                status_code=404, detail="Upstream devices resource not found"
            )
        else:
            # Try to forward upstream error details if JSON, else generic
            try:
                upstream_error = resp.json()
            except Exception:
                upstream_error = {"detail": resp.text}
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "Upstream service error",
                    "status_code": resp.status_code,
                    "error": upstream_error,
                },
            )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504, detail="Upstream devices endpoint timed out"
        )
    except httpx.RequestError as e:
        logger.error(f"Network error contacting upstream: {e}")
        raise HTTPException(
            status_code=502, detail="Failed to contact upstream devices service"
        )


@router.get("/devices/{device_id}", tags=["Devices"])
async def fetch_devices_details(device_id: str) -> Dict[str, Any]:
    """Fetch device data by device id from Mobivisor endpoint."""
    mobivisorConfig = get_mobivisor_api_config()
    base_url = mobivisorConfig.get("mobivisor_api_url")

    if not base_url:
        raise HTTPException(status_code=500, detail="Mobivisor base URL is missing")

    upstream_url = f"{base_url}devices/{device_id}"

    # Resolve bearer token
    auth_header = mobivisorConfig.get("mobivisor_api_token")
    if not auth_header:
        raise HTTPException(
            status_code=401,
            detail="Missing Bearer token. Provide Authorization header.",
        )

    headers = {"Authorization": f"Bearer {auth_header}"}

    timeout = httpx.Timeout(10.0, connect=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(upstream_url, headers=headers)

        if resp.status_code == 200:
            data: Dict[str, Any] = resp.json()
            return data
        elif resp.status_code in (401, 403):
            raise HTTPException(
                status_code=resp.status_code,
                detail="Unauthorized to access upstream devices endpoint",
            )
        elif resp.status_code == 404:
            raise HTTPException(
                status_code=404, detail="Upstream devices resource not found"
            )
        else:
            try:
                upstream_error = resp.json()
            except Exception:
                upstream_error = {"detail": resp.text}
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "Upstream service error",
                    "status_code": resp.status_code,
                    "error": upstream_error,
                },
            )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504, detail="Upstream devices endpoint timed out"
        )
    except httpx.RequestError as e:
        logger.error(f"Network error contacting upstream: {e}")
        raise HTTPException(
            status_code=502, detail="Failed to contact upstream devices service"
        )
