"""FastAPI application for the AI service."""

import logging
import uuid
from typing import Any, Dict

import yaml
from anomaly_detection import AnomalyDetector
from device_memory import DeviceMemory
from fastapi import FastAPI, HTTPException
from llm import LLMService
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

app = FastAPI(title=config["app"]["name"], version=config["app"]["version"])

# Initialize services
llm_service = LLMService()
memory_service = DeviceMemory()
anomaly_detector = AnomalyDetector()


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


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Check service health."""
    llm_health = llm_service.check_health()
    return {
        "status": "healthy",
        "llm_connected": llm_health,
        "version": config["app"]["version"],
    }


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

        # 3. Combine Contexts
        full_context = (
            f"Relevant History:\n{long_term_context}\n\n"
            f"Current Conversation:\n{short_term_context}"
        )

        # 4. Generate response
        response = llm_service.generate_response(request.query, context=full_context)

        return {
            "response": response,
            "context_used": {
                "long_term_memories": len(context_memories),
                "short_term_messages": len(request.history),
            },
        }
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ai/analyze")
async def analyze_device(request: AnalysisRequest) -> Dict[str, Any]:
    """Analyze device metrics for anomalies using Hybrid approach."""
    try:
        # 1. Rule-Based Analysis (Fast & Deterministic)
        anomaly_score = anomaly_detector.check_anomaly(request.metrics)

        # 2. LLM Analysis (Contextual & Explanatory)
        # We feed the rule-based score to the LLM to guide its interpretation
        prompt = (
            f"Analyze these metrics for device {request.device_id}.\n"
            f"Metrics: {request.metrics}\n"
            f"Automated Anomaly Score: {anomaly_score}/1.0\n"
            f"Task: Explain any anomalies found and recommend actions."
        )
        analysis = llm_service.generate_response(prompt)

        # 3. Store Analysis in Memory
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config["app"]["host"], port=config["app"]["port"])
