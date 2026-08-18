# HOMEPOT AI Integration Roadmap

> **Version:** 2.0  
> **Date:** July 29, 2026  
> **Status:** Active Development (Phases 1-3 complete, Phase 4 ongoing)  
> **Target:** 2026  
> **Foundation:** Personal AI Companion Architecture

## Executive Summary

This roadmap outlines the strategic path from the current **Complete Website Integration** milestone to a fully operational **AI-Powered Data Analysis Platform** for HOMEPOT Client. The roadmap is divided into 5 major phases spanning approximately 9 months.

**Key Decision:** We will leverage the proven **Personal AI Companion architecture** (FastAPI + Ollama + ChromaDB + RAG) as the foundation, adapting it for device monitoring rather than building from scratch. This approach reduces development time from 6-12 months to 5-8 weeks for the AI infrastructure phase, and cuts costs by 75-90%.

---

## Foundation: Personal AI Companion Architecture

### Overview

Instead of building an LLM from scratch (which would require $100K-$1M, 100+ GPUs, and 12+ months), we will **adapt the proven Personal AI Companion architecture** developed by the HOMEPOT team. This architecture has been successfully implemented and tested with:

- **FastAPI backend** for REST API endpoints
- **Ollama** for local LLM inference (no third-party dependencies)
- **ChromaDB** for vector-based memory storage
- **SentenceTransformer** for embeddings
- **RAG (Retrieval-Augmented Generation)** for context-aware responses
- **Multi-layer memory management** (short-term + long-term)

### Architecture Components

```
Personal AI Companion (Proven)          HOMEPOT AI Service (Adapted)
─────────────────────────────            ────────────────────────────
app/
├── api.py            # FastAPI          → homepot-ai/api.py
├── llm.py            # Ollama           → homepot-ai/llm.py (same)
├── vector_memory.py  # ChromaDB         → homepot-ai/device_memory.py
├── memory_store.py   # JSON storage     → homepot-ai/event_store.py
├── sentiment.py      # TextBlob         → homepot-ai/anomaly_detection.py
├── persona.py        # Chat modes       → homepot-ai/analysis_modes.py
└── config.yaml       # Configuration    → homepot-ai/config.yaml
```

### Key Adaptations for HOMEPOT

| Component | Original Purpose | HOMEPOT Adaptation |
|-----------|------------------|-------------------|
| **Chat Memory** | Conversation history | Device event logs (recent alerts, metrics) |
| **Vector Memory** | Semantic search of conversations | Historical device patterns, past incidents |
| **Sentiment Analysis** | Emotional tone detection | Device health scoring (anomaly detection) |
| **Personas** | Conversation styles | Analysis modes (maintenance, predictive, executive) |
| **Summarization** | Conversation summaries | Device status summaries, incident reports |
| **Reflection** | User insights | Daily/weekly device health reports |
| **Relevant Memories** | Context retrieval | "Find similar failure patterns" |

### Why This Approach?

**Advantages:**
- **80% code reuse** - Core architecture already built and tested
- **Local LLM** - Ollama runs Llama/Mistral locally (no API costs, full data privacy)
- **Vector memory** - ChromaDB implementation proven for RAG
- **5-8 weeks** to adapt vs 6-12 months to build from scratch
- **Fine-tune ready** - Can fine-tune Llama 3.2 on HOMEPOT data later
- **No third-party dependencies** - Everything runs on-premises

**vs Building from Scratch:**
- Custom LLM: $100K-$1M, 100+ GPUs, 12+ months, massive dataset required
- Fine-tuning existing: $5K-$20K, single GPU, 2-4 weeks, HOMEPOT data only

### Data Security & Storage

**PostgreSQL (Current HOMEPOT Setup):**
- **Location:** 100% local Docker volume (`/var/lib/docker/volumes/homepot-client_postgres-data/_data`)
- **Network:** Isolated to Docker network, not exposed to internet
- **Authentication:** Password-protected (`POSTGRES_PASSWORD`)
- **Persistence:** Data survives container restarts and system reboots
- **Backup:** Daily automated backups to local storage

**Security Features:**
1. **At-rest storage** - All data stored locally on your infrastructure
2. **Network isolation** - PostgreSQL only accessible via `localhost:5432`
3. **Authentication** - Username/password required for all connections
4. **Audit logging** - All database changes tracked via `audit_logs` table
5. **Encryption support** - pgcrypto extension available for sensitive fields
6. **Data retention** - 6-month rolling window for AI training, older data archived

**AI Training Data Collection:**
- All training data collected from existing PostgreSQL tables
- No external data sources or cloud uploads
- Export to local JSONL files for fine-tuning
- Complete control over data lifecycle

---

## Implementation Status (July 2026)

