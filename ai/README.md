# AI/LLM Services

> **Status:** Foundation Implemented (December 2025)
> **Roadmap:** [AI Integration Roadmap](/docs/ai-roadmap.md)

This directory contains the AI and Machine Learning services for the HOMEPOT Client. The system implements a **Hybrid Analysis Architecture** that combines deterministic rule-based detection with contextual LLM analysis.

## Architecture Overview

We utilize a **Hybrid Analysis** approach to balance speed and intelligence:

1.  **Fast Layer (Rule-Based)**: Immediate detection of known issues (e.g., "CPU > 90%"). This is deterministic, instant, and prevents the LLM from hallucinating safety when metrics are critical.
2.  **Smart Layer (LLM)**: Contextual understanding. It takes the raw data and the rule-based score to explain *why* an anomaly matters and recommends actions.
3.  **Memory Layer (RAG)**: Uses Vector Memory (ChromaDB) to store analysis results. Future queries retrieve these "memories" to identify recurring patterns across devices.

## Key Components

The implementation consists of four core modules:

*   **`api.py` (The Brain)**: A FastAPI application serving as the entry point.
    *   `POST /api/ai/analyze`: Analyzes metrics, scores anomalies, and generates LLM explanations.
    *   `POST /api/ai/query`: Answers natural language questions using RAG (Retrieval-Augmented Generation).
*   **`anomaly_detection.py` (The Reflex)**: Implements rule-based logic to check thresholds (CPU, Memory, Disk, Error Rate) and calculate an `anomaly_score` (0.0 - 1.0).
*   **`llm.py` (The Voice)**: A wrapper for **Ollama** that manages the connection to local models (Llama/Mistral) and constructs context-aware prompts.
*   **`device_memory.py` (The Memory)**: Manages **ChromaDB** interactions for storing and retrieving semantic vector embeddings of device logs.

## Development Guidelines

### Execution Strategy: Local First, Docker Second

**Rule of Development:**
We prioritize **normal execution cycles** (running directly in a local environment) over Docker during development. Docker is treated as an additional deployment feature, not the primary runner for development.

*   **Do not** rely on `docker-compose` for daily coding and testing of the AI service.
*   **Do** run the service using a local Python virtual environment.
*   **Do** ensure tests pass locally using `pytest`.

### Prerequisites
*   Python 3.11+
*   [Ollama](https://ollama.ai/) installed and running locally (`ollama serve`)
*   A model pulled (e.g., `ollama pull llama3.2`)

### Running Locally

1.  **Activate Virtual Environment**:
    ```bash
    source venv/bin/activate
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
