"""FastAPI application for the AI service."""

import logging
from typing import Any, Dict

import yaml
from device_memory import DeviceMemory
from fastapi import FastAPI, HTTPException
from llm import LLMService
from pydantic import BaseModel

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


class QueryRequest(BaseModel):
    """Request model for AI queries."""

    query: str
    device_id: str | None = None


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
    """Ask a natural language question about devices."""
    try:
        # 1. Retrieve context from memory
        context_memories = memory_service.query_similar(request.query)
        context_str = "\n".join([m["content"] for m in context_memories])

        # 2. Generate response
        response = llm_service.generate_response(request.query, context=context_str)

        return {"response": response, "context_used": len(context_memories)}
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ai/analyze")
async def analyze_device(request: AnalysisRequest) -> Dict[str, Any]:
    """Analyze device metrics for anomalies."""
    try:
        # Placeholder for anomaly detection logic
        # In future: use anomaly_detection.py

        prompt = (
            f"Analyze these metrics for device {request.device_id}: "
            f"{request.metrics}. Are there any anomalies?"
        )
        analysis = llm_service.generate_response(prompt)

        return {
            "device_id": request.device_id,
            "analysis": analysis,
            "status": "processed",
        }
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config["app"]["host"], port=config["app"]["port"])
