# AI/LLM Services

> **Status:** Foundation Implemented (December 2025)
> **Roadmap:** [AI Integration Roadmap](/docs/ai-roadmap.md)
> **Documentation:** [Context Builder](/docs/ai-context-builder.md)

This directory contains the AI and Machine Learning services for the HOMEPOT Client. The system implements a **Hybrid Analysis Architecture** that combines deterministic rule-based detection with contextual LLM analysis.

## Context Builder

The **Context Builder** (`ai/context_builder.py`) exposes many context sources for "situational awareness" to the LLM. Note that this README describes the standalone/legacy architecture; the **live integrated** AI surface (`/api/v1/ai/query` in `AIEndpoint.py`) injects a focused, real-time subset (current site/device status, push stats, active alerts, recent jobs) rather than every table on every request — see [AI Implementation & Architecture](../docs/ai-implementation.md) and the [API Reference](../docs/ai-api-reference.md).

Available context sources include:

*   **Tenants:** Multi-tenancy organisations and their active status.
*   **Tenant Memberships:** User-role assignments within tenants.
*   **Sites:** Site metadata and operating schedules.
*   **Site Memberships:** User-role assignments within sites.
*   **Devices:** Full device metadata (firmware, IP, lifecycle state, permissions, capabilities, config, peripherals).
*   **Device Metrics:** CPU, memory, disk, network latency, transaction counts, error rates.
*   **Device State History:** Connectivity and state transitions (Online/Offline).
*   **Device Assignments:** Historical and current site assignments per device.
*   **Device Lifecycle Events:** Lifecycle state transitions (pending → active → retired).
*   **Device Credentials:** Active/revoked API credential versions per device.
*   **Device Commands:** Pending and executed commands (restart, update_config, ping).
*   **Jobs:** Device management job queue (status, priority, targeting).
*   **Job Outcomes:** Failed job execution results and error messages.
*   **Health Checks:** Recent connectivity and response-time checks per device.
*   **Error Logs:** System errors, stack traces, and severity classifications.
*   **Configuration History:** Device and system parameter changes with rollback tracking.
*   **Audit Logs:** User actions and system events.
*   **API Request Logs:** API call history with status codes and response times.
*   **User Activities:** Page views and interaction events per user.
*   **Push Notification Logs:** Delivery status across FCM, APNs, WNS, Web Push providers.
*   **Alerts:** Active system alerts with severity and device association.
*   **Enrolment Intents:** Pending/completed/expired device enrolment requests.
*   **Lifecycle Epochs:** Claim-to-retirement periods per device.
*   **User Profiles:** User metadata including role and active status.

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

## Switching LLM Models Locally

The HOMEPOT AI talks to a local **Ollama** instance (`ai/llm.py`). Which model you can run is bounded by the hardware the Ollama server is running on. This section documents how we assess whether a candidate model fits, the tests we ran, and the metrics that matter.

### How model choice is configured

The active model is read from `ai/config.yaml`:

```yaml
llm:
  model: "llama3.2"
  base_url: "http://localhost:11434"
  temperature: 0.7
  context_window: 4096
```

`./scripts/setup-ollama.sh` reads the model name from this file and pulls it if it is not already present.

### How to switch models

A model switch is a three-step procedure; the backend reload is easy to miss:

1. **Pull the model** so Ollama can serve it:
   ```bash
   ollama pull <model>
   ```
2. **Edit `ai/config.yaml`** and set `llm.model` to the new name.
3. **Reload the backend.** This is required and non-obvious: the backend runs under
   `uvicorn --reload`, but uvicorn's default reload filter watches **`*.py` files
   only**, so a `.yaml` change does **not** restart it. The `LLMService` singleton
   is initialised once per process and keeps serving the old model until the
   process restarts. Either touch any `.py` under `backend/src` or `ai/` to
   trigger a reload, or restart uvicorn yourself.

No `ollama` restart is needed for a switch: Ollama loads any pulled model on
demand. (If the Ollama runner ever wedges — e.g. after a client is killed
mid-request — `sudo systemctl restart ollama` recovers it, but that is a
recovery action, not part of a normal model switch.)

To verify the switch took effect, run the live endpoint and compare latency;
each AI request generates far fewer tokens on the new model, so the timing and
the answer should change.

### Why GPU memory is the binding constraint

To run **entirely on the GPU** (no CPU spill), the model weights *plus* the KV cache (which scales with the context window) must fit in GPU VRAM:

```
VRAM needed ≈ weights (at your quantization) + KV cache + ~100-200 MiB overhead
KV cache (fp16) ≈ 2 × layers × kv_heads × head_dim × context_window × 2 bytes
```

- **Weights** are the model file size at a given quantization (e.g. `qwen3:4b` ≈ 2.5 GB at Q4_K_M).
- **KV cache** is per-token and grows linearly with `context_window`; reducing the context window shrinks it.
- **Overhead** is the CUDA context and compute buffers (typically ~100-200 MiB).
- If the total exceeds VRAM, Ollama offloads layers to **CPU RAM/swap** — this is generally undesirable for interactive use because latency jumps and the CPU (an i7-9850H in our test box) is far slower at inference.

When only a subset fits on the GPU, the remainder spills to CPU; Ollama does not spill "cleanly" per task. Deliberately running tiny models for low-resource tasks (e.g. simple classification) on CPU is a separate, opt-in design choice, not the default.

