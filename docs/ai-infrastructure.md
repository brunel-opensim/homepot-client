# AI Infrastructure Implementation Plan

> **Version:** 1.0  
> **Date:** November 27, 2025  
> **Branch:** `feature/ai-infrastructure`  
> **Duration:** 5-8 weeks  
> **Status:** Planning Complete - Ready for Implementation

## Table of Contents

1. [Overview](#overview)
2. [Architecture Design](#architecture-design)
3. [Component Adaptation Strategy](#component-adaptation-strategy)
4. [Implementation Timeline](#implementation-timeline)
5. [Technical Requirements](#technical-requirements)
6. [API Specifications](#api-specifications)
7. [Data Flow](#data-flow)
8. [Testing Strategy](#testing-strategy)
9. [Deployment Plan](#deployment-plan)

---

## Overview

Phase 3 adapts the proven **Personal AI Companion** architecture for HOMEPOT's device monitoring and analysis needs. This approach provides **80% code reuse**, reducing development time from 6-12 months to 5-8 weeks while maintaining full data privacy through local LLM inference.

### Goals

- Implement AI-powered device analysis using local LLMs (Ollama)
- Enable natural language queries about device status and history
- Provide anomaly detection and predictive insights
- Generate automated device health reports
- Maintain 100% data privacy (no external API calls)

### Success Metrics

- Natural language query response time < 2 seconds
- Device pattern matching accuracy > 85%
- Anomaly detection precision > 80%
- System operates fully offline (no internet dependency)
- Memory usage < 8GB RAM for LLM inference

---

## Architecture Design

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      HOMEPOT Frontend                       │ 
│               (React + Dashboard Components)                │ 
└────────────────────┬────────────────────────────────────────┘
                     │ HTTPS/REST
┌────────────────────▼────────────────────────────────────────┐
│                  HOMEPOT Backend API                        │
│              (FastAPI + PostgreSQL + TimescaleDB)           │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           AI Service Module (NEW)                    │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │  AI Router (/api/ai/*)                         │  │   │
│  │  │  - /query    (natural language queries)        │  │   │
│  │  │  - /analyze  (device analysis)                 │  │   │
│  │  │  - /predict  (anomaly prediction)              │  │   │
│  │  │  - /report   (health report generation)        │  │   │
│  │  │  - /status   (Ollama health check)             │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  │                                                      │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │  LLM Service (llm.py)                          │  │   │
│  │  │  - Ollama integration                          │  │   │
│  │  │  - Prompt engineering                          │  │   │
│  │  │  - Response generation                         │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  │                                                      │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │  Device Memory (device_memory.py)              │  │   │
│  │  │  - ChromaDB integration                        │  │   │
│  │  │  - Vector embeddings (SentenceTransformer)     │  │   │
│  │  │  - Semantic pattern matching                   │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  │                                                      │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │  Event Store (event_store.py)                  │  │   │
│  │  │  - Recent device events caching                │  │   │
│  │  │  - PostgreSQL query optimization               │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  │                                                      │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │  Anomaly Detection (anomaly_detection.py)      │  │   │
│  │  │  - Device health scoring                       │  │   │
│  │  │  - Pattern deviation detection                 │  │   │
│  │  │  - Alert severity classification               │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  │                                                      │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │  Analysis Modes (analysis_modes.py)            │  │   │
│  │  │  - Maintenance mode                            │  │   │
│  │  │  - Predictive analysis mode                    │  │   │
│  │  │  - Executive reporting mode                    │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   PostgreSQL + TimescaleDB                  │
│          (Device metrics, events, audit logs)               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  Ollama (Local LLM Service)                 │
│                  http://localhost:11434                     │
│          Models: Llama 3.2 3B, Mistral 7B, Phi 3.5          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│            ChromaDB (Vector Database - Local)               │
│              ./chroma_db (persistent storage)               │
│        Collections: device_patterns, incident_history       │
└─────────────────────────────────────────────────────────────┘
```

### Integration Strategy

**Monolithic Integration (Native Python)**
- AI service as a module within the existing HOMEPOT backend
- Shared database connection pool
- Unified authentication/authorization
- Single Python process deployment
- **Pros:** Simpler deployment, shared context, easier testing, no Docker complexity
- **Cons:** Larger memory footprint, coupled release cycles

**Decision:** We'll implement the AI service as a native Python module within the existing HOMEPOT backend, avoiding Docker containerization to eliminate authentication complications and infrastructure dependencies.

---

## Component Adaptation Strategy

### 1. Chat Memory → Event Store

**Personal AI Companion (`memory_store.py`):**
```python
# Stores conversation history
memory = [
    {"user": "How are you?", "ai": "I'm doing well!"},
    {"user": "What did we discuss?", "ai": "We talked about..."}
]
```

**HOMEPOT Adaptation (`event_store.py`):**
```python
# Stores recent device events for context
recent_events = [
    {"device_id": "sensor_1234", "event": "temperature_spike", 
     "value": 85.2, "timestamp": "2025-11-27T10:30:00"},
    {"device_id": "sensor_1234", "event": "normal_operation", 
     "value": 72.1, "timestamp": "2025-11-27T10:45:00"}
]
```

**Implementation Tasks:**
- Create `event_store.py` with PostgreSQL integration
- Implement caching layer (last 100 events per device)
- Add event summarization for LLM context
- Create cleanup job for old cached events

---

### 2. Vector Memory → Device Pattern Database

**Personal AI Companion (`vector_memory.py`):**
```python
# Stores conversation summaries as embeddings
save_summary("User discussed career goals and work-life balance")
relevant_memories = get_relevant_memories("tell me about my goals")
# Returns semantically similar past conversations
```

**HOMEPOT Adaptation (`device_memory.py`):**
```python
# Stores device incident patterns as embeddings
save_incident_pattern(
    "Sensor 1234 temperature spike to 85°C followed by cooling system activation"
)
similar_incidents = get_similar_patterns("sensor temperature anomaly")
# Returns past incidents with similar patterns
```

**Implementation Tasks:**
- Create `device_memory.py` with ChromaDB integration
- Define embedding model (SentenceTransformer 'all-mpnet-base-v2')
- Implement incident pattern storage
- Create similarity search API
- Add pattern categorization (temperature, connectivity, power, etc.)

---

### 3. Sentiment Analysis → Anomaly Detection

**Personal AI Companion (`sentiment.py`):**
```python
# Analyzes emotional tone
def analyse_sentiment(text: str) -> str:
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity
    if polarity > 0.2: return "positive"
    elif polarity < -0.2: return "negative"
    else: return "neutral"
```

**HOMEPOT Adaptation (`anomaly_detection.py`):**
```python
# Analyzes device health
def analyze_device_health(metrics: dict) -> dict:
    health_score = calculate_health_score(metrics)
    if health_score > 0.8: return {"status": "healthy", "score": health_score}
    elif health_score < 0.4: return {"status": "critical", "score": health_score}
    else: return {"status": "warning", "score": health_score}
```

**Implementation Tasks:**
- Create `anomaly_detection.py`
- Implement health scoring algorithm (based on metrics deviation)
- Add threshold configuration per device type
- Create anomaly logging to PostgreSQL
- Implement severity classification (info, warning, critical)

---

### 4. Personas → Analysis Modes

**Personal AI Companion (`persona.py`):**
```python
personas = {
    "supportive": "You are a thoughtful, supportive companion...",
    "coach": "You are a motivating coach...",
    "therapist": "You are a calm therapist..."
}
```

**HOMEPOT Adaptation (`analysis_modes.py`):**
```python
analysis_modes = {
    "maintenance": "You are a technical systems analyst...",
    "predictive": "You are a predictive maintenance expert...",
    "executive": "You are an executive reporting assistant..."
}
```

**Mode Specifications:**

1. **Maintenance Mode** (Default)
   - Focus: Technical details, troubleshooting steps
   - Audience: System administrators, technicians
   - Output: Detailed metrics, root cause analysis, fix recommendations

2. **Predictive Mode**
   - Focus: Trend analysis, failure prediction
   - Audience: Maintenance planners
   - Output: Risk scores, maintenance schedules, cost estimates

3. **Executive Mode**
   - Focus: High-level summaries, business impact
   - Audience: Management, decision-makers
   - Output: KPIs, uptime stats, cost analysis, strategic recommendations

**Implementation Tasks:**
- Create `analysis_modes.py` with mode definitions
- Implement mode switching API
- Create prompt templates for each mode
- Add mode persistence (per user preference)

---

### 5. Summarization → Device Status Reports

**Personal AI Companion:**
```python
# Summarizes recent conversation
@app.get("/summarise")
def summarise_conversation():
    summary = generate_response(
        "Summarise this conversation: [chat history]"
    )
    return {"summary": summary}
```

**HOMEPOT Adaptation:**
```python
# Generates device health report
@app.get("/api/ai/report/{device_id}")
async def generate_device_report(device_id: str, period: str = "24h"):
    events = get_device_events(device_id, period)
    metrics = get_device_metrics(device_id, period)
    
    report = generate_response(
        f"Generate a health report for device {device_id}. "
        f"Events: {events}. Metrics: {metrics}."
    )
    return {"report": report, "device_id": device_id}
```

**Report Types:**
- **Daily Health Report** - 24h overview (automated, scheduled)
- **Incident Report** - Triggered by critical events
- **Weekly Summary** - 7-day trends and recommendations
- **Custom Analysis** - User-requested time range

**Implementation Tasks:**
- Create report generation endpoints
- Implement scheduled report generation (Celery/APScheduler)
- Add report storage to PostgreSQL
- Create report email notifications
- Build report dashboard UI component

---

### 6. Reflection → Predictive Insights

**Personal AI Companion:**
```python
@app.get("/reflect")
def reflect_on_user():
    # Analyzes past conversations and sentiment trends
    reflection = generate_response(
        "Reflect on the user's recent activity and emotional tone"
    )
    return {"reflection": reflection}
```

**HOMEPOT Adaptation:**
```python
@app.get("/api/ai/insights/{site_id}")
async def generate_site_insights(site_id: str):
    # Analyzes historical patterns and predicts issues
    devices = get_site_devices(site_id)
    patterns = get_historical_patterns(site_id, days=30)
    
    insights = generate_response(
        f"Analyze patterns for site {site_id} and predict potential issues. "
        f"Historical data: {patterns}"
    )
    return {"insights": insights, "site_id": site_id}
```

**Implementation Tasks:**
- Create predictive insights endpoint
- Implement pattern analysis (30-day rolling window)
- Add trend detection algorithms
- Create insight visualization components
- Implement insight action tracking (was action taken? was it effective?)

---

## Implementation Timeline

### Sprint 1: Foundation (Week 1-2)

**Objectives:**
- Set up Ollama and ChromaDB
- Create AI service module structure
- Implement basic LLM integration

**Deliverables:**
- Ollama installed and running (localhost:11434)
- ChromaDB persistent storage configured (./chroma_db)
- `backend/src/homepot/ai/` module created
- `llm.py` - Basic Ollama integration
- `config.yaml` - AI service configuration
- `/api/ai/status` endpoint (health check)
- Unit tests for LLM service

**Technical Setup:**
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull models
ollama pull llama3.2:3b
ollama pull mistral:7b
ollama pull phi3.5:3.8b

# Install Python dependencies
pip install chromadb sentence-transformers textblob pyyaml
```

---

### Sprint 2: Core Components (Week 3-4) - COMPLETED

**Objectives:**
- Implement device memory and event storage
- Create anomaly detection module
- Build analysis modes

**Deliverables:**
- `event_store.py` - Device event caching (Implemented)
- `device_memory.py` - Vector database integration (Implemented)
- `anomaly_detection.py` - Health scoring (Implemented)
- `analysis_modes.py` - Mode definitions (Implemented)
- Database integration for Event Store (Implemented - uses `device_metrics`)
- Integration tests (Implemented)

**Database Schema:**
```sql
-- AI-related tables
CREATE TABLE ai_incident_patterns (
    id SERIAL PRIMARY KEY,
    device_id INTEGER REFERENCES devices(id),
    pattern_description TEXT NOT NULL,
    embedding VECTOR(768),  -- SentenceTransformer output dimension
    created_at TIMESTAMPTZ DEFAULT NOW(),
    severity VARCHAR(20)
);

CREATE TABLE ai_anomaly_logs (
    id SERIAL PRIMARY KEY,
    device_id INTEGER REFERENCES devices(id),
    health_score FLOAT NOT NULL,
    status VARCHAR(20) NOT NULL,  -- healthy, warning, critical
    metrics JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ai_reports (
    id SERIAL PRIMARY KEY,
    report_type VARCHAR(50) NOT NULL,  -- daily, incident, weekly
    site_id INTEGER REFERENCES sites(id),
    device_id INTEGER REFERENCES devices(id),
    content TEXT NOT NULL,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    mode VARCHAR(20) NOT NULL  -- maintenance, predictive, executive
);
```

---

### Sprint 3: API Endpoints (Week 5)

**Objectives:**
- Build natural language query API
- Implement device analysis endpoints
- Create report generation

**Deliverables:**
- `/api/ai/query` - Natural language queries
- `/api/ai/analyze/{device_id}` - Device analysis
- `/api/ai/predict/{device_id}` - Anomaly prediction
- `/api/ai/report/{device_id}` - Report generation
- `/api/ai/insights/{site_id}` - Site-wide insights
- API documentation (OpenAPI/Swagger)
- Integration tests with mocked LLM responses

---

### Sprint 4: Testing & Optimization (Week 6-7)

**Objectives:**
- End-to-end testing
- Performance optimization
- Memory usage optimization

**Deliverables:**
- E2E test suite (pytest)
- Performance benchmarks (query response time)
- Memory profiling and optimization
- LLM response caching
- Error handling and retry logic
- Load testing (concurrent queries)

**Performance Targets:**
- Query response time < 2 seconds (95th percentile)
- Memory usage < 8GB (Ollama + ChromaDB)
- Concurrent queries: 10+ simultaneous users
- Embedding generation < 100ms per document

---

### Sprint 5: Integration & Documentation (Week 8)

**Objectives:**
- Frontend integration
- Documentation
- Deployment preparation

**Deliverables:**
- Frontend AI query component
- Device analysis dashboard widget
- Report viewer component
- Developer documentation
- User guide
- Deployment scripts
- CI/CD pipeline updates

---

## Technical Requirements

### Infrastructure

**Server Requirements:**
- **CPU:** 4+ cores (8+ recommended for better performance)
- **RAM:** 16GB minimum (32GB recommended)
  - HOMEPOT Backend: 2-4GB
  - PostgreSQL: 2-4GB
  - Ollama (LLM): 6-8GB
  - ChromaDB: 1-2GB
  - System: 2GB
- **Storage:** 50GB+ SSD
  - Ollama models: ~15GB (Llama 3.2 3B + Mistral 7B + Phi 3.5)
  - ChromaDB: Growing (estimate 1GB per 100K embeddings)
  - PostgreSQL: Existing + AI tables
- **GPU:** Optional but recommended (NVIDIA GPU with 8GB+ VRAM for faster inference)

**Software Requirements:**
- **OS:** Linux (Ubuntu 22.04+ recommended) or macOS
- **Python:** 3.11+
- **Ollama:** Latest stable release
- **PostgreSQL:** 14+ (existing HOMEPOT database)
- **pip/venv:** For Python package management

### Python Dependencies

Add to `backend/requirements.txt`:
```
# AI Infrastructure
chromadb>=0.4.22
sentence-transformers>=2.2.2
textblob>=0.17.1
pyyaml>=6.0.1
transformers>=4.36.0
torch>=2.1.0
numpy>=1.24.0

# Scheduling (for automated reports)
apscheduler>=3.10.4
```

### Model Selection

**Recommended Models:**

1. **Llama 3.2 3B** (Default)
   - Size: 2GB
   - Speed: Fast (~40 tokens/sec on CPU)
   - Quality: Excellent for technical queries
   - Use case: General device queries, analysis

2. **Mistral 7B**
   - Size: 4.1GB
   - Speed: Moderate (~20 tokens/sec on CPU)
   - Quality: Best accuracy
   - Use case: Complex analysis, executive reports

3. **Phi 3.5 3.8B**
   - Size: 2.2GB
   - Speed: Very fast (~50 tokens/sec on CPU)
   - Quality: Good for simple queries
   - Use case: Quick status checks, simple summaries

**Model Configuration (`backend/src/homepot/ai/config.yaml`):**
```yaml
ai_service:
  default_model: "llama3.2:3b"
  models:
    fast: "phi3.5:3.8b"
    balanced: "llama3.2:3b"
    accurate: "mistral:7b"
  
  ollama:
    url: "http://localhost:11434"
    timeout: 30
    max_retries: 3
  
  chromadb:
    path: "./chroma_db"
    collection_name: "device_patterns"
  
  embedding:
    model: "all-mpnet-base-v2"
    dimension: 768
  
  anomaly_detection:
    health_thresholds:
      healthy: 0.8
      warning: 0.4
      critical: 0.0
    
  caching:
    enabled: true
    ttl: 300  # 5 minutes
    max_size: 1000
```

---

## API Specifications

### 1. Natural Language Query

**Endpoint:** `POST /api/ai/query`

**Request:**
```json
{
  "question": "What's the status of all sensors in Building A?",
  "mode": "maintenance",  // optional: maintenance, predictive, executive
  "model": "llama3.2:3b"  // optional override
}
```

**Response:**
```json
{
  "answer": "Building A has 12 active sensors. 11 are operating normally...",
  "relevant_devices": [
    {"id": "sensor_1234", "name": "Temperature Sensor - Room 101", "status": "normal"},
    {"id": "sensor_5678", "name": "Temperature Sensor - Room 102", "status": "warning"}
  ],
  "mode": "maintenance",
  "response_time_ms": 1847,
  "model_used": "llama3.2:3b"
}
```

---

### 2. Device Analysis

**Endpoint:** `GET /api/ai/analyze/{device_id}`

**Query Parameters:**
- `period`: Time range (1h, 24h, 7d, 30d) - default: 24h
- `mode`: Analysis mode - default: maintenance

**Response:**
```json
{
  "device_id": "sensor_1234",
  "device_name": "Temperature Sensor - Server Room",
  "analysis": {
    "summary": "Device operating normally with occasional temperature spikes...",
    "health_score": 0.82,
    "status": "healthy",
    "anomalies_detected": 2,
    "similar_past_incidents": [
      {
        "date": "2025-11-15",
        "description": "Similar temperature spike pattern",
        "resolution": "Cooling system adjusted",
        "similarity_score": 0.91
      }
    ],
    "recommendations": [
      "Monitor cooling system performance",
      "Schedule preventive maintenance in 2 weeks"
    ]
  },
  "metrics": {
    "avg_temperature": 72.3,
    "max_temperature": 85.2,
    "uptime_percentage": 99.8
  },
  "period": "24h",
  "generated_at": "2025-11-27T14:30:00Z"
}
```

---

### 3. Anomaly Prediction

**Endpoint:** `GET /api/ai/predict/{device_id}`

**Response:**
```json
{
  "device_id": "sensor_1234",
  "predictions": [
    {
      "prediction": "Temperature spike likely in next 6 hours",
      "confidence": 0.78,
      "reasoning": "Historical pattern shows temperature increase during afternoon peak hours",
      "recommended_action": "Verify cooling system operational status",
      "severity": "warning"
    }
  ],
  "risk_score": 0.65,
  "forecast_period": "24h",
  "generated_at": "2025-11-27T14:30:00Z"
}
```

---

### 4. Device Report Generation

**Endpoint:** `GET /api/ai/report/{device_id}`

**Query Parameters:**
- `period`: Time range (24h, 7d, 30d) - default: 24h
- `report_type`: daily, incident, weekly - default: daily
- `mode`: maintenance, predictive, executive - default: maintenance

**Response:**
```json
{
  "report_id": "rpt_20251127_1234",
  "device_id": "sensor_1234",
  "report_type": "daily",
  "mode": "executive",
  "content": {
    "title": "Daily Health Report - Temperature Sensor (Server Room)",
    "summary": "Device maintained 99.8% uptime with 2 minor anomalies detected...",
    "key_metrics": {
      "uptime": "99.8%",
      "avg_temperature": "72.3°C",
      "events_logged": 156,
      "anomalies": 2
    },
    "incidents": [
      {
        "timestamp": "2025-11-27T10:30:00Z",
        "description": "Temperature spike to 85.2°C",
        "resolution": "Automatic cooling adjustment",
        "impact": "None"
      }
    ],
    "recommendations": [
      "Schedule preventive maintenance in 2 weeks",
      "Consider upgrading cooling capacity for peak periods"
    ],
    "cost_impact": "$0 downtime cost, $150 estimated preventive maintenance"
  },
  "generated_at": "2025-11-27T14:30:00Z"
}
```

---

### 5. Site-Wide Insights

**Endpoint:** `GET /api/ai/insights/{site_id}`

**Response:**
```json
{
  "site_id": "site_123",
  "site_name": "Building A",
  "insights": {
    "overall_health": "Good",
    "health_score": 0.87,
    "total_devices": 45,
    "devices_healthy": 42,
    "devices_warning": 2,
    "devices_critical": 1,
    "key_findings": [
      "HVAC system showing signs of reduced efficiency",
      "3 sensors approaching end of warranty period",
      "Network connectivity stable across all devices"
    ],
    "predicted_issues": [
      {
        "description": "HVAC compressor may require maintenance within 30 days",
        "confidence": 0.72,
        "estimated_cost": "$800-$1200"
      }
    ],
    "cost_analysis": {
      "current_month_downtime_cost": "$0",
      "prevented_issues_value": "$2400",
      "recommended_maintenance_budget": "$1500"
    }
  },
  "generated_at": "2025-11-27T14:30:00Z"
}
```

---

### 6. Ollama Health Check

**Endpoint:** `GET /api/ai/status`

**Response:**
```json
{
  "ollama_status": "running",
  "ollama_url": "http://localhost:11434",
  "available_models": [
    {"name": "llama3.2:3b", "size": "2.0GB", "status": "ready"},
    {"name": "mistral:7b", "size": "4.1GB", "status": "ready"},
    {"name": "phi3.5:3.8b", "size": "2.2GB", "status": "ready"}
  ],
  "chromadb_status": "connected",
  "chromadb_collections": 2,
  "total_embeddings": 15847,
  "memory_usage": {
    "ollama": "6.2GB",
    "chromadb": "1.4GB"
  },
  "timestamp": "2025-11-27T14:30:00Z"
}
```

---

## Data Flow

### Natural Language Query Flow

```
1. User Query
2. POST /api/ai/query
3. Parse query + extract intent
4. Fetch relevant device data (PostgreSQL)
5. Retrieve similar past patterns (ChromaDB vector search)
6. Build context prompt:
   - User question
   - Current device data
   - Relevant historical patterns
   - Analysis mode (maintenance/predictive/executive)
7. Send to Ollama LLM
8. Generate response
9. Post-process (extract device references, format)
10. Return structured response to frontend
```

### Anomaly Detection Flow

```
1. Device Metric Update (every 1 minute)
2. Calculate health score:
   - Compare to baseline
   - Check threshold violations
   - Analyze trend deviation
3. If anomaly detected:
4. Log to ai_anomaly_logs table
5. Generate incident description
6. Create embedding (SentenceTransformer)
7. Store in ChromaDB (device_patterns collection)
8. Search for similar past incidents
9. If similar incident found:
   - Retrieve past resolution
   - Generate recommendation
10. Send alert notification
11. Update frontend dashboard
```

### Predictive Analysis Flow

```
1. Scheduled Task (hourly)
2. For each device:
3. Fetch 30-day historical metrics
4. Extract patterns (time-series analysis)
5. Query ChromaDB for similar progression patterns
6. Build prediction prompt:
   - Current metrics
   - Historical trend
   - Similar past failures (if any)
7. Send to Ollama LLM
8. Parse prediction + confidence score
9. If high-risk prediction:
   - Log to database
   - Generate alert
   - Create recommended action
10. Update predictive maintenance schedule
```

---

## Testing Strategy

### Unit Tests

**Coverage Target:** 80%+

**Test Files:**
```
backend/tests/ai/
├── test_llm.py                    # Ollama integration
├── test_device_memory.py          # ChromaDB operations
├── test_event_store.py            # Event caching
├── test_anomaly_detection.py      # Health scoring
├── test_analysis_modes.py         # Mode switching
└── test_api_endpoints.py          # API routes
```

**Key Test Cases:**
- LLM response generation with mocked Ollama
- Embedding generation and vector search
- Health score calculation accuracy
- Event caching and retrieval
- Mode prompt formatting
- Error handling (Ollama down, ChromaDB unavailable)

---

### Integration Tests

**Test Scenarios:**
1. **End-to-End Query Flow**
   - User query → LLM response → structured output
   - Verify device data retrieval
   - Verify vector search integration

2. **Anomaly Detection Pipeline**
   - Simulate metric update → anomaly detection → alert generation
   - Verify pattern storage in ChromaDB
   - Verify similar incident retrieval

3. **Report Generation**
   - Generate daily report → verify content structure
   - Test different modes (maintenance, predictive, executive)
   - Verify report storage

4. **Performance Tests**
   - Query response time < 2s (95th percentile)
   - Concurrent query handling (10+ users)
   - Memory usage monitoring

---

### Load Testing

**Tools:** Locust or Apache JMeter

**Test Scenarios:**
- 10 concurrent users querying devices
- 100 requests/minute sustained load
- Spike test: 50 concurrent queries

**Metrics to Monitor:**
- Response time percentiles (p50, p95, p99)
- Error rate
- Ollama queue length
- Memory usage
- Database connection pool usage

---

## Deployment Plan

### Development Environment

```bash
# 1. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. Pull models
ollama pull llama3.2:3b
ollama pull mistral:7b
ollama pull phi3.5:3.8b

# 3. Start Ollama service (in background)
ollama serve &

# 4. Activate virtual environment
cd /home/mghorbani/workspace/homepot-client
source venv/bin/activate

# 5. Install Python dependencies
cd backend
pip install -r requirements.txt

# 6. Set environment variables
export OLLAMA_URL="http://localhost:11434"
export CHROMADB_PATH="./chroma_db"
export AI_ENABLED="true"

# 7. Run database migrations
alembic upgrade head

# 8. Initialize ChromaDB
python -m homepot.ai.init_chromadb

# 9. Start backend with AI service
uvicorn homepot.main:app --reload --host 0.0.0.0 --port 8000
```

---

### Production Deployment (Native)

**Systemd Service Setup:**

Create `/etc/systemd/system/homepot-ollama.service`:

```ini
[Unit]
Description=Ollama LLM Service for HOMEPOT
After=network.target

[Service]
Type=simple
User=homepot
WorkingDirectory=/opt/homepot
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_MODELS=/opt/homepot/ollama_models"
ExecStart=/usr/local/bin/ollama serve
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/homepot-backend.service`:

```ini
[Unit]
Description=HOMEPOT Backend API with AI Service
After=network.target postgresql.service homepot-ollama.service
Requires=postgresql.service homepot-ollama.service

[Service]
Type=simple
User=homepot
WorkingDirectory=/opt/homepot/backend
Environment="PYTHONPATH=/opt/homepot/backend/src"
Environment="DATABASE_URL=postgresql://homepot_user:password@localhost:5432/homepot_db"
Environment="OLLAMA_URL=http://localhost:11434"
Environment="CHROMADB_PATH=/opt/homepot/chroma_db"
Environment="AI_ENABLED=true"
ExecStart=/opt/homepot/venv/bin/uvicorn homepot.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Deployment Steps:**

```bash
# 1. Create deployment directory structure
sudo mkdir -p /opt/homepot/{backend,ollama_models,chroma_db,logs}
sudo useradd -r -s /bin/false homepot
sudo chown -R homepot:homepot /opt/homepot

# 2. Install Ollama system-wide
curl -fsSL https://ollama.com/install.sh | sh

# 3. Pull required models
sudo -u homepot ollama pull llama3.2:3b
sudo -u homepot ollama pull mistral:7b
sudo -u homepot ollama pull phi3.5:3.8b

# 4. Deploy application code
sudo cp -r /home/mghorbani/workspace/homepot-client/* /opt/homepot/
sudo chown -R homepot:homepot /opt/homepot

# 5. Set up Python virtual environment
cd /opt/homepot
sudo -u homepot python3.11 -m venv venv
sudo -u homepot /opt/homepot/venv/bin/pip install -r backend/requirements.txt

# 6. Run database migrations
sudo -u homepot /opt/homepot/venv/bin/alembic -c /opt/homepot/backend/alembic.ini upgrade head

# 7. Initialize ChromaDB
sudo -u homepot /opt/homepot/venv/bin/python -m homepot.ai.init_chromadb

# 8. Install and start systemd services
sudo systemctl daemon-reload
sudo systemctl enable homepot-ollama homepot-backend
sudo systemctl start homepot-ollama
sleep 5  # Wait for Ollama to initialize
sudo systemctl start homepot-backend

# 9. Verify services
sudo systemctl status homepot-ollama
sudo systemctl status homepot-backend

# 10. Test AI service
curl http://localhost:8000/api/ai/status
```

---

### Monitoring & Maintenance

**Metrics to Monitor:**
- Ollama response time
- ChromaDB query performance
- Memory usage (Ollama + ChromaDB)
- LLM request queue length
- Error rate
- Cache hit rate

**Logging:**
```python
# Add structured logging for AI operations
import logging

logger = logging.getLogger("homepot.ai")

# Log all LLM requests
logger.info(f"LLM query: {query[:100]}...", extra={
    "model": model,
    "user_id": user_id,
    "response_time_ms": response_time
})

# Log anomaly detections
logger.warning(f"Anomaly detected: {device_id}", extra={
    "health_score": health_score,
    "threshold": threshold,
    "severity": severity
})
```

**Maintenance Tasks:**
- Weekly ChromaDB backup (`tar -czf chroma_backup.tar.gz ./chroma_db`)
- Monthly model update check (`ollama list` and `ollama pull <model>`)
- Quarterly embedding regeneration (if embedding model upgraded)
- Daily cleanup of old cached events
- Service health monitoring (`systemctl status homepot-*`)
- Log rotation for Ollama and backend logs

---

## Next Steps

1. **Review this plan** with the development team
2. **Set up infrastructure** (Ollama, ChromaDB)
3. **Create feature branch** (DONE: `feature/ai-infrastructure`)
4. **Sprint 1 kickoff** - Foundation setup
5. **Weekly progress reviews** and plan adjustments

---

## References

- [Personal AI Companion Repository](https://github.com/mzrghorbani/personal-ai-companion)
- [Ollama Documentation](https://github.com/ollama/ollama)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [SentenceTransformers](https://www.sbert.net/)
- [HOMEPOT AI Roadmap](./ai-roadmap.md)

---

**Document Version:** 1.0  
**Last Updated:** November 27, 2025  
**Author:** HOMEPOT Development Team  
**Status:** Ready for Implementation

