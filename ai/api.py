"""FastAPI application for the AI service."""

import asyncio
import logging
import os
import uuid
from typing import Any, Dict

import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, select

from homepot.app.models.AnalyticsModel import Alert
from homepot.database import get_database_service

from .analysis_modes import ModeManager
from .anomaly_detection import AnomalyDetector
from .context_builder import ContextBuilder
from .device_memory import DeviceMemory
from .device_resolver import DeviceResolver
from .event_store import EventStore
from .failure_predictor import FailurePredictor
from .llm import LLMService
from .prompts import PromptManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load config
config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

app = FastAPI(title=config["app"]["name"], version=config["app"]["version"])

# Initialize services
llm_service = LLMService()
memory_service = DeviceMemory()
anomaly_detector = AnomalyDetector()
event_store = EventStore()
mode_manager = ModeManager()
failure_predictor = FailurePredictor(event_store)
context_builder = ContextBuilder()


class ChatMessage(BaseModel):
    """Model for a single chat message."""

    role: str  # 'user' or 'assistant'
    content: str


class QueryRequest(BaseModel):
    """Request model for AI queries."""

    query: str
    device_id: str | None = None
    user_id: str | None = None  # Added for user context
    history: list[ChatMessage] = Field(default_factory=list)


class AnalysisRequest(BaseModel):
    """Request model for device analysis."""

    device_id: str
    metrics: Dict[str, Any]


