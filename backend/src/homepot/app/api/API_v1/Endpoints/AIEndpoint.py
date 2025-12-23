"""AI Insights API Endpoints.

Provides REST API access to AI-powered analytics, predictions, and recommendations.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from homepot.ai import AIAnalyticsService, FailurePredictor, PredictiveJobScheduler

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class JobScheduleRequest(BaseModel):
    """Request model for job scheduling recommendation."""

    site_id: str = Field(..., description="Target site identifier")
    job_priority: str = Field(
        default="medium", description="Job priority: low, medium, high, critical"
    )
    earliest_start: Optional[str] = Field(
        None, description="Earliest acceptable start time (ISO format)"
    )


class SuccessProbabilityRequest(BaseModel):
    """Request model for success probability calculation."""

    site_id: str = Field(..., description="Target site identifier")
    device_id: str = Field(..., description="Target device identifier")
    scheduled_time: str = Field(..., description="Proposed execution time (ISO format)")


# ==================== Analytics Endpoints ====================


@router.get("/insights/device/{device_id}", tags=["AI Insights"])
async def get_device_insights(
    device_id: str,
    days: int = Query(default=30, ge=1, le=90, description="Analysis period in days"),
) -> Dict[str, Any]:
    """Get comprehensive AI insights for a device.

    Includes performance trends, health score, and predictive analysis.
    """
    try:
        analytics = AIAnalyticsService()

        # Get performance trends
        performance = await analytics.get_device_performance_trends(device_id, days)

        # Get error analysis
        errors = await analytics.get_error_frequency_analysis(
            device_id, days=min(days, 7)
        )

        # Get failure prediction
        predictor = FailurePredictor()
        failure_prediction = await predictor.predict_device_failure(device_id)

        return {
            "device_id": device_id,
            "analysis_period_days": days,
            "performance": performance,
            "errors": errors,
            "failure_prediction": failure_prediction,
            "generated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get device insights: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to generate device insights due to an internal error."
        )


@router.get("/insights/site/{site_id}", tags=["AI Insights"])
async def get_site_insights(
    site_id: str,
    days: int = Query(default=30, ge=1, le=90, description="Analysis period in days"),
) -> Dict[str, Any]:
    """Get comprehensive AI insights for a site.

    Includes job patterns, optimal scheduling windows, and site-level analytics.
    """
    try:
        analytics = AIAnalyticsService()

        # Get job outcome patterns
        job_patterns = await analytics.get_job_outcome_patterns(site_id, days)

        # Get optimal scheduling windows
        scheduling = await analytics.get_optimal_scheduling_windows(site_id)

        # Get configuration change impact
        config_impact = await analytics.get_configuration_impact_analysis(
            site_id, days=min(days, 14)
        )

        return {
            "site_id": site_id,
            "analysis_period_days": days,
            "job_patterns": job_patterns,
            "scheduling_windows": scheduling,
            "configuration_impact": config_impact,
            "generated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get site insights: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to generate site insights due to an internal error."
        )


# ==================== Prediction Endpoints ====================


@router.get("/predictions/failure/{device_id}", tags=["AI Predictions"])
async def predict_device_failure(
    device_id: str,
    window_hours: int = Query(
        default=24, ge=1, le=168, description="Prediction window in hours (max 7 days)"
    ),
) -> Dict[str, Any]:
    """Predict likelihood of device failure in the next N hours.

    Returns probability, risk level, contributing factors, and recommendations.
    """
    try:
        predictor = FailurePredictor()
        prediction = await predictor.predict_device_failure(device_id, window_hours)

        return prediction

    except Exception as e:
        logger.error(f"Failed to predict device failure: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to predict device failure due to an internal error."
        )


@router.get("/predictions/at-risk-devices", tags=["AI Predictions"])
async def get_at_risk_devices(
    site_id: Optional[str] = Query(None, description="Optional site filter"),
    min_risk_level: str = Query(
        default="medium",
        regex="^(low|medium|high|critical)$",
        description="Minimum risk level to include",
    ),
) -> Dict[str, Any]:
    """Identify all devices currently at risk of failure.

    Returns prioritized list with risk levels and recommendations.
    """
    try:
        predictor = FailurePredictor()
        at_risk = await predictor.identify_at_risk_devices(site_id, min_risk_level)

        return at_risk

    except Exception as e:
        logger.error(f"Failed to identify at-risk devices: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to identify at-risk devices due to an internal error."
        )


# ==================== Recommendation Endpoints ====================


@router.post("/recommendations/schedule-job", tags=["AI Recommendations"])
async def recommend_job_schedule(request: JobScheduleRequest) -> Dict[str, Any]:
    """Get AI recommendation for optimal job execution time.

    Considers site schedules, historical success rates, and current conditions.
    """
    try:
        scheduler = PredictiveJobScheduler()

        # Parse earliest_start if provided
        earliest_start = None
        if request.earliest_start:
            try:
                earliest_start = datetime.fromisoformat(request.earliest_start)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid earliest_start format. Use ISO 8601 format.",
                )

        recommendation = await scheduler.recommend_execution_time(
            site_id=request.site_id,
            job_priority=request.job_priority,
            earliest_start=earliest_start,
        )

        return recommendation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to recommend job schedule: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate scheduling recommendation due to an internal error.",
        )


@router.post("/recommendations/success-probability", tags=["AI Recommendations"])
async def calculate_success_probability(
    request: SuccessProbabilityRequest,
) -> Dict[str, Any]:
    """Calculate probability of job success at a specific time.

    Analyzes device health, historical patterns, and site conditions.
    """
    try:
        scheduler = PredictiveJobScheduler()

        # Parse scheduled_time
        try:
            scheduled_time = datetime.fromisoformat(request.scheduled_time)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid scheduled_time format. Use ISO 8601 format.",
            )

        probability = await scheduler.calculate_success_probability(
            site_id=request.site_id,
            device_id=request.device_id,
            scheduled_time=scheduled_time,
        )

        return probability

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to calculate success probability: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to calculate success probability due to an internal error."
        )


@router.get("/recommendations/optimal-windows/{site_id}", tags=["AI Recommendations"])
async def get_optimal_windows(
    site_id: str,
    day_of_week: Optional[int] = Query(
        None, ge=0, le=6, description="Optional day filter (0=Monday, 6=Sunday)"
    ),
) -> Dict[str, Any]:
    """Get optimal scheduling windows for a site.

    Returns recommended time windows that avoid peak hours and maintenance periods.
    """
    try:
        analytics = AIAnalyticsService()
        windows = await analytics.get_optimal_scheduling_windows(site_id, day_of_week)

        return windows

    except Exception as e:
        logger.error(f"Failed to get optimal windows: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to get optimal scheduling windows due to an internal error.",
        )


# ==================== Health Forecast Endpoint ====================


@router.get("/health-forecast", tags=["AI Insights"])
async def get_health_forecast(
    site_id: Optional[str] = Query(None, description="Optional site filter"),
    forecast_hours: int = Query(
        default=24, ge=1, le=168, description="Forecast period in hours"
    ),
) -> Dict[str, Any]:
    """Get health forecast for site or all devices.

    Provides predictive view of system health in the forecast window.
    """
    try:
        predictor = FailurePredictor()

        # Get all at-risk devices
        at_risk = await predictor.identify_at_risk_devices(
            site_id, min_risk_level="low"
        )

        # Analyze overall health trend
        total_devices = at_risk.get("total_devices_analyzed", 0)
        at_risk_count = at_risk.get("at_risk_count", 0)
        risk_dist = at_risk.get("risk_distribution", {})

        # Calculate overall health score
        if total_devices > 0:
            health_percentage = ((total_devices - at_risk_count) / total_devices) * 100
        else:
            health_percentage = 100.0

        # Determine forecast status
        if risk_dist.get("critical", 0) > 0:
            forecast_status = "critical"
            forecast_message = "Critical issues require immediate attention"
        elif risk_dist.get("high", 0) > 0:
            forecast_status = "warning"
            forecast_message = "High-risk devices need attention soon"
        elif at_risk_count > 0:
            forecast_status = "moderate"
            forecast_message = "Some devices show elevated risk"
        else:
            forecast_status = "healthy"
            forecast_message = "All systems operating normally"

        return {
            "site_id": site_id,
            "forecast_hours": forecast_hours,
            "overall_health_score": round(health_percentage, 2),
            "forecast_status": forecast_status,
            "forecast_message": forecast_message,
            "total_devices": total_devices,
            "healthy_devices": total_devices - at_risk_count,
            "at_risk_devices": at_risk_count,
            "risk_distribution": risk_dist,
            "top_concerns": at_risk.get("at_risk_devices", [])[:5],  # Top 5
            "generated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to generate health forecast: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to generate health forecast due to an internal error."
        )


# ==================== System Status ====================


@router.get("/status", tags=["AI Insights"])
async def get_ai_system_status() -> Dict[str, Any]:
    """Get AI system status and capabilities."""
    return {
        "status": "operational",
        "version": "1.0.0",
        "capabilities": {
            "device_insights": True,
            "site_insights": True,
            "failure_prediction": True,
            "at_risk_detection": True,
            "job_scheduling": True,
            "success_probability": True,
            "health_forecast": True,
        },
        "data_sources": {
            "device_metrics": "real-time (5s intervals)",
            "job_outcomes": "historical",
            "device_state_history": "real-time",
            "error_logs": "real-time",
            "configuration_history": "real-time",
            "site_analytics": "aggregated",
            "device_analytics": "aggregated",
            "site_operating_schedules": "configured",
        },
        "timestamp": datetime.utcnow().isoformat(),
    }
