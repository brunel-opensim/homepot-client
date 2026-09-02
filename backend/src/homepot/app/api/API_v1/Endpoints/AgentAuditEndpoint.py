"""API endpoint for device audit event reporting.

Devices (or emulators mimicking them) push audit events here so the Dashboard's
"Audit Trail" tab can display real-time device activity.
"""

import logging
from typing import Any, Dict, List, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select

from homepot.app.api.API_v1.Endpoints.agent_permission_gate import require_monitor
from homepot.app.auth_utils import get_current_device
from homepot.app.schemas.agent import AgentAuditRequest
from homepot.database import get_database_service
from homepot.models import AuditLog, Device

logger = logging.getLogger(__name__)
router = APIRouter()

DEFAULT_AUDIT_LIMIT = 50


def _iso(value: Any) -> Any:
    """Format a datetime as ISO, returning None for missing values."""
    return value.isoformat() if value is not None else None


@router.post("/audit", tags=["Agent"])
async def report_audit_event(
    payload: AgentAuditRequest,
    current_device: Device = Depends(get_current_device),
) -> Dict[str, Any]:
    """Store a single device audit event for Dashboard display."""
    logger.info("Audit event report received for device_id=%s", payload.device_id)
    if current_device.device_id != payload.device_id:
        raise HTTPException(
            status_code=403,
            detail="Authenticated device does not match payload device_id",
        )
    try:
        db_service = await get_database_service()
        await db_service.create_audit_log(
            event_type=payload.event_type,
            description=payload.description,
            device_id=cast(Any, current_device.id),
            site_id=cast(Any, current_device.site_id),
            event_metadata=payload.metadata,
        )
        return {"status": "success", "message": "Audit event stored"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to store device audit event: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _envelope(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"status": "success", "message": "Device audit events fetched", "data": data}


@router.get("/{device_id}/audit", tags=["Agent"])
async def get_device_audit_events(
    device_id: str,
    limit: int = DEFAULT_AUDIT_LIMIT,
    current_device: Device = Depends(get_current_device),
) -> Dict[str, Any]:
    """Return the latest audit events for the authenticated device.

    Requires the device owner to have granted the Monitor tier. The device
    authenticates via ``X-Device-ID`` and ``X-API-Key`` headers and can only
    read its own audit trail.
    """
    if current_device.device_id != device_id:
        raise HTTPException(
            status_code=403,
            detail="Authenticated device can only read its own audit events",
        )
    require_monitor(current_device)
    try:
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            result = await session.execute(
                select(AuditLog)
                .where(AuditLog.device_id == int(current_device.id))
                .order_by(desc(AuditLog.created_at))
                .limit(int(limit))
            )
            events = result.scalars().all()

        return _envelope(
            [
                {
                    "id": event.id,
                    "event_type": event.event_type,
                    "description": event.description,
                    "event_metadata": event.event_metadata,
                    "created_at": _iso(event.created_at),
                }
                for event in events
            ]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to fetch audit events for %s: %s", device_id, e, exc_info=True
        )
        raise HTTPException(
            status_code=500, detail="Failed to fetch device audit events"
        )
