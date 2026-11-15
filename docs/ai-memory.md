# AI Memory (Short-Term & Long-Term)

The AI has two kinds of memory. This page describes how they work, how they are
scoped for multi-tenant safety, and how to configure them.

| | Short-term memory | Long-term memory |
|---|---|---|
| **What** | Recent conversation turns | Past answers / outcomes / incidents |
| **Where** | Supplied by the client per request | ChromaDB vector store (on disk) |
| **Lifetime** | One request | Until pruned (default 90 days) |
| **Recall** | Last 4 messages (2 turns), verbatim | Semantic similarity + scope filter |
| **Code** | `AIEndpoint.query_ai` | `ai/device_memory.py` |

!!! note "Provider-independent"
    Memory is assembled in the backend and injected into the prompt *before* the
    LLM is called. It behaves identically for Ollama, OpenAI and Anthropic: the
    long-term store is embedded locally with ChromaDB's default
    `all-MiniLM-L6-v2` model, so switching the answer provider does not change
    recall quality. See [LLM Providers](ai-llm-providers.md#memory-behaviour-provider-independent).

---

## Short-term memory (conversation)

The client sends the conversation `history` in the request body. The endpoint
keeps the **last 4 messages** (two turns), sanitizes them (prompt-injection
scrubbing), and injects them as a `[CONVERSATION HISTORY]` block. Older
messages are replaced by an explicit
`[EARLIER CONVERSATION: N prior turn(s) omitted …]` marker, so the model knows
the transcript is bounded:

```python
# backend/src/homepot/app/api/API_v1/Endpoints/AIEndpoint.py
_recent, _older = _select_history(
    effective_history, _max_hist_msgs, _max_hist_tokens
)
short_term_context = "\n".join(_parts)  # history + omitted/summary marker
```

The limit comes from `llm.history.max_messages` in `ai/config.yaml` (currently
4). The full transcript is still stored server-side in `investigation_messages`;
only the prompt selection is bounded.

Short-term memory is **stateless on the server for API clients**: the client is
responsible for sending history back. When a `session_id` is supplied, the
endpoint loads the prior turns from the backend-held transcript instead.

!!! note "Dashboard coverage"
    The API accepts `history` and the Dashboard's `AskAIWidget` now sends the
    prior turns (bounded by the backend's `llm.history.max_messages`, currently
    the last 4 messages), so short-term memory works in both the compact
    assistant and the AI workspace. The compact view shows only the latest
    answer; the workspace renders the full thread. Long-term memory works
    regardless.

### Multi-turn behaviour

A follow-up question ("What has already been tried?") reuses the conversation
history so the technician does not need to restate the device or context. The
backend:

1. Loads the prior turns (client-supplied or from the backend-held transcript
   when a `session_id` is provided).
2. Applies a bounded context policy (`llm.history.max_messages`,
   `max_tokens`, `summarise_older`) so the prompt stays within the model's
   window.
3. Carries forward a `device_id` inferred from the history when the follow-up
   does not specify one, so device-specific context is retained.
4. Re-runs validation gates on **live** data — historical conversation content
   never overrides current device status or authorisation.

### Limitations

- **Ollama comprehension:** `llama3.2` (4B, CPU) may not reliably use prior
  context for follow-ups — same comprehension limitation as complex fleet
  queries. Use cloud providers for accurate multi-turn investigations.
- **Context window:** with `num_ctx: 8192`, 5 turns of history + full context
  + system prompt leave limited headroom for output. Keep conversations short
  or raise `context_window` (RAM permitting).
- **Device inference:** device context is carried forward by regex-matching
  `DEVICE-XXXX-XXXX-XXXX` in prior turns. If the first question did not
  mention a device ID, follow-ups are fleet-wide.

!!! note "Cost"
    On the CPU-only host every history token is re-evaluated on each turn
    (~22 tok/s). Keep client history short; it is capped at 5 turns but not by
    token budget.

---

## Long-term memory (vector recall)

Long-term memory is a persistent **ChromaDB** collection named `device_logs`
(path `ai/data/chroma_db`). Each entry is a small text record plus metadata,
stored as an embedding (ChromaDB's default `all-MiniLM-L6-v2`, run locally) so
the AI can recall entries that are *semantically similar* to the current
question. Embedding is provider-independent: it is the same store and embedder
for Ollama, OpenAI and Anthropic.

!!! note "Not the documentation index"
    `device_logs` is a **different** store from the documentation index
    (`data/docs_chroma`, collection `project_docs`) that grounds the knowledge
    path. That index is documentation retrieval, not memory — see
    [AI Doc Retrieval](ai-doc-retrieval.md).

!!! note "Knowledge answers are docs-only"
    Long-term memory is used by the device-backed **diagnostic** path and the
    agent's on-demand **incident search**, but never by the **knowledge**
    (how-to/definition) path. A knowledge answer is grounded in documentation
    alone: it neither recalls past memories nor writes its answer to the store.
    The store holds the model's own past output, and feeding it back on a path
    with no live ground truth would let a wrong answer reinforce itself with
    nothing to correct it. See [AI Query Routing](ai-query-routing.md).

### Writers

Three code paths write to the store:

| `source` | Writer | Record |
|---|---|---|
| `ai_query` | `AIEndpoint.py` — after each diagnostic query | `Q: <question>\nA: <first ~500 chars of the answer>` |
| `ai_outcome` | `verifier.py::_record_outcome` — when a plan reaches terminal | `AI action plan <id> (<tier>): status=…, verified=…, rolled_back=…, actions=[…]` |
| *(none)* | `ai/api.py` `analyze` endpoint (legacy) | `Analysis for <device>: …` + anomaly score |

**`ai_query` — past answers.** After a successful diagnostic query the endpoint
stores a compact record (`write_on_query: true`); knowledge answers are never
stored. A query the technician cancels (Stop/Esc) is not stored either — see
[Cancelling a query](ai-concurrency.md#cancelling-a-query-stop-esc).

**Proposal answers are not stored.** When a query produces an AI action
proposal, its answer ("recorded, pending approval") is *transient state*, not
durable knowledge. Writing it would let a later query recall "I already
proposed X" and skip proposing again — the memory-pollution regression observed
on Brunel Device 001, where a second AI soak run degraded because the first
run's proposal answers were recalled. The durable record is the plan outcome
(`ai_outcome`) written by the verifier, so nothing is lost by skipping the
proposal answer. See `_should_persist_answer_to_memory` in
`backend/src/homepot/app/api/API_v1/Endpoints/AIEndpoint.py`.

**`ai_outcome` — plan outcomes.** When an AI action plan reaches a terminal
state the verifier records the outcome (verified / failed / rolled back) as the
"what actually happened" record. This is the trustworthy half of the store,
distinct from the model's own past answers.

**Legacy analysis.** The standalone `ai/api.py` service (a separate FastAPI app,
not mounted in the main backend) writes one record per anomaly analysis with
`device_id` + `anomaly_score` metadata and **no** `source` tag. In the current
deployment this path is dormant.

### Readers

Three code paths read the store:

| Path | When | What |
|---|---|---|
| Automatic recall | `AIEndpoint.py` — **every** diagnostic query | `query_similar(query, scope)` → a `[RELEVANT MEMORIES]` block injected into the prompt |
| Incident search | `ai/tools.py::search_similar_incidents` — **on demand** | past incidents/resolutions, only when the agent calls the tool |
| Legacy recall | `ai/api.py` — every query | `query_similar(query)` → `long_term_context` |

The **automatic recall** is the one to watch: it feeds the model its own prior
assertions back as ground truth on every query, which is both the echo-chamber
risk (a stale "device is healthy" recalled against live data) and the cause of
the pollution bug above. The **incident search** is the high-signal, on-demand
path.

### Metadata

A stored record carries:

| Field | Meaning |
|---|---|
| `user_id` | Author (carried from the authenticated user) |
| `site_id` | Site the memory belongs to (when unambiguous) |
| `device_id` | Device, for device-focused queries |
| `created_at` | Unix timestamp, used for retention |
| `source` | `ai_query` or `ai_outcome` (legacy analyses carry none) |
| `trust_score`, `is_actionable` | Validation-gate outcome (`ai_query` records only) |

The store is written with `upsert` and a content-derived id, so re-storing the
same record is a no-op (deduplicated).

### Scoping (multi-tenant safety)

`MemoryScope` (`ai/device_memory.py`) mirrors the RBAC model. Both the **write**
and the **recall** are scoped:

- **Admins** (`current_user["role"] == "Admin"`, `homepot.app.auth_utils`)
  are **unrestricted** — they recall across all memories.
- **Device-focused queries** (`device_id` set) recall only memories about that
  device.
- **Otherwise** a user recalls memories in **their sites** (`get_accessible_site_ids`)
  **or** written by themselves. There is no cross-tenant bleed.

```python
scope = MemoryScope(user_id=..., site_ids=[...], device_id=..., is_admin=...)
memory.query_similar(query, scope=scope)   # builds the ChromaDB `where` filter
memory.remember(text, scope=scope)         # tags the stored metadata
```

### Relevance threshold

Recall filters by vector distance. Memories farther than `max_distance` are not
injected, so an off-topic question does not pull in irrelevant records (which
would waste CPU tokens and risk hallucination). Set `max_distance: null` to
disable the cutoff and always return the top `n_results`.

!!! warning "The metric matters"
    `max_distance` is only meaningful for the distance metric the collection was
    built with. `distance_metric` is applied when the collection is first
    created; changing it later has no effect until the collection is recreated
    (delete the `chroma_path` directory). The store logs a warning if the
    collection's space differs from the configured one.

### Retention (TTL)

Every entry carries `created_at`. On startup (and via
`DeviceMemory.prune_older_than()`) entries older than `retention_days` are
deleted. Set `retention_days: null` to keep memories forever.

---

## Configuration

All in `ai/config.yaml`:

```yaml
memory:
  chroma_path: "data/chroma_db"
  collection_name: "device_logs"
  embedding_model: "all-MiniLM-L6-v2"   # informational; ChromaDB's default embedder
  distance_metric: "cosine"             # "cosine" or "l2"
  n_results: 3                          # max memories recalled per query
  max_distance: 0.9                     # relevance cutoff (metric-specific); null = off
  retention_days: 90                    # prune older than this; null = keep
  answer_digest_chars: 500              # how much of each answer to store
  write_on_query: true                  # persist a memory after each diagnostic answer
```

Recall depth can be overridden per provider via
`llm.external.{openai,anthropic}.memory_n_results` (default 3), so a cloud
provider recalls the same shallow set by default — deeper recall stays an
explicit `search_similar_incidents` tool call rather than a longer prompt.

To change the distance metric on an existing deployment, stop the backend and
delete `ai/data/chroma_db` (the collection is rebuilt on next start).

---

## Inspecting memory

Use the inspection tool to see what the AI remembers:

```bash
./scripts/query-chroma.sh count
./scripts/query-chroma.sh query "camera failure"
./scripts/query-chroma.sh dump
```

See [Memory Inspection](ai-memory-inspection.md) for details. Each record now
also carries `user_id`/`site_id`/`device_id`/`created_at`, so `dump` shows the
scope and age of every memory.

---

## Testing

`backend/tests/test_ai_memory.py` covers the store end-to-end with a
deterministic embedding function and a throwaway database: similarity recall,
site/user/device scoping, admin bypass, the distance cutoff, deduplication, and
retention pruning — plus endpoint tests asserting that a diagnostic query both
recalls with a scope and persists the answer, that a knowledge query touches
long-term memory in neither direction, and that a proposal answer is *not*
persisted (`_should_persist_answer_to_memory`).
