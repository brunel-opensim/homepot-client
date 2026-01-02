"""AI Insights API Endpoints.

Provides REST API access to AI-powered analytics, predictions, and recommendations.
"""

import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, case, func, select

# Add project root to path to allow importing 'ai' package
# Current file: backend/src/homepot/app/api/API_v1/Endpoints/AIEndpoint.py
# Root is 7 levels up
project_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../../../../")
)
if project_root not in sys.path:
    sys.path.append(project_root)

from ai.analytics_service import AIAnalyticsService  # noqa: E402
from ai.anomaly_detection import AnomalyDetector  # noqa: E402
from ai.context_builder import ContextBuilder  # noqa: E402
from ai.device_memory import DeviceMemory  # noqa: E402
from ai.failure_predictor import FailurePredictor  # noqa: E402
from ai.job_scheduler import PredictiveJobScheduler  # noqa: E402
from ai.llm import LLMService  # noqa: E402
from ai.system_knowledge import SystemKnowledge  # noqa: E402

from homepot.app.models.AnalyticsModel import (  # noqa: E402
    DeviceMetrics,
    DeviceStateHistory,
    PushNotificationLog,
)
from homepot.database import get_database_service  # noqa: E402
from homepot.models import Device, HealthCheck, Site  # noqa: E402

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


class ChatMessage(BaseModel):
    """Model for a single chat message."""

    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class AIQueryRequest(BaseModel):
    """Request model for AI query."""

    query: str = Field(..., description="The question or prompt for the AI")
    context: Optional[str] = Field(None, description="Optional context for the query")
    device_id: Optional[str] = Field(None, description="Optional device ID for context")
    history: Optional[list[ChatMessage]] = Field(
        default_factory=list, description="Conversation history for short-term memory"
    )


# ==================== Analytics Endpoints ====================


