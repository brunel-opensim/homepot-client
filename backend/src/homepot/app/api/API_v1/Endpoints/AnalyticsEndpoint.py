"""API endpoints for analytics data collection and querying."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from homepot.app.auth_utils import TokenData, get_current_user
from homepot.app.db.database import get_db
from homepot.app.models import AnalyticsModel as models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Data Collection Endpoints ====================


@router.post("/analytics/user-activity", status_code=status.HTTP_201_CREATED)
async def log_user_activity(
    activity: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> Dict[str, Any]:
    """Log user activity from frontend.

    Expected payload:
    {
        "activity_type": "page_view|click|search|interaction",
        "page_url": "/dashboard",
        "element_id": "button_export",
        "search_query": "device status",
        "metadata": {...},
        "duration_ms": 1500
    }
    """
    try:
        activity_log = models.UserActivity(
            user_id=current_user.email,
            session_id=activity.get("session_id"),
            activity_type=activity.get("activity_type"),
            page_url=activity.get("page_url"),
            element_id=activity.get("element_id"),
            search_query=activity.get("search_query"),
            metadata=activity.get("metadata"),
            duration_ms=activity.get("duration_ms"),
            timestamp=datetime.now(timezone.utc),
        )
        db.add(activity_log)
        db.commit()

        return {"success": True, "message": "Activity logged"}

    except Exception as e:
        logger.error(f"Error logging user activity: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to log activity")


@router.post("/analytics/error", status_code=status.HTTP_201_CREATED)
async def log_error(
    error: Dict[str, Any],
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Log application errors.

    Expected payload:
    {
        "category": "api|database|external_service|validation",
        "severity": "critical|error|warning|info",
        "error_code": "AUTH_001",
        "error_message": "Authentication failed",
        "stack_trace": "...",
        "endpoint": "/api/v1/auth/login",
        "user_id": "user@example.com",
        "device_id": "device-123",
        "context": {...}
    }
    """
    try:
        error_log = models.ErrorLog(
            category=error.get("category", "unknown"),
            severity=error.get("severity", "error"),
            error_code=error.get("error_code"),
            error_message=error.get("error_message", "Unknown error"),
            stack_trace=error.get("stack_trace"),
            endpoint=error.get("endpoint"),
            user_id=error.get("user_id"),
            device_id=error.get("device_id"),
            context=error.get("context"),
            timestamp=datetime.now(timezone.utc),
        )
        db.add(error_log)
        db.commit()

        return {"success": True, "message": "Error logged"}

    except Exception as e:
        logger.error(f"Error logging error: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to log error")


