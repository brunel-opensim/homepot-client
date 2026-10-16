# AI Memory (Short-Term & Long-Term)

The AI has two kinds of memory. This page describes how they work, how they are
scoped for multi-tenant safety, and how to configure them.

| | Short-term memory | Long-term memory |
|---|---|---|
| **What** | Recent conversation turns | Past answers / incidents |
| **Where** | Supplied by the client per request | ChromaDB vector store (on disk) |
| **Lifetime** | One request | Until pruned (default 90 days) |
| **Recall** | Last 5 messages, verbatim | Semantic similarity + scope filter |
| **Code** | `AIEndpoint.query_ai` | `ai/device_memory.py` |

---

## Short-term memory (conversation)

The client sends the conversation `history` in the request body. The endpoint
keeps the **last 5 messages**, sanitizes them (prompt-injection scrubbing), and
injects them as a `[CONVERSATION HISTORY]` block:

```python
# backend/src/homepot/app/api/API_v1/Endpoints/AIEndpoint.py
if request.history:
    short_term_context = "\n[CONVERSATION HISTORY]\n"
    short_term_context += "\n".join(
        f"{sanitize(msg.role)}: {sanitize(msg.content)}"
        for msg in request.history[-5:]
    )
```

Short-term memory is **stateless on the server**: nothing is stored, and the
client is responsible for sending history back. This keeps the request path
simple and avoids storing transcripts.

!!! note "Cost"
    On the CPU-only host every history token is re-evaluated on each turn
    (~22 tok/s). Keep client history short; it is capped at 5 turns but not by
    token budget.

---

## Long-term memory (vector recall)

Long-term memory is a persistent **ChromaDB** collection. Each entry is a small
text record plus metadata, stored as an embedding so the AI can recall entries
that are *semantically similar* to the current question.

### What gets stored

After a successful query the endpoint stores a compact record
(`write_on_query: true`):

```
Q: <the question>
A: <first ~500 chars of the answer>
```

with metadata:

| Field | Meaning |
|---|---|
| `user_id` | Author (carried from the authenticated user) |
| `site_id` | Site the memory belongs to (when unambiguous) |
| `device_id` | Device, for device-focused queries |
| `created_at` | Unix timestamp, used for retention |
| `source` | `ai_query` |
| `trust_score`, `is_actionable` | Validation-gate outcome for the answer |

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
  n_results: 5                          # max memories recalled per query
  max_distance: 0.9                     # relevance cutoff (metric-specific); null = off
  retention_days: 90                    # prune older than this; null = keep
  answer_digest_chars: 500              # how much of each answer to store
  write_on_query: true                  # persist a memory after each AI answer
```

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
retention pruning — plus an endpoint test asserting that a query both recalls
with a scope and persists the answer.