@router.get("/anomalies", tags=["AI Insights"])
async def get_system_anomalies() -> Dict[str, Any]:
    """Detect system-wide anomalies using AI heuristics."""
    try:
        detector = AnomalyDetector()
        anomalies = []

        db_service = await get_database_service()
        async with db_service.get_session() as session:
            # 1. Get all monitored devices
            result = await session.execute(
                select(Device).where(Device.is_monitored.is_(True))
            )
            devices = result.scalars().all()

            for device in devices:
                device_metrics: Dict[str, Any] = {}

                # 2. Get latest metrics
                metrics_result = await session.execute(
                    select(DeviceMetrics)
                    .where(DeviceMetrics.device_id == device.device_id)
                    .order_by(DeviceMetrics.timestamp.desc())
                    .limit(1)
                )
                latest_metric = metrics_result.scalars().first()
                if latest_metric:
                    device_metrics.update(
                        {
                            "cpu_percent": latest_metric.cpu_percent,
                            "memory_percent": latest_metric.memory_percent,
                            "disk_percent": latest_metric.disk_percent,
                            "network_latency_ms": latest_metric.network_latency_ms,
                            "error_rate": latest_metric.error_rate,
                        }
                    )

                # 3. Get Flapping Count (last 1 hour)
                one_hour_ago = datetime.utcnow() - timedelta(hours=1)
                flapping_result = await session.execute(
                    select(func.count(DeviceStateHistory.id)).where(
                        and_(
                            DeviceStateHistory.device_id == device.device_id,
                            DeviceStateHistory.timestamp >= one_hour_ago,
                        )
                    )
                )
                device_metrics["flapping_count"] = float(flapping_result.scalar() or 0)

                # 4. Get Consecutive Failures
                # Simplified: Check last 5 health checks
                health_result = await session.execute(
                    select(HealthCheck)
                    .where(HealthCheck.device_id == device.id)
                    .order_by(HealthCheck.timestamp.desc())
                    .limit(5)
                )
                checks = health_result.scalars().all()
                consecutive_failures = 0
                for check in checks:
                    if not check.is_healthy:
                        consecutive_failures += 1
                    else:
                        break
                device_metrics["consecutive_failures"] = float(consecutive_failures)

                # 5. Run Detection
                score = detector.check_anomaly(device_metrics)

                if score > 0:
                    anomalies.append(
                        {
                            "device_id": device.device_id,
                            "device_name": device.name,
                            "score": round(score, 2),
                            "severity": "critical" if score >= 0.8 else "warning",
                            "metrics": device_metrics,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )

        # Sort by score descending
        anomalies.sort(key=lambda x: float(str(x["score"])), reverse=True)

        return {"count": len(anomalies), "anomalies": anomalies}

    except Exception as e:
        logger.error(f"Failed to detect anomalies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Anomaly detection failed")


@router.post("/query", tags=["AI Chat"])
async def query_ai(request: AIQueryRequest) -> Dict[str, Any]:
    """Query the AI assistant."""
    try:
        llm = LLMService()
        knowledge = SystemKnowledge(project_root)
        memory = DeviceMemory()
        context_builder = ContextBuilder()

        # 1. Build Short-Term Context (Conversation History)
        short_term_context = ""
        if request.history:
            short_term_context = "\n[CONVERSATION HISTORY]\n"
            short_term_context += "\n".join(
                [f"{msg.role}: {msg.content}" for msg in request.history[-5:]]
            )

        # 2. Build Long-Term Context (Vector Memory)
        long_term_context = ""
        try:
            # Get Memory Stats (Self-Awareness)
            mem_stats = memory.get_memory_stats()
            long_term_context = (
                f"\n[MEMORY SYSTEM STATUS]\n"
                f"Total Memories Stored: {mem_stats['total_memories']}\n"
            )

            # Get Similar Memories
            similar_memories = memory.query_similar(request.query)
            if similar_memories:
                long_term_context += "\n[RELEVANT MEMORIES]\n"
                long_term_context += "\n".join(
                    [f"- {m['content']}" for m in similar_memories]
                )
        except Exception as e:
            logger.warning(f"Failed to query vector memory: {e}")

        # 3. Build Real-Time System Context
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            # Get Sites
            result = await session.execute(select(Site).where(Site.is_active.is_(True)))
            sites = result.scalars().all()

            site_context = "[CURRENT SYSTEM STATUS]\n"
            site_context += f"Total Sites: {len(sites)}\n"
            for site in sites:
                site_context += f"- Site: {site.name} (ID: {site.site_id}), Location: {site.location}\n"

            # Get Push Notification Stats (Last 24 hours)
            one_day_ago = datetime.utcnow() - timedelta(days=1)
            push_result = await session.execute(
                select(
                    func.count(PushNotificationLog.id),
                    func.sum(
                        case((PushNotificationLog.status == "delivered", 1), else_=0)
                    ),
                    func.avg(PushNotificationLog.latency_ms),
                ).where(PushNotificationLog.sent_at >= one_day_ago)
            )
            total_push, delivered_push, avg_latency = push_result.one()

            site_context += "\n[PUSH NOTIFICATION STATS (24h)]\n"
            site_context += f"- Total Sent: {total_push or 0}\n"
            site_context += f"- Delivered: {delivered_push or 0}\n"
            if avg_latency:
                site_context += f"- Avg Latency: {round(avg_latency, 2)}ms\n"

            # Get Job Context if relevant
            job_context = await context_builder.get_job_context(session=session)

        # 4. Assemble Final Context
        full_context = (
            f"{site_context}\n{job_context}\n{long_term_context}\n{short_term_context}"
        )

        if request.context:
            full_context += f"\n[USER CONTEXT]\n{request.context}"

        if request.device_id:
            full_context += f"\n[FOCUS DEVICE]\nID: {request.device_id}"

        # Get static system knowledge
        system_knowledge = knowledge.get_full_system_context()

        response = llm.generate_response(
            prompt=request.query,
            context=full_context,
            system_prompt=(
                "IDENTITY:\n"
                "You are the HOMEPOT System Diagnostic AI, an advanced operational "
                "assistant for the HOMEPOT Client ecosystem.\n"
                "Your goal is to monitor, diagnose, and explain the behavior of "
                "IoT devices, sites, and the platform itself.\n\n"
                "CAPABILITIES & DATA SOURCES:\n"
                "1. Real-Time Database (PostgreSQL): You have access to live device "
                "metrics, site status, and push notification stats.\n"
                "2. Long-Term Memory (ChromaDB): You can recall past anomalies, "
                "error patterns, and resolutions to identify recurring issues.\n"
                "3. System Knowledge: You are self-aware of the codebase structure, "
                "file locations, and documentation.\n"
                "4. Short-Term Memory: You maintain context of the current conversation.\n\n"
                "SYSTEM CONTEXT:\n"
                f"{system_knowledge}\n\n"
                "INSTRUCTIONS:\n"
                "- Scope your answers to the HOMEPOT system. Do not answer unrelated "
                "general knowledge questions.\n"
                "- Use the provided [CURRENT SYSTEM STATUS] and [RELEVANT MEMORIES] "
                "to ground your answers in facts.\n"
                "- If you don't know something, admit it. Do not hallucinate system details.\n"
                "- Be concise, professional, and technical where appropriate."
            ),
        )
        return {
            "response": response,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"AI query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/insights/push-notifications", tags=["AI Insights"])
async def get_push_insights(
    device_id: Optional[str] = Query(
        None, description="Optional device ID to filter by"
    ),
    days: int = Query(default=7, ge=1, le=90, description="Analysis period in days"),
) -> Dict[str, Any]:
    """Get AI analytics for push notification delivery."""
    try:
        analytics = AIAnalyticsService()
        analytics_result = await analytics.get_push_notification_analytics(
            device_id, days
        )

        # If the analytics service indicates an error, raise a generic HTTP error
        if (
            isinstance(analytics_result, dict)
            and analytics_result.get("status") == "error"
        ):
            logger.error(
                "Push notification analytics service reported an error: %s",
                analytics_result.get("message"),
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to analyze push notifications",
            )

        return analytics_result
    except HTTPException:
        # Re-raise HTTPException without modification
        raise
    except Exception as e:
        logger.error(f"Failed to get push insights: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to analyze push notifications"
        )


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
            status_code=500,
            detail="Failed to generate device insights due to an internal error.",
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
            status_code=500,
            detail="Failed to generate site insights due to an internal error.",
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
            status_code=500,
            detail="Failed to predict device failure due to an internal error.",
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
            status_code=500,
            detail="Failed to identify at-risk devices due to an internal error.",
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
            status_code=500,
            detail="Failed to calculate success probability due to an internal error.",
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
            status_code=500,
            detail="Failed to generate health forecast due to an internal error.",
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
