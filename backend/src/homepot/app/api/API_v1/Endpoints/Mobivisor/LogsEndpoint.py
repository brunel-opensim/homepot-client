"""Mobivisor Logs endpoint.

Proxies the Mobivisor debug logs endpoint (`/debuglogs`) so internal
clients can request diagnostic log dumps for troubleshooting.
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

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/debuglogs", tags=["Mobivisor Logs"])
async def fetch_mobivisor_debug_logs() -> Any:
    """Proxy GET /debuglogs from Mobivisor.

    This endpoint forwards a GET to the Mobivisor `/debuglogs` endpoint and
    returns the proxied response. It is intended for support/debugging use
    (requires an appropriately permissioned Mobivisor token).
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

    if not config.get("mobivisor_api_token"):
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Configuration Error",
                "message": "Mobivisor API token is not configured",
            },
        )

    logger.info("Fetching debug logs from Mobivisor API")

    response = await make_mobivisor_request("GET", "debuglogs", config=config)
    return handle_mobivisor_response(response, "fetch debug logs")