### Completed Layers (Phases 1-3)

| Component | Status | Details |
|-----------|--------|---------|
| AI Infrastructure (FastAPI + Ollama + ChromaDB) | ✅ | `ai/api.py`, `ai/llm.py`, `ai/device_memory.py` |
| Context Builder (12 data sources) | ✅ | `ai/context_builder.py` — parallel async DB queries |
| Anomaly Detection (rule-based) | ✅ | `ai/anomaly_detection.py` — 6-factor scoring |
| Validation Gates (A, B, C, D, E) | ✅ | `ai/gates/` — contract, integrity, context readiness, permissions/capabilities, lifecycle integrity |
| Analysis Modes (3 personas) | ✅ | `ai/analysis_modes.py` — maintenance, predictive, executive |
| AI Query Endpoint (`/api/v1/ai/query`) | ✅ | `AIEndpoint.py` with trust envelope |
| Device Memory (ChromaDB RAG) | ✅ | `ai/device_memory.py` — semantic vector storage |
| Failure Predictor (partial) | 🟡 | `ai/failure_predictor.py` — factors 3 & 4 are stubs |
| Predictive Job Scheduler | 🟡 | `ai/job_scheduler.py` — basic, not yet production-tuned |

### Current Data Sources Fed to AI

The Context Builder currently queries **14 of 25** database tables:

`device_metrics` · `health_checks` · `error_logs` · `job_outcomes` · `alerts`  
`device_state_history` · `configuration_history` · `api_request_logs`  
`push_notification_logs` · `user_activities` · `site_operating_schedules`  
`devices` (partial) · `users` (basic) · `audit_logs`

### Gap Analysis: Missing Data Sources

The following tables and fields are **available in the database but not fed to the AI**:

#### Critical (blocks evidence-based recommendations)

| Table | Missing Fields | Why AI Needs It |
|-------|---------------|-----------------|
| `devices` | `device_permissions`, `capabilities` | AI can't know what actions a device supports |
| `devices` | `lifecycle_state`, `health_state`, `is_simulated`, `enrollment_method` | AI can't distinguish emulated vs real, active vs retired |
| `devices` | `config`, `firmware_version`, `os_details`, `peripherals` | AI lacks device configuration context |
| `configuration_history` | `performance_before`, `performance_after`, `was_rolled_back`, `rollback_reason` | AI can't assess config change impact |

#### High (enriches evidence quality)

| Table | Missing Fields | Why AI Needs It |
|-------|---------------|-----------------|
| `enrolment_intents` | All fields (status, method, expiry, consumption) | AI can't trace device enrolment provenance |
| `lifecycle_epochs` | All fields (claimed_at, ended_at, enrolment_method) | AI lacks full device lifecycle timeline |
| `device_lifecycle_events` | All fields (state transitions, reasons, triggers) | AI can't analyze why devices changed state |
| `jobs` (main table) | `priority`, `payload`, `config_url`, `config_version`, `scheduled_at` | AI only sees `job_outcomes`, not the job intent |
| `alerts` | `ai_recommendation`, `ai_confidence`, `resolved_by` | AI can't learn from past AI recommendations |
| `device_metrics` | `transaction_volume`, `active_connections`, `queue_depth`, `extra_metrics` | Missing financial and operational dimensions |

#### Medium (adds operational context)

| Table | Missing Fields | Why AI Needs It |
|-------|---------------|-----------------|
| `device_assignments` | All fields (assignment_reason, assigned_at, unassigned_at) | AI can't trace device-to-site assignment history |
| `device_credentials` | All fields (key_hash, rotated_at, revoked_at, is_active) | AI can't assess device authentication health |
| `tenants` | `settings`, memberships | AI lacks organization hierarchy awareness |
| `tenant_memberships`, `site_memberships` | `role` | AI can't reason about user permissions |
| `audit_logs` | `old_values`, `new_values`, `event_metadata`, `ip_address` | AI lacks full audit trail detail |
| `site_operating_schedules` | `is_closed`, `special_considerations` | Has data, but underused for scheduling logic |

### Gap Analysis: Validation Gates

Current gates only validate `DeviceMetrics` + `HealthCheck` schemas and timeliness:

| Missing Gate | What It Should Validate | Priority |
|-------------|------------------------|----------|
| **Gate D: Permission & Capability** | Device `device_permissions`/`capabilities` match requested AI actions | High |
| **Gate E: Lifecycle Integrity** | Device lifecycle state, credential health, enrolment status | High |
| **Gate F: Context Coverage** | All required context blocks from the gap tables above are present | Medium |
| **Gate G: Rollback Awareness** | Config rollback state, recent reversions, stability indicators | Medium |

---

