# AI Implementation & Architecture

This document details the implementation of the AI and Machine Learning services for the HOMEPOT Client. The system implements a **Hybrid Analysis Architecture** that combines deterministic rule-based detection with contextual LLM analysis.

## Architecture Overview

We utilize a **Hybrid Analysis** approach to balance speed and intelligence:

1.  **Fast Layer (Rule-Based)**: Immediate detection of known issues (e.g., "CPU > 90%"). This is deterministic, instant, and prevents the LLM from hallucinating safety when metrics are critical.
2.  **Smart Layer (LLM)**: Contextual understanding. It takes the raw data and the rule-based score to explain *why* an anomaly matters and recommends actions.
3.  **Memory Layer (RAG)**: Uses Vector Memory (ChromaDB) to store analysis results. Future queries retrieve these "memories" to identify recurring patterns across devices.

## Memory & Self-Awareness (New)

As of January 2026, the AI has been upgraded with a **Dual-Memory System** and **System Knowledge**, making it fully self-aware and contextually intelligent.

### 1. Short-Term Memory (Conversation History)
*   **Mechanism**: The API now tracks the last 5 exchanges in the conversation.
*   **Benefit**: Enables natural, back-and-forth dialogue. You can ask follow-up questions like "Tell me more about that error" without restating the context.

### 2. Long-Term Memory (Vector Store)
*   **Mechanism**: Uses **ChromaDB** (`ai/device_memory.py`) to store and retrieve semantic memories.
*   **Benefit**: Before answering, the AI searches its "brain" for similar past incidents. If a device failed with a specific error code last month, the AI will recall the solution and suggest it.

### 3. System Knowledge (Self-Awareness)
*   **Mechanism**: The `SystemKnowledge` service (`ai/system_knowledge.py`) scans the codebase structure and `README.md` in real-time.
*   **Benefit**: The AI knows "what" it is. It understands the project structure, where files are located, and the overall goals of HOMEPOT. You can ask "Where is the frontend code?" or "What is the purpose of the `ai` folder?" and it will answer accurately.

### The Workflow (The "Cycle")

1.  **Input**: User asks a question (e.g., "Why is the kitchen camera failing?").
2.  **Context Assembly**:
    *   **Short-Term**: Fetches recent chat history.
    *   **Long-Term**: Queries ChromaDB for similar past events.
    *   **Real-Time**: Fetches current status from PostgreSQL (Sites, Devices, Push Stats).
    *   **System**: Scans the codebase for structural context.
3.  **Processing**: The LLM synthesizes all these inputs.
4.  **Output**: A highly contextualized answer that considers the past, present, and system architecture.

## Key Components

The live AI surface is exposed through the main backend at `/api/v1/ai/*`, implemented in `backend/src/homepot/app/api/API_v1/Endpoints/AIEndpoint.py` and the `ai/` package:

*   **`AIEndpoint.py` (The API Surface)**: The FastAPI router mounted at `/api/v1/ai`.
    *   `POST /api/v1/ai/query`: Answers natural-language questions using RAG, wrapped in the [validation-gate trust envelope](ai-validation-gates.md). Returns `{response, timestamp, trust}`.
    *   `GET /api/v1/ai/anomalies`: Returns the current rule-based anomaly scan. See [Anomaly Detection](anomaly-detection.md).
    *   `GET /api/v1/ai/insights/...` and `/api/v1/ai/predictions/...`: Per-device/site insights and failure predictions.
    *   `POST /api/v1/ai/recommendations/...`: Job-scheduling recommendations and success-probability estimates.
*   **`context_builder.py` (The Context)**: Assembles the real-time, historical, and system context handed to the LLM (sites, devices, alerts, jobs, memories).
*   **`gates/` (The Validation Envelope)**: Gates A-E bound the trust of every answer (see [Trust & Validation Gates](ai-validation-gates.md)).
*   **`system_knowledge.py` (The Self-Awareness)**:
    *   Scans the project directory structure.
    *   Reads the root `README.md` to understand the project's purpose.
    *   Provides the "System Context" to the LLM.
