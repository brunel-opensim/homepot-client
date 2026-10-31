# AI Service API Reference

> **Status:** Experimental
> **Base URL:** `/api/v1/ai`

The AI Service provides intelligent analysis and natural-language querying for the HOMEPOT Client. It runs against a local LLM (Ollama) by default, or an external provider (OpenAI, Anthropic) when selected — see [LLM Providers](ai-llm-providers.md). Long-term memory uses Vector Memory (ChromaDB) for data privacy, and every chat answer is wrapped in a [trust & validation-gate envelope](ai-validation-gates.md) so confidence is always surfaced.

---

## 1. Natural Language Query

Ask questions about the system, specific devices, or historical incidents. The system uses **RAG** and **Context Injection**, and returns the answer together with a **trust envelope** describing how much confidence to place in it.

### Endpoint
`POST /api/v1/ai/query`

### Request Body
```json
{
  "query": "Why is device DEVICE-8TKX-MVVG-U4EH failing?",
  "device_id": "DEVICE-8TKX-MVVG-U4EH",
  "role": "Admin",
  "history": [
    { "role": "user", "content": "Is the system healthy?" },
    { "role": "assistant", "content": "Most devices are online, but one is reporting errors." }
  ]
}
```

**Parameters:**
* `query` (string, required): the question to ask.
* `context` (string, optional): extra context appended verbatim to the prompt.
* `device_id` (string, optional): if provided, fetches device-specific context and runs the per-device gates (D, E).
* `role` (string, optional): the requester's role, injected into the prompt.
* `history` (list, optional): prior `{role, content}` messages for short-term memory.

### Response
```json
{
  "response": "Based on recent logs, DEVICE-8TKX-MVVG-U4EH is experiencing high CPU usage (92.5%) and intermittent network latency. This pattern matches a known issue with the v2.4.1 firmware update. I recommend rolling back to v2.4.0.",
  "timestamp": "2026-07-17T15:13:16.418238",
  "trust": {
    "trust_mode": "grounded",
    "trust_mode_label": "Grounded LLM Interface",
    "trust_score": 1.0,
    "actionable": true,
    "passed_gates": ["A", "B", "C", "D", "E", "C"],
    "failed_gate": null,
    "summary": "Passed all gates (A, B, C, D, E, C) — Grounded LLM Interface",
    "gates": [
      {
        "gate_id": "A",
        "name": "Contract and Infrastructure",
        "status": "pass",
        "score": 1.0,
        "checks": [ { "check_id": "A.db_readiness", "passed": true, "message": "...", "evidence": [] } ]
      }
    ]
  }
}
```

The `trust` object is the `EnvelopeResult` from `ai/gates/envelope.py`. See [Trust & Validation Gates](ai-validation-gates.md) for the mode reference and how trust is surfaced in the Dashboard.

---

## 2. Anomaly Scan

Return the current rule-based anomaly scan across active devices.

### Endpoint
`GET /api/v1/ai/anomalies`

### Response
```json
{
  "anomalies": [
    {
      "device_id": "DEVICE-8TKX-MVVG-U4EH",
      "device_name": "Web Dashboard 1-4",
      "score": 0.82,
      "severity": "high",
      "reason": "CPU 92.5% and memory 85% sustained"
    }
  ],
  "status": "success"
}
```

---

## 3. Insights

Per-scope analytics summaries.

### Endpoint
`GET /api/v1/ai/insights/device/{device_id}`
`GET /api/v1/ai/insights/site/{site_id}`
`GET /api/v1/ai/insights/push-notifications`

### Example (site)
`GET /api/v1/ai/insights/site/SITE-6725-FUJH`

```json
{
  "site_id": "SITE-6725-FUJH",
  "insights": {
    "performance_trend": "...",
    "configuration_impact": "...",
    "job_outcomes": "..."
  }
}
```

---

## 4. Predictions

Failure-risk assessments for devices.

### Endpoints
`GET /api/v1/ai/predictions/failure/{device_id}`
`GET /api/v1/ai/predictions/at-risk-devices`

### Example
`GET /api/v1/ai/predictions/failure/DEVICE-8TKX-MVVG-U4EH`

```json
{
  "device_id": "DEVICE-8TKX-MVVG-U4EH",
  "risk_score": 0.4,
  "risk_level": "medium",
  "factors": { "resource_trend": 0.35, "error_trend": 0.3 },
  "prediction_window_hours": 24,
  "recommendation": "..."
}
```

---

## 5. Recommendations

Job-scheduling recommendations.

### Endpoints
`POST /api/v1/ai/recommendations/schedule-job`
`POST /api/v1/ai/recommendations/success-probability`
`GET /api/v1/ai/recommendations/optimal-windows/{site_id}`

### Example
`POST /api/v1/ai/recommendations/schedule-job`

```json
{ "site_id": "SITE-6725-FUJH", "job_priority": "medium", "earliest_start": "2026-07-17T20:00:00Z" }
```

---

## 6. Health Forecast

`GET /api/v1/ai/health-forecast`

Aggregate operational-health forecast across all active devices.

---

## 7. Status

`GET /api/v1/ai/status`

Static capability/status report for the AI service.

---

## 8. LLM Provider

Inspect and switch the active LLM provider. See
[LLM Providers](ai-llm-providers.md) for the full guide.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/ai/provider` | Any authenticated user | Current provider, model, health, options |
| `PUT` | `/api/v1/ai/provider?provider=<name>` | **Admin** | Switch the active provider |
| `PUT` | `/api/v1/ai/provider/key?provider=<name>&api_key=<key>` | **Admin** | Store an API key for a provider |

Valid provider names: `ollama`, `openai`, `anthropic`.

### Example — inspect

```http
GET /api/v1/ai/provider
```

```json
{
  "status": "success",
  "data": {
    "current": "openai",
    "available": [
      {"name": "ollama", "active": false},
      {"name": "openai", "active": true, "has_api_key": true},
      {"name": "anthropic", "active": false, "has_api_key": true}
    ],
    "healthy": true,
    "model": "gpt-4o-mini"
  }
}
```

### Example — switch

```http
PUT /api/v1/ai/provider?provider=anthropic
```

Switching resets the AI service singleton, so the new provider takes effect
immediately. A non-admin caller receives `403 Admin role required`.

### Example — store a key

```http
PUT /api/v1/ai/provider/key?provider=openai&api_key=sk-...
```

!!! warning
    Keys stored through this endpoint are written in plaintext to
    `ai/provider.json`. Prefer `.env.local` for managed deployments. See
    [API keys and secret management](ai-llm-providers.md#api-keys-and-secret-management).

---

## Authentication

All `/api/v1/ai/*` endpoints require an authenticated user (`require_user()`,
enforced at the router). Provider switching and key storage additionally require
the **Admin** role; a non-admin caller receives `403 Admin role required`.