## Layered Development Plan (Phase 4 — Ongoing)

### Layer 1: Core Device Intelligence (Est. 2-3 sprints)

Integrate the most critical missing device fields into AI context:

- [ ] Add `device_permissions`/`capabilities` to `context_builder.get_metadata_context()`
- [ ] Add `lifecycle_state`, `health_state`, `is_simulated`, `enrollment_method` to device context
- [ ] Add `config`, `firmware_version`, `os_details`, `peripherals` to device context
- [ ] Add `performance_before`/`after`, `was_rolled_back` from `configuration_history`
- [ ] Add `transaction_volume`, `active_connections`, `queue_depth` from `device_metrics`
- [ ] Update `AIAnalyticsService` to surface these new fields in insights
- [ ] Create **Gate D: Permission & Capability Gate** — validates device capabilities
- [ ] Create **Gate E: Lifecycle Integrity Gate** — validates lifecycle and credential health

### Layer 2: Enrolment & Provenance (Est. 1-2 sprints)

Add device enrolment and lifecycle tracking to AI context:

- [ ] Add `EnrolmentIntent` context to `context_builder` (status, method, expiry, consumption)
- [ ] Add `LifecycleEpoch` context (claimed_at, ended_at, enrolment_method)
- [ ] Add `DeviceLifecycleEvent` context (state transitions with reasons and triggers)
- [ ] Add `DeviceAssignment` context (assignment history, reasons)
- [ ] Add `DeviceCredential` context (key rotation status, revocation state)

### Layer 3: Full Job & Configuration Intelligence (Est. 1-2 sprints)

Expand AI's understanding of jobs and config beyond outcomes:

- [ ] Add full `Job` records to context (priority, payload, config_url, version, scheduling)
- [ ] Add `alert.ai_recommendation`, `alert.ai_confidence`, `alert.resolved_by` to alert context
- [ ] Add `audit_log.old_values`, `audit_log.new_values`, `audit_log.event_metadata` to audit context
- [ ] Add `site_operating_schedules.is_closed`, `special_considerations` for smarter scheduling

### Layer 4: Organization & Access Control (Est. 1 sprint)

Add tenant and membership context for multi-tenant awareness:

- [ ] Add `Tenant` context to query path (settings, member count, active status)
- [ ] Add `TenantMembership`/`SiteMembership` roles to user context
- [ ] Surface user permission levels to gate/trust decisions

### Layer 5: Gate Chain Completion (Est. 2-3 sprints)

Complete the validation gate architecture:

- [ ] **Gate D** — Permission & Capability gate (see Layer 1)
- [ ] **Gate E** — Lifecycle Integrity gate (see Layer 1)
- [ ] **Gate F** — Context Coverage gate — verifies all expected context blocks are present
- [ ] **Gate G** — Rollback Awareness gate — checks config stability before recommendations
- [ ] Wire all new gates into `build_default_envelope()` in `ai/gates/envelope.py`
- [ ] Update trust mode documentation and dashboard trust banner

### Layer 6: Predictor & Scheduler Backfill (Est. 1-2 sprints)

Complete the stub predictors left from Phase 3:

- [ ] `FailurePredictor.identify_at_risk_devices()` — implement full device scan
- [ ] `FailurePredictor.predict_device_failure()` — implement factor 3 (state stability) and factor 4 (health trend)
- [ ] `PredictiveJobScheduler` — production tuning and validation against real data
- [ ] Add TimescaleDB continuous aggregate queries for long-window trend analysis

### Layer 7: Testing & Calibration (Est. 1 sprint per layer)

Each layer above must include:

- [ ] Unit tests for new context builder methods (`test_ai_context_builder.py`)
- [ ] Unit tests for new gates (`test_validation_gates.py`)
- [ ] Integration tests for the full query pipeline with new data
- [ ] Gate trust-ceiling calibration against real deployment data

---

## Dependency Graph

```
Layer 1 (Core Device Intel)
    │
    ├── Layer 2 (Enrolment & Provenance) — depends on Layer 1 patterns
    ├── Layer 3 (Job & Config Intel)     — independent of Layer 2
    │
    ├── Layer 5 (Gate Chain)             — depends on Layer 1 data
    │                                        (Gates D/E need device fields)
    │
    ├── Layer 4 (Org & Access Control)   — can run in parallel with 2/3
    │
    ├── Layer 6 (Predictor Backfill)     — depends on Layer 1 + 3 metrics
    │
    └── Layer 7 (Testing & Calibration)  — runs after each layer
```

**Recommended execution order:** Layer 1 → Layer 5 (gates D+E) → Layer 2 → Layer 3 → Layer 6 → Layer 4

---

*This roadmap is a living document and will be updated as the project progresses and requirements evolve.*
