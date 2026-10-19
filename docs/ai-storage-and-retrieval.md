# AI Storage & Retrieval (As-Built Review)

This page is an **as-built review** of the AI subsystem: what is stored, where it
lives, and how a query flows through it to an answer. It complements the
component docs (`ai-memory.md`, `ai-doc-retrieval.md`, `ai-query-routing.md`,
`ai-code-access.md`) by describing the *current* wiring end to end, with the
numbers and traces observed on the running server.

Verified against `main` at commit `b33799d` on the deployment host
(`vps-5cd9e31f`), 2026-10-19. Counts and distances below are snapshots; re-run
the commands in [Inspecting it yourself](#7-inspecting-it-yourself) to refresh.

## 1. The map

A query enters `POST /api/v1/ai/query` with `mode: auto | knowledge | diagnostic`.
`auto` is resolved by a small **signal classifier**, not an LLM call:

| Signal | Example reason (from the log) | Resolves to |
| --- | --- | --- |
| How-to / definition wording | `how-to signal: 'how can'` | `knowledge` |
| Operational wording | `operational signal: 'status'` | `diagnostic` |
| Explicit `mode` | `explicit override: knowledge` | as requested |

The two paths then diverge:

```
POST /api/v1/ai/query
        |
        +-- knowledge  -> Chroma "project_docs" (top-4 chunks, cutoff 0.9)
        |                 -> static knowledge prompt + [RELEVANT DOCUMENTATION]
        |                 -> LLM -> strip [ANSWER]/Source markup
        |                 (no DB scan, no gates, no memory read, no memory write)
        |
        +-- diagnostic -> Postgres read via SQL  -> [CURRENT SYSTEM STATUS] / jobs
                          Chroma "device_logs"   -> [MEMORY SYSTEM STATUS] + [RELEVANT MEMORIES]
                          validation gates (A-E) -> trust envelope
                          LLM -> strip markup -> write compact memory
```

Two ChromaDB collections and one PostgreSQL database back everything. There is
**no third store** - in particular, the codebase is not embedded anywhere
(section 5).

## 2. PostgreSQL - the system of record

PostgreSQL is the authoritative store for operational data and is read **live**
at query time. It is never vectorised, and no row is ever written into Chroma.

* **30 tables** in `public`, including `sites`, `devices`, `device_metrics`,
  `device_state_history`, `health_checks`, `jobs`, `job_outcomes`, `alerts`,
  `configuration_history`, `enrolment_intents`, `api_request_logs`,
  `audit_logs`, `users`, and the delegation tables `ai_action_plan`,
  `ai_action_step`, `ai_approval`, `ai_outcome`.
* The diagnostic path builds `[CURRENT SYSTEM STATUS]` from SQL - active
  `Site` rows, then their active `Device` rows (`is_active`), from which it
  derives online/healthy counts, per-mode counts, and per-site device detail.
  Push/job context is added by `ContextBuilder`.
* Current deployment is a test fleet, so those counts are all zero
  (`sites 0, devices 0, device_metrics 0, jobs 0, alerts 0, users 4`). This is
  why diagnostic answers truthfully say the system is dormant - that is live
  data, not memory echoing.

```
[CURRENT SYSTEM STATUS]
Total Sites: 0
Total Active Devices: 0
Online Devices: 0
Healthy Devices: 0
Devices by Mode: 0 simulated, 0 emulated, 0 real
```

## 3. ChromaDB collection #1 - the documentation index (Tier C)

| Property | Value (observed) |
| --- | --- |
| Collection | `project_docs` |
| Location | `ai/data/docs_chroma` (~27 MB: 22 MB SQLite + HNSW segments) |
| Contents | 109 top-level `docs/*.md` -> **3227 chunks** + 1 index-version record = 3228 items |
| Embedder | ChromaDB default ONNX `all-MiniLM-L6-v2` (384-d), cosine distance |
| Metadata | `{source, title, heading}` per chunk |
| Retrieval | `n_results: 4`, `max_distance: 0.9` |

**How a chunk is built** (`ai/doc_retriever.py`): markdown is split into
heading-aware sections; each long section is windowed at `chunk_size: 800`
characters with `chunk_overlap: 150`; each window is stored as
`# {heading}\n{window}` with id `sha256(source, section_idx, window_idx)`.

**Rebuild policy**: the index version is a hash of the corpus
(`path`, `size`, `mtime`) plus the indexing settings (`chunk_size`,
`chunk_overlap`, `max_chunks_per_doc`, `max_file_bytes`). When the hash changes,
the collection is recreated and re-added (lazily, on the next knowledge query).
A stable corpus costs nothing per query; touching any doc - or changing the
chunking - triggers a full rebuild.

**Retrieval is grounded in real paths.** For *"How do I enrol a device?"*
(`n=4`, cutoff 0.9) the four chunks were:

```
0.3548  docs/device-registration.md             - Method A: Pre-Provisioned (Dashboard-Driven)
0.3819  docs/enrolment-intents.md               - Enrolment Intents
0.4164  docs/device-lifecycle-and-ownership.md  - Pre-provisioned enrolment
0.4208  docs/device-registration.md             - Prerequisites
```

Those chunks are rendered into a `[RELEVANT DOCUMENTATION]` block, each
labelled `--- source - heading ---`; the unique paths are returned as the
response `sources`. If nothing passes the cutoff, the fixed doc excerpts are
used as a fallback. This is what prevents the model from inventing file names
like `docs/device-enrolment.md`.

### Coverage gaps (known)

* `_discover_docs()` only lists markdown files **directly** in `docs/`, so
  subdirectory docs are not indexed - currently 6 files:
  `docs/uq/{overview,study1-anomaly,study2-simulator,study3-push}.md` and
  `docs/images/{README,QUICKREF}.md`.
* `max_chunks_per_doc: 60` caps any single document; at least 10 large guides
  sit at the cap (e.g. `database-guide.md`, `deployment-guide.md`,
  `development-guide.md`, `mqtt-push-integration.md`,
  `timescaledb-integration.md`), so their tail content is not retrievable.

## 4. ChromaDB collection #2 - long-term memory

| Property | Value |
| --- | --- |
| Collection | `device_logs` (`ai/data/chroma_db`, ~0.7 MB) |
| Metadata | `{source: ai_query, trust_score, is_actionable, user_id, created_at}` |
| Recall | `n_results: 5`, `max_distance: 0.9`, scope-filtered (user/site/device) |
| Retention | `retention_days: 90`, pruned at service start |
| Writer | the API process only (single writer) |

**Only the diagnostic path touches memory.** On the knowledge path, memory is
neither read nor written (`docs/ai-memory.md`): a knowledge answer is grounded
in documentation only, so the model can never echo its own past output back to
itself.

On the diagnostic path the recalled memory is injected as:

```
[MEMORY SYSTEM STATUS]
Total Memories Stored: N

[RELEVANT MEMORIES]
- Q: ... A: ...
```

The effect is visible in the per-request size line, `AI context parts`:

| Store state | `memory=` chars in the context |
| --- | --- |
| Empty | **49** (status line only) |
| One matching memory | **476** (status line + recalled Q/A) |

Because the diagnostic path also *writes* a compact memory after each answer
(`write_on_query: true`, `answer_digest_chars: 500`), repeated similar questions
accumulate near-duplicate self-referential answers. That is intentional for now
(those answers are anchored by live data and gates), but it is the same
feedback loop that was removed from the knowledge path, and it is worth
revisiting once the fleet carries real data. An incident writer (section 8) is
the natural replacement for "store every answer".

## 5. Where the codebase lives

**Nowhere in a store.** The repository is not chunked, embedded, or copied into
either Chroma collection. Code grounding is a separate, *live* layer (Tier B,
`ai/repo_tools.py`):

* Tools: `read_file`, `search_code`, `list_dir` - bounded and read-only.
* Roots: `docs/`, `backend/src/`, `ai/`, `frontend/src/`, with deny globs for
  secret material (`.env*`, `*.pem`, `*.key`, `*.p12`, `id_rsa*`, ...).
* Results carry exact `path:line` from the working tree, so they are always
  current and never stale.

It is **disabled** (`code_access.enabled: false`) because enabling it on the
knowledge path cost ~9-10x latency with no measurable answer gain on this
hardware. When it is enabled, the knowledge path runs a bounded tool loop and
surfaces every file it read as an extra source. See `docs/ai-code-access.md`.

## 6. End-to-end traces (from `journalctl -u homepot-api`)

**Diagnostic** (auto-routed by the `'status'` signal; warm, ~41 s):

```
AI query | device_id=N/A | query_len=34 | user=...
AI query routing | requested=auto | resolved=diagnostic | reason=operational signal: 'status'
AI context parts | full=1773 site=222 job=36 memory=476 short=0 enriched=389 other=650
AI query done | device_id=N/A | mode=Mode 1: Status-only | score=0.00 | actionable=False
AUDIT: ai_query - AI query | mode=Mode 1: Status-only | score=0.00
```

**Knowledge** (explicit override; warm, ~72 s):

```
AI query routing | requested=knowledge | resolved=knowledge | reason=explicit override: knowledge
AI query done | mode=knowledge | reason=explicit override: knowledge
AUDIT: ai_query - AI query | mode=knowledge | device=N/A
```

Note the `AI context parts` breakdown: `site`/`job`/`memory`/`enriched` are the
dynamic, per-query context (~1.8k chars here); the static system prompt
(~3.8k tokens) is separate. The dynamic part is re-evaluated by the CPU on
every query, so it is the main size/latency lever.

## 7. Inspecting it yourself

```bash
# Documentation index (chunk count, structure, similarity search)
./scripts/query-chroma.sh --store docs count
./scripts/query-chroma.sh --store docs query "How do I enrol a device?" -n 6
./scripts/query-chroma.sh --store docs dump        # id + metadata only

# Long-term memory
./scripts/query-chroma.sh count
./scripts/query-chroma.sh peek -n 5

# System of record
psql "$(printf '%s' "$DATABASE__URL" | sed 's/+asyncpg//')" -c "\dt"
psql "$(printf '%s' "$DATABASE__URL" | sed 's/+asyncpg//')" -c "SELECT count(*) FROM devices"

# Query traces / audit
journalctl -u homepot-api -f | grep -E "AI query|routing|context parts"
```

The running API holds the Chroma stores open (single writer), so the inspector
transparently falls back to a temporary snapshot copy and says so. See
`docs/ai-memory-inspection.md`.

## 8. Known limitations & observations

1. **Cold starts can starve other users.** With `max_concurrent: 1` and
   `queue_timeout_seconds: 45`, one long generation (a cold model load after
   >30 min idle takes ~2-5 min) fills the only inference slot; concurrent
   queries get `503 Service Unavailable`. Observed on 2026-10-19: a knowledge
   query took 324 s cold and 503'd a real query that arrived 2 minutes later.
   Mitigations: keep the model resident (`keep_alive: 30m` already), raise
   `max_concurrent` with Ollama slots, or answer from cache for repeated queries.
2. **`num_predict: 160` suits the status answer** (~110-140 tokens) but is tight
   for knowledge how-to answers (numbered step lists), which can be truncated.
   A per-path output cap is the obvious fix.
3. **Documentation coverage:** subdirectory `.md` files (notably the four
   `docs/uq/` study docs) are not indexed, and the 60-chunk-per-doc cap
   truncates the largest guides.
4. **Memory noise:** write-on-query accumulates near-duplicate diagnostic
   answers (see section 4).
5. **Test-environment emptiness** means the validation gates (A-E) are barely
   exercised; Gate B's continuity/completeness thresholds are deliberately
   relaxed in `ai/config.yaml` for that reason.
6. **Cosmetic:** the `llm.keep_alive` comment block is duplicated in
   `ai/config.yaml`.

Candidate next steps (tracked separately): slim the dynamic context
(`validation_gates.gate_c.max_context_chars` is 16000), enable Tier B on the
agentic path only, add the incident writer, and either recurse into `docs/`
subdirectories or explicitly exclude them.