@router.post("/analytics/device-state-change", status_code=status.HTTP_201_CREATED)
async def log_device_state_change(
    state_change: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: Optional[TokenData] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Log device state changes.

    Expected payload:
    {
        "device_id": "device-123",
        "previous_state": "online",
        "new_state": "offline",
        "reason": "Network timeout",
        "metadata": {...}
    }
    """
    try:
        state_log = models.DeviceStateHistory(
            device_id=state_change.get("device_id"),
            previous_state=state_change.get("previous_state"),
            new_state=state_change.get("new_state"),
            changed_by=current_user.email if current_user else "system",
            reason=state_change.get("reason"),
            metadata=state_change.get("metadata"),
            timestamp=datetime.now(timezone.utc),
        )
        db.add(state_log)
        db.commit()

        return {"success": True, "message": "State change logged"}

    except Exception as e:
        logger.error(f"Error logging state change: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to log state change")


@router.post("/analytics/job-outcome", status_code=status.HTTP_201_CREATED)
async def log_job_outcome(
    outcome: Dict[str, Any],
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Log job execution outcomes.

    Expected payload:
    {
        "job_id": "job-456",
        "job_type": "restart|update|health_check",
        "device_id": "device-123",
        "status": "success|failed|timeout|cancelled",
        "duration_ms": 5000,
        "error_code": "TIMEOUT_001",
        "error_message": "Device did not respond",
        "retry_count": 2,
        "initiated_by": "user@example.com",
        "metadata": {...}
    }
    """
    try:
        outcome_log = models.JobOutcome(
            job_id=outcome.get("job_id"),
            job_type=outcome.get("job_type"),
            device_id=outcome.get("device_id"),
            status=outcome.get("status"),
            duration_ms=outcome.get("duration_ms"),
            error_code=outcome.get("error_code"),
            error_message=outcome.get("error_message"),
            retry_count=outcome.get("retry_count", 0),
            initiated_by=outcome.get("initiated_by"),
            metadata=outcome.get("metadata"),
            timestamp=datetime.now(timezone.utc),
        )
        db.add(outcome_log)
        db.commit()

        return {"success": True, "message": "Job outcome logged"}

    except Exception as e:
        logger.error(f"Error logging job outcome: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to log outcome")


# ==================== Analytics Query Endpoints ====================


@router.get("/metrics/api-performance")
async def get_api_performance(
    hours: int = Query(24, ge=1, le=168),
    endpoint: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get API performance metrics."""
    try:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        query = db.query(
            models.APIRequestLog.endpoint,
            func.count(models.APIRequestLog.id).label("request_count"),
            func.avg(models.APIRequestLog.response_time_ms).label("avg_response_time"),
            func.max(models.APIRequestLog.response_time_ms).label("max_response_time"),
            func.min(models.APIRequestLog.response_time_ms).label("min_response_time"),
        ).filter(models.APIRequestLog.timestamp >= cutoff_time)

        if endpoint:
            query = query.filter(models.APIRequestLog.endpoint == endpoint)

        results = query.group_by(models.APIRequestLog.endpoint).all()

        return {
            "success": True,
            "time_range_hours": hours,
            "metrics": [
                {
                    "endpoint": r.endpoint,
                    "request_count": r.request_count,
                    "avg_response_time_ms": round(r.avg_response_time, 2),
                    "max_response_time_ms": r.max_response_time,
                    "min_response_time_ms": r.min_response_time,
                }
                for r in results
            ],
        }
    except Exception as e:
        logger.error(f"Error fetching API performance: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch metrics")


@router.get("/metrics/job-outcomes")
async def get_job_outcomes(
    hours: int = Query(24, ge=1, le=168),
    job_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get job outcome statistics."""
    try:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        query = db.query(
            models.JobOutcome.job_type,
            models.JobOutcome.status,
            func.count(models.JobOutcome.id).label("count"),
            func.avg(models.JobOutcome.duration_ms).label("avg_duration"),
        ).filter(models.JobOutcome.timestamp >= cutoff_time)

        if job_type:
            query = query.filter(models.JobOutcome.job_type == job_type)

        results = query.group_by(
            models.JobOutcome.job_type, models.JobOutcome.status
        ).all()

        return {
            "success": True,
            "time_range_hours": hours,
            "outcomes": [
                {
                    "job_type": r.job_type,
                    "status": r.status,
                    "count": r.count,
                    "avg_duration_ms": (
                        round(r.avg_duration, 2) if r.avg_duration else None
                    ),
                }
                for r in results
            ],
        }
    except Exception as e:
        logger.error(f"Error fetching job outcomes: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch outcomes")


@router.get("/metrics/error-trends")
async def get_error_trends(
    hours: int = Query(24, ge=1, le=168),
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get error trend statistics."""
    try:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        query = db.query(
            models.ErrorLog.category,
            models.ErrorLog.severity,
            func.count(models.ErrorLog.id).label("count"),
        ).filter(models.ErrorLog.timestamp >= cutoff_time)

        if category:
            query = query.filter(models.ErrorLog.category == category)

        results = query.group_by(
            models.ErrorLog.category, models.ErrorLog.severity
        ).all()

        return {
            "success": True,
            "time_range_hours": hours,
            "errors": [
                {
                    "category": r.category,
                    "severity": r.severity,
                    "count": r.count,
                }
                for r in results
            ],
        }
    except Exception as e:
        logger.error(f"Error fetching error trends: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch trends")


@router.get("/metrics/device-state-history/{device_id}")
async def get_device_state_history(
    device_id: str,
    hours: int = Query(24, ge=1, le=720),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get device state change history."""
    try:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        history = (
            db.query(models.DeviceStateHistory)
            .filter(
                models.DeviceStateHistory.device_id == device_id,
                models.DeviceStateHistory.timestamp >= cutoff_time,
            )
            .order_by(models.DeviceStateHistory.timestamp.desc())
            .limit(1000)
            .all()
        )

        return {
            "success": True,
            "device_id": device_id,
            "time_range_hours": hours,
            "history": [
                {
                    "timestamp": h.timestamp.isoformat(),
                    "previous_state": h.previous_state,
                    "new_state": h.new_state,
                    "changed_by": h.changed_by,
                    "reason": h.reason,
                    "metadata": h.metadata,
                }
                for h in history
            ],
        }
    except Exception as e:
        logger.error(f"Error fetching device history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch history")
