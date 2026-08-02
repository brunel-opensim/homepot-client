"""API endpoint for device log reporting.

Devices (or emulators mimicking them) push log lines here so the Dashboard's
"Live Logs" tab can display real-time device activity.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from homepot.app.auth_utils import get_current_device
from homepot.app.schemas.agent import AgentLogRequest
from homepot.error_logger import log_error
from homepot.models import Device

logger = logging.getLogger(__name__)
router = APIRouter()

_SEVERITY_ALIASES = {
    "info": "info",
    "warning": "warning",
    "warn": "warning",
    "error": "error",
    "critical": "critical",
}


@router.post("/logs", tags=["Agent"])
async def report_log(
    payload: AgentLogRequest,
    current_device: Device = Depends(get_current_device),
) -> Dict[str, Any]:
    """Store a single device log line for Dashboard display."""
    logger.info("Log report received for device_id=%s", payload.device_id)
    if current_device.device_id != payload.device_id:
        raise HTTPException(
            status_code=403,
            detail="Authenticated device does not match payload device_id",
        )
    try:
        severity = _SEVERITY_ALIASES.get(payload.level.lower(), "info")
        await log_error(
            category=payload.category or "device",
            severity=severity,
            error_message=payload.message,
            error_code=None,
            endpoint="/agent/logs",
            device_id=payload.device_id,
            context=payload.context,
        )
        return {"status": "success", "message": "Log stored"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to store device log: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
