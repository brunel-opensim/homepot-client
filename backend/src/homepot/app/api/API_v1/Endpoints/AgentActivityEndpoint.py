"""API endpoints for device activity retrieval.

Devices (or emulators mimicking them) read back their own activity streams —
logs, audit trail, jobs, alerts and push history — so the User App can display
real-time device activity. Each endpoint authenticates the device via
``X-Device-ID`` + ``X-API-Key`` headers and only returns that device's data.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import String as SA_String
from sqlalchemy import cast as sa_cast
from sqlalchemy import desc, select

from homepot.app.auth_utils import get_current_device
from homepot.app.models.AnalyticsModel import Alert, ConfigurationHistory, ErrorLog
from homepot.database import get_database_service
from homepot.models import AuditLog, Device, Job

logger = logging.getLogger(__name__)
router = APIRouter()

DEFAULT_LIMIT = 50


def _envelope(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"status": "success", "message": "Device activity fetched", "data": data}


async def _require_own_device(device_id: str, current_device: Device) -> None:
    """Raise 403 when the authenticated device tries to read another device."""
    if current_device.device_id != device_id:
        raise HTTPException(
            status_code=403,
            detail="Authenticated device can only read its own activity",
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


@router.get("/{device_id}/audit", tags=["Agent"])
async def get_device_audit(
    device_id: str,
    limit: int = DEFAULT_LIMIT,
    current_device: Device = Depends(get_current_device),
) -> Dict[str, Any]:
    """Return the latest device audit events (Audit Trail)."""
    try:
        await _require_own_device(device_id, current_device)
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            result = await session.execute(
                select(AuditLog)
                .where(AuditLog.device_id == current_device.id)
                .order_by(desc(AuditLog.created_at))
                .limit(limit)
            )
            logs = result.scalars().all()

        return _envelope(
            [
                {
                    "id": log.id,
                    "event_type": log.event_type,
                    "description": log.description,
                    "created_at": _iso(log.created_at),
                    "ip_address": log.ip_address,
                    "metadata": log.event_metadata,
                }
                for log in logs
            ]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch audit for %s: %s", device_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch device audit")


@router.get("/{device_id}/jobs", tags=["Agent"])
async def get_device_jobs(
    device_id: str,
    limit: int = DEFAULT_LIMIT,
    current_device: Device = Depends(get_current_device),
) -> Dict[str, Any]:
    """Return the latest device jobs (Job History)."""
    try:
        await _require_own_device(device_id, current_device)
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            result = await session.execute(
                select(Job)
                .where(Job.device_id == current_device.id)
                .order_by(desc(Job.created_at))
                .limit(limit)
            )
            jobs = result.scalars().all()

        return _envelope(
            [
                {
                    "job_id": j.job_id,
                    "action": j.action,
                    "description": j.description,
                    "status": j.status,
                    "priority": j.priority,
                    "created_at": _iso(j.created_at),
                    "completed_at": _iso(j.completed_at),
                    "result": j.result,
                    "error_message": j.error_message,
                }
                for j in jobs
            ]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch jobs for %s: %s", device_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch device jobs")


@router.get("/{device_id}/alerts", tags=["Agent"])
async def get_device_alerts(
    device_id: str,
    limit: int = DEFAULT_LIMIT,
    current_device: Device = Depends(get_current_device),
) -> Dict[str, Any]:
    """Return the latest device alerts."""
    try:
        await _require_own_device(device_id, current_device)
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            result = await session.execute(
                select(Alert)
                .where(Alert.device_id == device_id)
                .order_by(desc(Alert.timestamp))
                .limit(limit)
            )
            alerts = result.scalars().all()

        return _envelope(
            [
                {
                    "id": a.id,
                    "title": a.title,
                    "description": a.description,
                    "severity": a.severity,
                    "category": a.category,
                    "status": a.status,
                    "timestamp": _iso(a.timestamp),
                    "ai_recommendation": a.ai_recommendation,
                    "ai_confidence": a.ai_confidence,
                }
                for a in alerts
            ]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch alerts for %s: %s", device_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch device alerts")


@router.get("/{device_id}/push-history", tags=["Agent"])
async def get_device_push_history(
    device_id: str,
    limit: int = DEFAULT_LIMIT,
    current_device: Device = Depends(get_current_device),
) -> Dict[str, Any]:
    """Return the latest device push-command history entries."""
    try:
        await _require_own_device(device_id, current_device)
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            result = await session.execute(
                select(ConfigurationHistory)
                .where(
                    ConfigurationHistory.entity_type == "device",
                    ConfigurationHistory.entity_id == device_id,
                )
                .order_by(desc(ConfigurationHistory.timestamp))
                .limit(limit)
            )
            entries = result.scalars().all()

        return _envelope(
            [
                {
                    "id": e.id,
                    "timestamp": _iso(e.timestamp),
                    "parameter_name": e.parameter_name,
                    "old_value": e.old_value,
                    "new_value": e.new_value,
                    "change_reason": e.change_reason,
                    "changed_by": e.changed_by,
                    "was_successful": e.was_successful,
                }
                for e in entries
            ]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to fetch push history for %s: %s", device_id, e, exc_info=True
        )
        raise HTTPException(
            status_code=500, detail="Failed to fetch device push history"
        )