*   **`anomaly_detection.py` (The Reflex)**:
    *   Implements the "Fast Layer".
    *   Calculates anomaly scores (0.0 - 1.0) based on stability and resource usage.
    *   See [Anomaly Detection Documentation](anomaly-detection.md) for scoring logic.
*   **`llm.py` (The Voice)**: A wrapper for **Ollama** that manages the connection to local models (Llama/Mistral) and constructs context-aware prompts.
*   **`device_memory.py` (The Long-Term Memory)**: Manages **ChromaDB** interactions for storing and retrieving semantic vector embeddings of device logs.
*   **`failure_predictor.py` / `job_scheduler.py` / `analytics_service.py`**: Predictive-maintenance risk scoring, job scheduling recommendations, and analytics aggregations.

!!! note "Legacy standalone service"
    An older, standalone FastAPI app in `ai/api.py` (routes like `POST /api/ai/analyze`, `POST /api/ai/query`, `POST /api/ai/mode`, `GET /predict/{device_id}`) predates the integrated `/api/v1/ai` surface. It is **not** the live service, is not started by any launch script, and does **not** run the validation gates. It remains in the repository and is still exercised by some backend tests. Prefer the integrated `/api/v1/ai/*` endpoints for all new work.

## Predictive Maintenance

We have introduced a **Predictive Maintenance** module (`failure_predictor.py`) that analyzes historical metrics to forecast potential failures.

### Features
*   **Risk Scoring**: Calculates a risk score (0.0 - 1.0) based on CPU, Memory, and Disk usage trends.
*   **Trend Analysis**: Detects increasing resource usage over time.
*   **API Endpoint**: `GET /api/v1/ai/predictions/failure/{device_id}` returns the current risk assessment.

## NLP Context Injection

The AI Query endpoint (`POST /api/v1/ai/query`) has been enhanced to bridge the gap between historical knowledge and real-time status.

### How it Works
When a user asks a question about a specific device (e.g., "Is the kitchen camera failing?"), the system:
1.  **Detects** the `device_id` in the request.
2.  **Fetches** the live risk assessment from the `FailurePredictor`.
3.  **Retrieves** the last 5 raw events from the `EventStore`.
4.  **Injects** this real-time context directly into the LLM's prompt.

This ensures the AI answers based on *what is happening right now*, not just what happened in the past.

### System Prompt Refinement
To ensure the LLM correctly interprets the injected context, we have updated the system prompts in `analysis_modes.py`. Each mode (Maintenance, Predictive, Executive) now includes a **CRITICAL RULE**:
> "If the context contains a [CURRENT SYSTEM STATUS] block, prioritize this real-time data over historical memories."

This prevents the AI from hallucinating safety based on old logs when the live system is actually in a critical state.

## Development Guidelines

### Execution Strategy: Local First, Docker Second

**Rule of Development:**
We prioritize **normal execution cycles** (running directly in a local environment) over Docker during development. Docker is treated as an additional deployment feature, not the primary runner for development.

*   **Do not** rely on `docker-compose` for daily coding and testing of the AI service.
*   **Do** run the service using a local Python virtual environment.
*   **Do** ensure tests pass locally using `pytest`.

### Prerequisites
*   Python 3.11+
*   [Ollama](https://ollama.ai/) installed and running locally.

### Running Locally

1.  **Activate Virtual Environment**:
    ```bash
    source .venv/bin/activate
    ```

2.  **Install Dependencies**:
    ```bash
    pip install -r backend/requirements.txt
    ```

3.  **Run the Service**: The AI endpoints are part of the main backend, so start the normal backend app rather than a separate AI process:
    ```bash
    python -m uvicorn homepot.app.main:app --host 0.0.0.0 --port 8000 --reload
    ```
    The AI API is available at `http://localhost:8000/api/v1/ai/*`. The legacy standalone `ai/api.py` service can still be run on port 8001 for debugging legacy paths, but it is not the live service.

4.  **Run Tests**:
    ```bash
    pytest backend/tests/test_ai_service.py backend/tests/test_ai_nlp_integration.py backend/tests/test_validation_gates.py
    ```
