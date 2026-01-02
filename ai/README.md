# AI/LLM Services

> **Status:** Foundation Implemented (December 2025)
> **Roadmap:** [AI Integration Roadmap](/docs/ai-roadmap.md)
> **Documentation:** [Context Builder](/docs/ai-context-builder.md)

This directory contains the AI and Machine Learning services for the HOMEPOT Client. The system implements a **Hybrid Analysis Architecture** that combines deterministic rule-based detection with contextual LLM analysis.

## Context Builder

The **Context Builder** (`ai/context_builder.py`) aggregates data from multiple sources to provide "situational awareness" to the LLM. It currently integrates:

*   **Job Outcomes:** Recent failed jobs (e.g., firmware updates).
*   **Error Logs:** System errors and stack traces.
*   **Configuration History:** Recent changes to device settings.
*   **Audit Logs:** User actions and system events.
*   **API Request Logs:** Failed API calls (4xx/5xx errors).
*   **Device State History:** Connectivity changes (Online/Offline).
*   **Push Notification Logs:** Delivery status and failures (FCM/APNs).
*   **User Context:** User profile and recent activity history.
*   **Site Context:** Operating hours and open/closed status.
*   **Metadata Context:** Device specifications (Firmware/IP) and Health Check logs.

For full details, see the [Context Builder Documentation](/docs/ai-context-builder.md).

## Core Components

### Device Resolver (`ai/device_resolver.py`)
A specialized service that handles the resolution of public UUID strings (`device_id`) to internal Integer Primary Keys (`id`).
*   **Purpose:** Bridges the gap between the API (public UUIDs) and the Database (Integer FKs).
*   **Optimization:** Caches resolutions within the request session scope to prevent redundant database lookups.

### Prompt Manager (`ai/prompts.py`)
Centralizes all prompt templates and string construction logic.
*   **Purpose:** Decouples prompt engineering from business logic.
*   **Features:** Provides static methods to build "Live Context" and "Full Prompts" ensuring consistent formatting across the application.

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

## The "Brain" Workflow

1.  **Input**: User asks a question (e.g., "Why is the camera offline?").
2.  **Context Assembly**:
    *   **Short-Term**: Fetches recent chat history.
    *   **Long-Term**: Queries ChromaDB for similar past events.
    *   **Real-Time**: Fetches current status from PostgreSQL (Sites, Devices, Push Stats).
    *   **System**: Scans the codebase for structural context.
3.  **Processing**: The LLM synthesizes all these inputs.
4.  **Output**: A highly contextualized answer that considers the past, present, and system architecture.

## Predictive Maintenance (Phase 4)

We have introduced a **Predictive Maintenance** module (`failure_predictor.py`) that analyzes historical metrics to forecast potential failures.

### Features
- **Risk Scoring**: Calculates a risk score (0.0 - 1.0) based on CPU, Memory, and Disk usage trends.
- **Trend Analysis**: Detects increasing resource usage over time.
- **API Endpoint**: `GET /predict/{device_id}` returns the current risk assessment.

### Usage
```bash
curl http://localhost:8000/predict/device-123
```

## NLP Context Injection (Phase 5)

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

## Key Components

The implementation consists of four core modules:

*   **`api.py` (The Brain)**: A FastAPI application serving as the entry point.
    *   `POST /api/ai/analyze`: Analyzes metrics, scores anomalies, and generates LLM explanations.
    *   `POST /api/ai/query`: Answers natural language questions using RAG (Retrieval-Augmented Generation).
    *   `POST /api/ai/mode`: Switches the AI's analysis persona (Maintenance, Predictive, Executive).
*   **`anomaly_detection.py` (The Reflex)**: Implements rule-based logic to check thresholds (CPU, Memory, Disk, Error Rate) and calculate an `anomaly_score` (0.0 - 1.0).
*   **`llm.py` (The Voice)**: A wrapper for **Ollama** that manages the connection to local models (Llama/Mistral) and constructs context-aware prompts.
*   **`device_memory.py` (The Long-Term Memory)**: Manages **ChromaDB** interactions for storing and retrieving semantic vector embeddings of device logs.
*   **`event_store.py` (The Short-Term Memory)**: Caches recent device events in-memory and persists them to the **PostgreSQL** `device_metrics` table to provide immediate context for analysis.
*   **`analysis_modes.py` (The Persona)**: Manages different system prompts to tailor the AI's output style and focus (e.g., technical vs. executive).

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

### Automated Setup (Recommended)

We provide a helper script to automate the installation and configuration of Ollama. This script will:
1.  Install Ollama (if missing).
2.  Check if the port (11434) is free or already in use.
3.  Start the Ollama server.
4.  Pull the specific model defined in `ai/config.yaml` (e.g., `llama3.2`).

```bash
./scripts/setup-ollama.sh
```

### Manual Setup (Alternative)

If you prefer to set up the environment manually:

1.  **Install Ollama**: Follow instructions at [ollama.ai](https://ollama.ai).
2.  **Start the Server**:
    ```bash
    ollama serve
    ```
3.  **Pull the Model**:
    Check `ai/config.yaml` for the required model, then run:
    ```bash
    ollama pull llama3.2
    ```

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

### Running the Demo

We have a **System Verification Suite** that demonstrates the full AI pipeline. This is not just a simulation; it verifies the integration of the Database, EventStore, Predictor, and LLM.

**The Workflow:**
`DB (Postgres) -> EventStore -> Predictor -> Context Builder -> LLM -> Response`

1.  **Ensure Ollama is running**:
    You can use our helper script to ensure everything is ready:
    ```bash
    ./scripts/setup-ollama.sh
    ```
    Or manually start it:
    ```bash
    ollama serve
    ```

2.  **Run the Analysis**:
    Run the demo script. It will automatically detect a device with recent metrics in the database, analyze its risk, and query the LLM.
    ```bash
    python backend/utils/demo_ai_scenario.py
    ```

    **What to expect:**
    *   The script will connect to the **PostgreSQL** database (configured in `ai/config.yaml`).
    *   It will find the device with the most recent data (e.g., `pos-terminal-001`).
    *   It will feed this real data into the AI pipeline.
    *   The LLM will provide an assessment based on the actual metrics found.

