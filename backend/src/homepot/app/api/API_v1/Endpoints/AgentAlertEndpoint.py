"""API endpoint for device alert reporting and retrieval.

Devices (or emulators mimicking them) push alert events here so the Dashboard's
"Alerts" tab can display real-time device issues. Devices can also read back
their own alerts (via ``X-Device-ID`` + ``X-API-Key``) so the User App can show
them, gated behind the Monitor tier (read-only diagnostics).
"""

import logging
from typing import Any, Dict, List, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select

from homepot.app.api.API_v1.Endpoints.agent_permission_gate import require_monitor
from homepot.app.auth_utils import get_current_device
from homepot.app.models.AnalyticsModel import Alert
from homepot.app.schemas.agent import AgentAlertRequest
from homepot.database import get_database_service
from homepot.models import Device

logger = logging.getLogger(__name__)
router = APIRouter()

DEFAULT_ALERT_LIMIT = 50


def _iso(value: Any) -> Any:
    """Format a datetime as ISO, returning None for missing values."""
    return value.isoformat() if value is not None else None


@router.post("/alert", tags=["Agent"])
async def report_alert(
    payload: AgentAlertRequest,
    current_device: Device = Depends(get_current_device),
) -> Dict[str, Any]:
    """Store a single device alert for Dashboard display."""
    logger.info("Alert report received for device_id=%s", payload.device_id)
    if current_device.device_id != payload.device_id:
        raise HTTPException(
            status_code=403,
            detail="Authenticated device does not match payload device_id",
        )
    try:
        db_service = await get_database_service()
        await db_service.create_alert(
            device_id=cast(str, current_device.device_id),
            site_id=cast(Any, current_device.site_id),
            title=payload.title,
            description=payload.description,
            severity=payload.severity,
            category=payload.category,
            timestamp=payload.timestamp,
        )
        return {"status": "success", "message": "Alert stored"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to store device alert: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _envelope(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"status": "success", "message": "Device alerts fetched", "data": data}


@router.get("/{device_id}/alerts", tags=["Agent"])
async def get_device_alerts(
    device_id: str,
    limit: int = DEFAULT_ALERT_LIMIT,
    current_device: Device = Depends(get_current_device),
) -> Dict[str, Any]:
    """Return the latest alerts for the authenticated device.

    Requires the device owner to have granted the Monitor tier (read-only
    diagnostics). The device can only read its own alerts.
    """
    if current_device.device_id != device_id:
        raise HTTPException(
            status_code=403,
            detail="Authenticated device can only read its own alerts",
        )
    require_monitor(current_device)

    capped_limit = max(1, min(int(limit), 200))
    try:
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            result = await session.execute(
                select(Alert)
                .where(Alert.device_id == device_id)
                .order_by(
                    desc(Alert.status == "active"),
                    desc(Alert.timestamp),
                )
                .limit(capped_limit)
            )
            alerts = result.scalars().all()

        return _envelope(
            [
                {
                    "id": alert.id,
                    "title": alert.title,
                    "description": alert.description,
                    "severity": alert.severity,
                    "category": alert.category,
                    "status": alert.status,
                    "timestamp": _iso(alert.timestamp),
                    "resolved_at": _iso(alert.resolved_at),
                    "resolved_by": alert.resolved_by,
                }
                for alert in alerts
            ]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch alerts for %s: %s", device_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch device alerts")