### What to check on your machine

Run these before choosing a model:

```bash
nvidia-smi --query-gpu=index,name,memory.total,memory.used,memory.free --format=csv,noheader
lscpu | grep -E "Model name|^CPU\(s\)"
free -h
```

Note: `nvidia-smi` only lists **CUDA-capable** GPUs. On machines with an integrated GPU (e.g. Intel UHD 630) alongside a discrete NVIDIA card, Windows Task Manager may number them differently than CUDA does. **Use the CUDA index from `nvidia-smi`** for Ollama; the integrated GPU cannot run the LLM.

### Measured findings (reference machine)

Test box: **Quadro P620 (4 GiB VRAM)**, Intel i7-9850H, 23 GiB RAM.

| Model | File size | Measured VRAM used | Headroom on 4 GiB |
|---|---|---|---|
| llama3.2 (3B, Q4_K_M) | 2.0 GB | ~2448 MiB | ~1.5 GiB |
| qwen3:4b (4B, Q4_K_M) | 2.5 GB | ~2465 MiB | ~1.5 GiB |

Estimated fit for larger candidates at a 4096-token context:

| Model | Quant | Weights | Est. VRAM | Fits 4 GiB? |
|---|---|---|---|---|
| qwen3:8b | Q4_K_M | ~4.9 GB | ~5.4 GiB | No - spills to CPU |
| qwen3:8b | Q3_K_M | ~3.5 GB | ~3.9 GiB | Borderline |
| llama3.1:8b | Q3_K_M | ~3.7 GB | ~4.4 GiB | No - spills to CPU |
| gemma3:12b | Q4_K_M | ~7.9 GB | ~8.7 GiB | No |
| qwen3:14b | Q4_K_M | ~8.9 GB | ~9.6 GiB | No |

**Conclusion for this class of machine:** a **4 GiB card tops out around a 4B-parameter model at Q4**. To go 8B+ with quality you need ~12-16 GiB VRAM; on 4 GiB the only options are a heavy quantization (poor quality) or accepting CPU offload.

### Measured inference latency (reference machine)

Both models fit on the P620, but generation speed differs sharply. Measured with `ai/utils/bench_llm.py` (server-reported timings, median of 3, unique prompt per trial to defeat the prompt cache; 200-token output cap):

| Metric | llama3.2 (3B) | qwen3:4b (4B) |
|---|---|---|
| Decode, short prompt | 22.0 t/s | 7.6 t/s |
| Decode, long context (2050 tok) | 12.0 t/s | 5.6 t/s |
| Prefill, long context | 230 t/s | 153 t/s |
| End-to-end HOMEPOT `/ai/query` | **~57 s** | **~474 s (~8 min)** |

Two things make qwen3:4b dramatically slower here:

1. **Bigger model on a weak GPU**: decode is ~2x slower than llama3.2.
2. **Thinking mode is always on and cannot be disabled**: `think: false`
   (as an option or top-level) is silently ignored by Ollama 0.32.5, and qwen3
   still emits 1k+ reasoning tokens per response. A `num_predict` cap below the
   thinking length returns an **empty** answer. So each request pays 60-80% of
   its token budget on hidden reasoning before producing any text.

**Takeaway:** for an interactive query workload on a 4 GiB card, llama3.2 is the
pragmatic default; qwen3:4b is a better-quality alternative only where answers
are produced asynchronously and an 8-minute wait is acceptable.

### How to verify a switch (the tests we ran)

1. **Pull and load the candidate:**
   ```bash
   ollama pull <model>
   ollama run <model> "hello"
   ```
2. **Confirm it stays on the GPU** - load the model, then check VRAM while idle and after a run:
   ```bash
   nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader
   ```
   A large jump in CPU/RAM use (or a large `free` drop) indicates CPU spill.
3. **Time a real inference** (wall-clock for a single prompt) and compare with the current model.
4. **Run the HOMEPOT AI tests** to confirm the endpoint still works:
   ```bash
   pytest backend/tests/test_ai_service.py
   ```
5. **Exercise the live endpoint** (requires a running backend + Ollama):
   ```bash
   curl -X POST http://localhost:8000/api/v1/ai/query -H "Content-Type: application/json" -d '{"query":"What devices are healthy?"}'
   ```

### Metrics that matter (local vs. server)

| Metric | Local workstation | Server |
|---|---|---|
| GPU VRAM (total / used / free) | Decide which model fits on-GPU | Primary constraint per model+quant |
| GPU utilization (`nvidia-smi`) | Confirm GPU is doing the work, not CPU | Per-replica sizing; watch for oversubscription |
| CPU cores / RAM | CPU fallback path quality; system overhead | Spill budget; other services running alongside |
| Context window (`num_ctx` / `context_window`) | Directly trades against VRAM via KV cache | Matches expected prompt sizes + headroom |
| Latency (time-to-first-token, tokens/sec) | Interactive feel; compare across models | Service-level objective / capacity planning |
| Model file size | Download/disk cost | Artifact storage, image size, cold-start time |
| Quantization level (Q2-Q8) | Quality vs. fit trade-off | Same, plus consistency across replicas |

The single most important number is **total VRAM required vs. available**. If the model+KV cache fits with headroom, GPU-only inference is achievable; if not, you either shrink the model/quant/context or move to hardware with more VRAM.

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

