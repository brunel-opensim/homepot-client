"""FastAPI application for the AI service."""

import logging
import os
import uuid
from typing import Any, Dict

import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .analysis_modes import ModeManager
from .anomaly_detection import AnomalyDetector
from .device_memory import DeviceMemory
from .event_store import EventStore
from .failure_predictor import FailurePredictor
from .llm import LLMService

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


class ChatMessage(BaseModel):
    """Model for a single chat message."""

    role: str  # 'user' or 'assistant'
    content: str


class QueryRequest(BaseModel):
    """Request model for AI queries."""

    query: str
    device_id: str | None = None
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

                live_context = (
                    f"[CURRENT SYSTEM STATUS]\n"
                    f"Device ID: {request.device_id}\n"
                    f"Risk Level: {prediction.get('risk_level', 'UNKNOWN')}\n"
                    f"Failure Probability: {prediction.get('failure_probability', 0.0)}\n"
                    f"Risk Factors: {', '.join(risk_factors)}\n"
                    f"Recent Events: {recent_events}\n"
                    f"----------------------------------------\n"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to fetch live context for {request.device_id}: {e}"
                )

        # 4. Combine Contexts
        full_context = (
            f"{live_context}\n"
            f"Relevant History:\n{long_term_context}\n\n"
            f"Current Conversation:\n{short_term_context}"
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
        anomaly_score = anomaly_detector.check_anomaly(request.metrics)

        # 2. Retrieve Context
        recent_events_summary = event_store.get_events_summary(request.device_id)

        # 3. LLM Analysis (Contextual & Explanatory)
        # We feed the rule-based score and recent history to the LLM
        prompt = (
            f"Analyze these metrics for device {request.device_id}.\n"
            f"Current Metrics: {request.metrics}\n"
            f"Automated Anomaly Score: {anomaly_score}/1.0\n"
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
