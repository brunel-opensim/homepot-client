"""API endpoint for device log reporting and retrieval.

Devices (or emulators mimicking them) push log lines here so the Dashboard's
"Live Logs" tab can display real-time device activity. Devices can also read
back their own log lines (via ``X-Device-ID`` + ``X-API-Key``) so the User App
can show the device's live error/connectivity history.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import String as SA_String
from sqlalchemy import cast as sa_cast
from sqlalchemy import desc, select

from homepot.app.auth_utils import get_current_device
from homepot.app.models.AnalyticsModel import ErrorLog
from homepot.app.schemas.agent import AgentLogRequest
from homepot.database import get_database_service
from homepot.error_logger import log_error
from homepot.models import Device

logger = logging.getLogger(__name__)
router = APIRouter()

DEFAULT_LIMIT = 50

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


def _envelope(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"status": "success", "message": "Device logs fetched", "data": data}


async def _require_own_device(device_id: str, current_device: Device) -> None:
    """Raise 403 when the authenticated device tries to read another device."""
    if current_device.device_id != device_id:
        raise HTTPException(
            status_code=403,
            detail="Authenticated device can only read its own logs",
        )


def _iso(value: Any) -> Any:
    """Format a datetime as ISO, returning None for missing values."""
    return value.isoformat() if value is not None else None


@router.get("/{device_id}/logs", tags=["Agent"])
async def get_device_logs(
    device_id: str,
    limit: int = DEFAULT_LIMIT,
    current_device: Device = Depends(get_current_device),
) -> Dict[str, Any]:
    """Return the latest device log lines (Live Logs)."""
    try:
        await _require_own_device(device_id, current_device)
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            result = await session.execute(
                select(ErrorLog)
                .where(
                    sa_cast(ErrorLog.context["original_device_id"], SA_String)
                    == f'"{device_id}"'
                )
                .order_by(desc(ErrorLog.timestamp))
                .limit(limit)
            )
            logs = result.scalars().all()
            if not logs:
                result = await session.execute(
                    select(ErrorLog)
                    .where(
                        sa_cast(ErrorLog.context["original_device_id"], SA_String)
                        == device_id
                    )
                    .order_by(desc(ErrorLog.timestamp))
                    .limit(limit)
                )
                logs = result.scalars().all()

        return _envelope(
            [
                {
                    "id": log.id,
                    "timestamp": _iso(log.timestamp),
                    "category": log.category,
                    "severity": log.severity,
                    "error_code": log.error_code,
                    "error_message": log.error_message,
                    "resolved": log.resolved,
                }
                for log in logs
            ]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch logs for %s: %s", device_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch device logs")