class ModeRequest(BaseModel):
    """Request model for setting analysis mode."""

    mode: str


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Check service health."""
    llm_health = llm_service.check_health()
    return {
        "status": "healthy",
        "llm_connected": llm_health,
        "version": config["app"]["version"],
        "mode": mode_manager.current_mode.value,
    }


@app.post("/api/ai/mode")
async def set_mode(request: ModeRequest) -> Dict[str, str]:
    """Set the AI analysis mode."""
    mode_manager.set_mode(request.mode)
    return {"status": "success", "mode": mode_manager.current_mode.value}


@app.post("/api/ai/query")
async def query_ai(request: QueryRequest) -> Dict[str, Any]:
    """Ask a natural language question about devices with context."""
    try:
        # 1. Retrieve Long-Term Context from Vector Memory
        context_memories = memory_service.query_similar(request.query)
        long_term_context = "\n".join([m["content"] for m in context_memories])

        # 2. Construct Short-Term Context from Conversation History
        short_term_context = "\n".join(
            [f"{msg.role}: {msg.content}" for msg in request.history[-5:]]
        )

        # 3. Retrieve Real-Time Device Context (The "Senses")
        live_context = ""
        if request.device_id:
            try:
                # Get failure prediction
                prediction = await failure_predictor.predict_device_failure(
                    request.device_id
                )

                # Get recent raw events
                recent_events = event_store.get_recent_events(
                    request.device_id, limit=5
                )

                risk_factors = [
                    f.get("name", "Unknown") for f in prediction.get("risk_factors", [])
                ]
                # Fetch additional context concurrently
                db_service = await get_database_service()
                async with db_service.get_session() as session:
                    # Resolve Device ID
                    resolver = DeviceResolver(session)
                    device_int_id = await resolver.resolve(request.device_id)

                    (
                        job_context,
                        error_context,
                        config_context,
                        audit_context,
                        api_context,
                        state_context,
                        push_context,
                        site_context,
                        metadata_context,
                        metrics_context,
                        alert_context,
                        user_context,
                    ) = await asyncio.gather(
                        context_builder.get_job_context(session=session),
                        context_builder.get_error_context(
                            device_id=request.device_id,
                            session=session,
                            device_int_id=device_int_id,
                        ),
                        context_builder.get_config_context(
                            device_id=request.device_id,
                            session=session,
                            device_int_id=device_int_id,
                        ),
                        context_builder.get_audit_context(
                            device_id=request.device_id,
                            session=session,
                            device_int_id=device_int_id,
                        ),
                        context_builder.get_api_context(session=session),
                        context_builder.get_state_context(
                            device_id=request.device_id, session=session
                        ),
                        context_builder.get_push_context(
                            device_id=request.device_id, session=session
                        ),
                        context_builder.get_site_context(
                            device_id=request.device_id,
                            session=session,
                            device_int_id=device_int_id,
                        ),
                        context_builder.get_metadata_context(
                            device_id=request.device_id,
                            session=session,
                            device_int_id=device_int_id,
                        ),
                        context_builder.get_metrics_context(
                            device_id=request.device_id,
                            session=session,
                            device_int_id=device_int_id,
                        ),
                        context_builder.get_alert_context(
                            device_id=request.device_id, session=session
                        ),
                        (
                            context_builder.get_user_context(
                                user_id=request.user_id, session=session
                            )
                            if request.user_id
                            else asyncio.sleep(0, result="")
                        ),
                    )

                context_data = {
                    "job": job_context,
                    "error": error_context,
                    "config": config_context,
                    "audit": audit_context,
                    "api": api_context,
                    "state": state_context,
                    "push": push_context,
                    "site": site_context,
                    "metadata": metadata_context,
                    "metrics": metrics_context,
                    "alert": alert_context,
                    "user": user_context,
                }

                live_context = PromptManager.build_live_context(
                    request.device_id,
                    prediction,
                    risk_factors,
                    recent_events,
                    context_data,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to fetch live context for {request.device_id}: {e}"
                )

        # 4. Combine Contexts
        full_context = PromptManager.build_full_prompt(
            live_context, long_term_context, short_term_context
        )

        # 5. Generate response
        response = llm_service.generate_response(
            request.query,
            context=full_context,
            system_prompt=mode_manager.get_system_prompt(),
        )

        return {
            "response": response,
            "context_used": {
                "long_term_memories": len(context_memories),
                "short_term_messages": len(request.history),
                "live_context_injected": bool(live_context),
            },
        }
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ai/analyze")
async def analyze_device(request: AnalysisRequest) -> Dict[str, Any]:
    """Analyze device metrics for anomalies using Hybrid approach."""
    try:
        # 0. Store current metrics as an event
        event_store.add_event(
            {
                "device_id": request.device_id,
                "event": "metrics_update",
                "value": request.metrics,
                # timestamp added by store
            }
        )

        # 1. Rule-Based Analysis (Fast & Deterministic)
        anomaly_score, anomaly_reasons = anomaly_detector.check_anomaly(request.metrics)

        # 1.1 Persist Low-Level Alerts Immediately
        if anomaly_reasons:
            try:
                db_service = await get_database_service()
                async with db_service.get_session() as session:
                    for reason in anomaly_reasons:
                        # Heuristic mapping for properties
                        severity = "warning"
                        if "System Failure" in reason or "High Instability" in reason:
                            severity = "critical"
                        elif "High Error Rate" in reason:
                            severity = "error"

                        category = "hardware"
                        if "Latency" in reason:
                            category = "network"
                        elif "Error" in reason or "Failure" in reason:
                            category = "software"

                        # Check for existing active alert to avoid duplicates
                        stmt = select(Alert).where(
                            and_(
                                Alert.device_id == request.device_id,
                                Alert.title == reason,
                                Alert.status == "active",
                            )
                        )
                        result = await session.execute(stmt)
                        existing_alert = result.scalar_one_or_none()

                        if not existing_alert:
                            # Create new alert
                            alert = Alert(
                                device_id=request.device_id,
                                title=reason,
                                description=f"Detected by AnomalyDetector (Score: {anomaly_score:.2f})",
                                severity=severity,
                                category=category,
                                status="active",
                                ai_confidence=anomaly_score,
                                ai_recommendation="Analysis pending...",
                            )
                            session.add(alert)
                    await session.commit()
            except Exception as e:
                logger.error(f"Failed to persist alerts: {e}")

        # 2. Retrieve Context
        recent_events_summary = event_store.get_events_summary(request.device_id)

        # 3. LLM Analysis (Contextual & Explanatory)
        # We feed the rule-based score and recent history to the LLM
        prompt = (
            f"Analyze these metrics for device {request.device_id}.\n"
            f"Current Metrics: {request.metrics}\n"
            f"Automated Anomaly Score: {anomaly_score}/1.0\n"
            f"Detected Anomalies: {', '.join(anomaly_reasons)}\n"
            f"Recent Events Context:\n{recent_events_summary}\n"
            f"Task: Explain any anomalies found and recommend actions."
        )
        analysis = llm_service.generate_response(
            prompt, system_prompt=mode_manager.get_system_prompt()
        )

        # 4. Store Analysis in Memory
        memory_service.add_memory(
            text=f"Analysis for {request.device_id}: {analysis}",
            metadata={
                "device_id": request.device_id,
                "anomaly_score": anomaly_score,
                "is_anomaly": anomaly_score > 0.5,
            },
            memory_id=str(uuid.uuid4()),
        )

        status = "anomaly_detected" if anomaly_score > 0.5 else "normal"

        return {
            "device_id": request.device_id,
            "anomaly_score": anomaly_score,
            "is_anomaly": anomaly_score > 0.5,
            "analysis": analysis,
            "status": status,
        }
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/predict/{device_id}")
async def predict_failure(device_id: str) -> Dict[str, Any]:
    """Predict failure risk for a specific device."""
    try:
        prediction = await failure_predictor.predict_device_failure(device_id)
        return prediction
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config["app"]["host"], port=config["app"]["port"])
