# AI Implementation & Architecture

This document details the implementation of the AI and Machine Learning services for the HOMEPOT Client. The system implements a **Hybrid Analysis Architecture** that combines deterministic rule-based detection with contextual LLM analysis.

## Architecture Overview

We utilize a **Hybrid Analysis** approach to balance speed and intelligence:

1.  **Fast Layer (Rule-Based)**: Immediate detection of known issues (e.g., "CPU > 90%"). This is deterministic, instant, and prevents the LLM from hallucinating safety when metrics are critical.
2.  **Smart Layer (LLM)**: Contextual understanding. It takes the raw data and the rule-based score to explain *why* an anomaly matters and recommends actions.
3.  **Memory Layer (RAG)**: Uses Vector Memory (ChromaDB) to store analysis results. Future queries retrieve these "memories" to identify recurring patterns across devices.

### The Two Memories

Think of it like a **Senior Engineer (the AI)** working with a **Log Book (PostgreSQL)** and a **Personal Diary (ChromaDB)**.

#### 1. PostgreSQL: "The Facts" (Structured Memory)
*   It holds the hard numbers: "Device A had 95% CPU at 10:00 AM."
*   It is exact, rigid, and holds the "System of Record."
*   **Role**: The AI looks here to get the raw data to analyze.

#### 2. ChromaDB: "The Experience" (Semantic Memory)
*   It holds the insights: "Last time Device A had 95% CPU, it was because of a memory leak in the video process."
*   It is fuzzy, searchable by meaning, and holds "Wisdom."
*   **Role**: The AI looks here to find patterns from the past.

### The Workflow (The "Cycle")

1.  **Input (The Trigger)**
    *   **User Input**: You ask, "Why is the kitchen camera failing?"
    *   **System Input**: Or, the system automatically sends current metrics (from PostgreSQL/Devices) to the AI.

2.  **Context Gathering (The Brain)**
    *   The AI looks at the Current Metrics (The Facts).
    *   The AI searches ChromaDB for similar past events (The Experience). "Have we seen this error before?"

3.  **Processing (The Intelligence)**
    *   The LLM combines the Facts + Experience to generate an answer.

4.  **Output (The Result)**
    *   **Recommendation**: "Restart the video service. This looks like the memory leak we saw last Tuesday."
    *   **Learning**: The AI saves this new analysis into ChromaDB. Now it has "learned" from this event for next time.

## Key Components

The implementation consists of four core modules:

*   **`api.py` (The Brain)**: A FastAPI application serving as the entry point.
    *   `POST /api/ai/analyze`: Analyzes metrics, scores anomalies, and generates LLM explanations.
    *   `POST /api/ai/query`: Answers natural language questions using RAG (Retrieval-Augmented Generation).
    *   `POST /api/ai/mode`: Switches the AI's analysis persona (Maintenance, Predictive, Executive).
    *   `GET /api/ai/anomalies`: Returns a list of currently detected anomalies. See [Anomaly Detection](anomaly-detection.md) for details.
*   **`anomaly_detection.py` (The Reflex)**:
    *   Implements the "Fast Layer".
    *   Calculates anomaly scores (0.0 - 1.0) based on stability and resource usage.
    *   See [Anomaly Detection Documentation](anomaly-detection.md) for scoring logic.
*   **`llm.py` (The Voice)**: A wrapper for **Ollama** that manages the connection to local models (Llama/Mistral) and constructs context-aware prompts.
*   **`device_memory.py` (The Long-Term Memory)**: Manages **ChromaDB** interactions for storing and retrieving semantic vector embeddings of device logs.
*   **`event_store.py` (The Short-Term Memory)**: Caches recent device events in-memory and persists them to the **PostgreSQL** `device_metrics` table to provide immediate context for analysis.
*   **`analysis_modes.py` (The Persona)**: Manages different system prompts to tailor the AI's output style and focus (e.g., technical vs. executive).

## Predictive Maintenance

We have introduced a **Predictive Maintenance** module (`failure_predictor.py`) that analyzes historical metrics to forecast potential failures.

### Features
*   **Risk Scoring**: Calculates a risk score (0.0 - 1.0) based on CPU, Memory, and Disk usage trends.
*   **Trend Analysis**: Detects increasing resource usage over time.
*   **API Endpoint**: `GET /predict/{device_id}` returns the current risk assessment.

## NLP Context Injection

The AI Query endpoint (`/api/ai/query`) has been enhanced to bridge the gap between historical knowledge and real-time status.

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

3.  **Run the Service**:
    ```bash
    python ai/api.py
    ```
    The API will be available at `http://localhost:8000`.

4.  **Run Tests**:
    ```bash
    pytest backend/tests/test_ai_service.py
    ```
