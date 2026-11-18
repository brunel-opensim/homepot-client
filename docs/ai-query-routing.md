# AI Query Intent Routing (Design)

> **Status:** Proposed / design-only — no code changes in this document yet.
> **Goal:** let the assistant answer **informational / how-to** questions (e.g.
> "how do I enroll a device?", "what does `root_access` mean?") **without**
> running the device-data validation pipeline, while the **diagnostic** and
> **action** paths behave exactly as they do today.
> **Related:** [Agentic AI](ai-agentic.md) | [Trust & Validation Gates](ai-validation-gates.md) | [Task Delegation](ai-delegation-plan.md) | [Concurrency & Load](ai-concurrency.md) | [AI Memory](ai-memory.md)

---

## 1. Problem

Every `POST /ai/query` currently runs the **same** pipeline regardless of what
is being asked (`backend/src/homepot/app/api/API_v1/Endpoints/AIEndpoint.py`):

1. Memory recall + **fleet-wide DB scans** (sites, active devices, alerts),
   push/job context, and enriched per-device context (`AIEndpoint.py:574-766`).
2. **Gates A–E** always run — `envelope.run(gate_context)` — except the
   zero-fleet short-circuit (`AIEndpoint.py:809-810`, `800-807`).
3. **AI insights** (system anomaly scan + failure prediction) run whenever Gate
   B passes (`AIEndpoint.py:826-878`).
4. The prompt always receives a `[VALIDATION TRUST STATUS]` block, and for
   non-actionable answers a `Failed gate: …` line; zero-fleet adds a
   `[REFUSAL MANDATE]` (`AIEndpoint.py:921-956`).
5. The system prompt then hard-instructs the model: *"If 'Actionable' is 'no',
   you MUST explicitly tell the user their data could not be fully validated …
   limit your answer to cautionary, non-actionable observations"*
   (`ai/system_knowledge.py:197-204`).

The result for a pure knowledge question ("how do I enroll a device?"):

- **Cost:** it pays the full operational-data + gate latency, which is
  significant on a CPU-only inference host.
- **Answer quality:** the model is pushed toward device-diagnostic, cautionary
  framing that has nothing to do with the question, so it can hedge or refuse
  even though the answer is documentation knowledge.
- **Misleading signal:** the response carries a `trust` envelope with a
  `failed_gate`, implying the *answer* was unvalidated when the gate concerns
  device telemetry the question never needed.
- **Thin knowledge base:** the docs handed to the model are a fixed set of five
  (`ai/system_knowledge.py:221-227`) with no enrollment/how-to content.

## 2. Goal and non-goals

**Goal**

- Route each query by **intent** and give the assistant a first-class
  **knowledge path** that answers how-to/definition/product questions from
  documentation, quickly and without the device gates.
- Leave the **diagnostic** and **action** paths — gates, insights, proposals,
  approval, execution — **unchanged**.

**Non-goals**

- Removing or weakening the validation gates for diagnostic/action queries.
- Changing proposal/approval/execution semantics (Level 2 delegation).
- Any change to what the AI may *do* — the AI still cannot execute anything.

## 3. Intent classes

| Class | Meaning | Examples |
|---|---|---|
| `knowledge` | Question answerable from product documentation / definitions; no live device state needed | "How do I enroll a device?", "What does `root_access` allow?", "Which command restarts an agent?" |
| `diagnostic` | Question about the **current or historical state** of the fleet | "Why is device X offline?", "Any anomalies at Site B today?", "Show stale devices." |
| `action` | A request that should produce a **proposed action plan** | "Restart device X.", "Raise brightness on the lobby display." |

`action` is a subset of the operational path; it is separated only so the
router can bias toward the agentic proposal flow and so the UI/labels can differ.

## 4. Design overview

```mermaid
flowchart TD
    Q[POST /ai/query] --> R{Resolve mode}
    R -->|explicit override| M[mode = knowledge / diagnostic]
    R -->|auto: heuristics| H[Classify intent]
    H -->|knowledge| K[Knowledge path]
    H -->|diagnostic / action| D[Today's operational path]

    K --> K1[Skip fleet scans, gates, insights]
    K1 --> K2[Knowledge system prompt + doc context]
    K2 --> K3[trust = informational]

    D --> D1[Fleet scan + gates A-E + insights]
    D1 --> D2[Diagnostic system prompt + trust status]
    D2 --> D3[Proposals only if actionable]
```

Nothing between the router and the executor is LLM-generated, and the knowledge
path can never create a plan.

## 5. Classification: heuristics + explicit override

Per the chosen approach, the default is **deterministic heuristics with no extra
LLM call** (keeps the CPU host fast), plus an **explicit override** the user can
set. The router is intentionally conservative: **when in doubt, fall back to
`diagnostic`** so today's (safe) behaviour is the default.

Resolution order (first match wins):

1. **Explicit override.** `request.mode` (`knowledge` | `diagnostic` | `auto`).
   `auto` (default) proceeds to heuristics.
2. **`action` intent.** If the query contains an imperative action signal for a
   declared capability (e.g. "restart", "reboot", "apply config", "set … to
   …", "change settings") → `diagnostic`/`action` path (agentic + proposals).
3. **`device_id` present.** A query scoped to a concrete device is treated as
   `diagnostic` (the user is asking about that device), unless the override says
   otherwise.
4. **`knowledge` intent.** If the query matches how-to/definition signals
   (interrogatives such as *how do I / how to / what is / what does / explain /
   where can I find / which command / meaning of*, plus a small allowlist of
   product terms) → `knowledge`.
5. **Default.** `diagnostic`.

Illustrative signals (tunable, single source of truth in config):

```text
KNOWLEDGE_PATTERNS = [
  r"\bhow (do|can|to|does)\b", r"\bwhat (is|are|does|do)\b",
  r"\bexplain\b", r"\bmeaning of\b", r"\bwhere (can|do) i\b",
  r"\bwhich command\b", r"\benroll(ment)?\b", r"\bpermission\b",
  r"\bdocumentation\b", r"\bhow it works\b",
]
ACTION_PATTERNS = [
  r"\brestart\b", r"\breboot\b", r"\bapply\b", r"\bset .* to\b",
  r"\bchange .* config", r"\bpush .* config", r"\bshut ?down\b",
]
```

Notes:

- **Conversation continuity:** a follow-up in an existing conversation
  ("and what about 24-bit?" after a knowledge answer) should inherit the prior
  turn's mode from `history` when the new text alone is ambiguous. If that is
  too much for v1, ambiguous follow-ups fall back to `diagnostic`.
- **Specific how-to about "my device X"** is a genuine ambiguity (device_id
  present ⇒ step 3 ⇒ diagnostic). The override lets a user pin `knowledge`; a
  later refinement can use embeddings-based routing.

## 6. Request and response contract

`AIQueryRequest` (`AIEndpoint.py:179`) gains one field:

```python
mode: Literal["auto", "knowledge", "diagnostic"] = Field(
    default="auto",
    description="Force a query path; 'auto' classifies by intent (default).",
)
```

The response echoes the **resolved** routing so callers can log/debug it:

```json
{
  "response": "...",
  "trust": { "mode": "informational", "score": null, "actionable": false },
  "routing": { "requested": "auto", "resolved": "knowledge", "reason": "how-to signal: 'how do i enroll'" }
}
```

Backwards compatible: existing callers omit `mode` and (for genuine diagnostic
questions) behave exactly as before.

## 6.1 UI — how a technician chooses

Today's Dashboard chat is `AskAIWidget.jsx` (rendered at `Dashboard.jsx:520`,
titled "System Diagnostics AI"). It has one input + send and calls
`api.ai.query(query, null, userRole)` (`AskAIWidget.jsx:340`), which posts
`{ query, role }` (`api.js:788`) — no `agentic`, no `mode` — so every question
takes the same gate-heavy path and always renders the `TrustBanner` +
`GateReplay`. There is **no selector today**; the mode is neither user-chosen nor
LLM-chosen because the field does not exist yet.

The design adds one control, with `Auto` as the default:

```
┌ System Diagnostics AI ───────────────────────────┐
│  [ response area ]                               │
│  ┌────────────────────────────────┐  ┌────────┐  │
│  │ Ask about status or how-to…    │  │  Send  │  │
│  └────────────────────────────────┘  └────────┘  │
│  Mode:  ( Auto )  Knowledge   Diagnostic         │
└──────────────────────────────────────────────────┘
```

- **Control:** a compact segmented control (`Auto` / `Knowledge` / `Diagnostic`)
  next to the input, defaulting to `Auto` — this is the override from §5.
- **Plumbing:** `api.ai.query` gains a `mode` argument and includes it in the
  payload; `AskAIWidget` passes the selected value. `Auto` sends `mode: "auto"`
  (or omits it — the backend default).
- **Only the technician selects `Knowledge`/`Diagnostic`; the LLM never picks the
  mode.** Under `Auto`, the backend heuristics resolve it (§5).
- **The UI reflects the resolved mode** (`routing.resolved` in the response):
  - `diagnostic` / `action` → today's `TrustBanner` + `GateReplay`, unchanged.
  - `knowledge` → hide the trust UI (no gates ran); show a small "Knowledge"
    chip and, optionally, the cited sources.
- **Optional:** remember the last choice per session — localStorage already holds
  `homepot_ai_query`/`_response`/`_trust`, so add a `homepot_ai_mode` key.

## 7. Per-mode pipeline

| Step | `knowledge` | `diagnostic` / `action` |
|---|---|---|
| Auth (`require_user`) | yes | yes |
| Memory-scope resolution + scoped recall | yes (RBAC unchanged) | yes |
| Fleet/sites/devices/alerts DB scans | **skip** | yes |
| Enriched per-device context | skip | yes |
| Gates A–E | **skip** | run |
| AI insights (anomaly + failure prediction) | skip | run when Gate B passes |
| System prompt | **knowledge prompt** (§8) | diagnostics prompt (current) |
| `[VALIDATION TRUST STATUS]` / refusal mandate | **not injected** | injected |
| Proposals | **never** | only if trust actionable and run healthy |
| Response `trust` | informational (§9) | envelope (current) |

Skipping gates/insights for `knowledge` removes the DB work and the
cautionary instructions in one move.

When the envelope is **not actionable**, the proposal tools refuse to record
anything and return the failed-gate reason to the model. If the agent still
attempted a proposal, the endpoint prepends a deterministic "No proposal was
created" notice to the answer. This prevents the assistant from telling a
technician that a proposal exists when nothing was persisted -- for example,
when Gate B fails on stale telemetry. See
[ai-delegation-plan.md](ai-delegation-plan.md) for the proposal lifecycle.

A second, broader guard covers any answer that claims an action was already
issued, sent, or executed ("Command Issued", "Status: SENT"). A chat turn can
only record a proposal -- it never sends a command -- so the endpoint prepends
a "No command was issued" correction. This holds even when the request ran
without the agent loop (for example a non-agentic API client). The dashboard's
Ask AI always opts into the agent loop (`agentic: true`) so natural-language
action requests become tracked proposals.

## 7.1 Knowledge mode and the analysis-mode guard

None of the diagnostic/cautionary behaviour should leak into `knowledge`. The
knowledge prompt does **not** contain the "if Actionable is no, you MUST warn…"
instruction, and the `[VALIDATION TRUST STATUS]` / `[REFUSAL MANDATE]` blocks are
not assembled at all.

## 8. Knowledge path details

**Prompt.** A separate knowledge-oriented system prompt (identity: product /
SOP assistant for HOMEPOT). It keeps the command-payload reference
(`ai/system_knowledge.py:248-342`) and the role definitions, but drops the
operational "diagnose the fleet" framing and the trust instruction.

**Documentation context — implemented (v1).** The path retrieves the most
relevant chunks from the **whole `docs/*.md` corpus** and injects them as a
`[RELEVANT DOCUMENTATION]` block with real file paths (see
[§8.1](#81-grounding-sources-of-truth-code-vs-docs) and
[AI Documentation Retrieval](ai-doc-retrieval.md)). The old fixed five-doc
excerpt list (`ai/system_knowledge.py:279-314`) is kept only as a fallback when
retrieval returns nothing. The knowledge path must never present operational
data as if it were live.

**No proposals.** The `propose_device_action` tool is not offered to the model
on this path, so a knowledge run cannot emit a plan even if the model tries.

## 8.1 Grounding & sources of truth (code vs docs)

The knowledge path is only as good as what the model is given, and today that is
**metadata and a fixed set of doc excerpts — never the code**. This subsection
defines how the assistant should stay anchored to the code, since the code — not
the prose — is the point of reference when they diverge.

### What the assistant sees today

| Source | What is exposed | Limits | Ref |
|---|---|---|---|
| README | intro prose | ~1800 chars, to first section | `ai/system_knowledge.py:36-61` |
| Project structure | **file names only** (4 dirs) | top 15 files each | `ai/system_knowledge.py:64-97` |
| DB schema | tables + first columns, **parsed from models** | 15 cols/table, ≤4500 chars | `ai/system_knowledge.py:99-148` |
| Documentation (knowledge path) | **whole `docs/*.md` corpus, retrieved per query** | top-k chunks + `max_distance` cutoff | `ai/doc_retriever.py` |
| Documentation (fallback) | **first 500 chars** of 5 docs | fixed list; used only when retrieval misses | `ai/system_knowledge.py:279-314` |
| Command reference | **hand-written literal** | static string | `ai/system_knowledge.py:316-410` |
| Agent tools | live device/fleet/memory reads + proposal capture | no code/doc access | `ai/tools.py:468-478` |

So the model can list files and see a slice of the schema, but **cannot open,
read, or search a source file on demand**. When docs drift from code it has no
route to the truth — and while the DB schema is *derived* from code, the command
reference is manual and can silently fall out of sync.

The knowledge path's *documentation* grounding now retrieves from the whole
corpus (Tier C, below); everything else in this table is unchanged, and there is
still **no on-demand code/source access** (that is Tier B).

### Grounding tiers (cheapest → richest)

**Status:** Tier C is **implemented** (v1) — see
[AI Documentation Retrieval](ai-doc-retrieval.md). Tier A and Tier B remain
proposals.

**Tier A — generate structured references from code (recommended first).**
Replace hand-maintained literals with values derived from their real source at
build/startup, so structured facts cannot drift:

- command payloads ← `homepot.agent.utils.command_poller.COMMAND_TYPES` and the
  `REQUIRED_PERMISSION` map;
- proposable actions ← `ai/actions.py` (`ACTION_REGISTRY`);
- API surface ← the FastAPI app's routes;
- DB schema ← the SQLAlchemy models (already done at
  `ai/system_knowledge.py:83-133`).

Generate at process start, and/or via a build step whose output is committed and
diffable. Deterministic, no LLM, no per-query cost.

**Tier C — retrieve docs (+ selected generated references) instead of fixed
excerpts. — ✓ implemented (v1)**
A ChromaDB index over the docs (`ai/doc_retriever.py`) chunks the corpus and
retrieves the top-k relevant chunks for the query, attaching **citations** (real
`docs/…` paths). This replaces "first 500 chars of 5 files" with query-relevant
context inside a bounded budget, and lets the corpus grow without bloating every
prompt.

As built: heading-aware chunking, a ChromaDB collection under `ai/data/docs_chroma`
with version-gated rebuilds (`path/size/mtime` plus the indexing settings), the
chunks injected as a `[RELEVANT DOCUMENTATION]` block, and the retrieved paths
returned as a machine-readable `sources` list (rendered as chips in the UI). It
reuses the existing ChromaDB/embedder stack rather than `DeviceMemory` directly,
so the two stores stay separate. Generated Tier-A references are **not** indexed
yet. Full details: [AI Documentation Retrieval](ai-doc-retrieval.md).

**Tier B — read-only code tools (design-only; see
[AI Code Access (Tier B)](ai-code-access.md)).**
Add allowlisted, sandboxed tools to the knowledge and agentic paths:

```
read_file(path)       # numbered lines, capped
search_code(pattern)  # ripgrep-style, capped result count
list_dir(path)
```

Hard constraints:

- **Allowlist** roots only (`docs/`, `backend/src/`, `ai/`, `frontend/src/`),
  with path normalization to block traversal/symlinks.
- **Size/line caps** (e.g. ≤400 lines, ≤20 hits) and explicit truncation markers.
- **Secret exclusion** — refuse `.env` and credential/key files via a denylist;
  never echo environment variables.
- **Read-only** and **audited** (via the existing audit logger); available on
  `knowledge`/agentic runs only — never a new mutate path.
- Answers that use code must **cite** `path:line`.

B is more powerful but costs model iterations on the CPU host, so it must be
bounded and enabled deliberately. Full contracts, safety envelope, and rollout:
[AI Code Access (Tier B)](ai-code-access.md).

### Freshness & invalidation

- Tier A references are regenerated at process start (and can be committed);
  they are the anti-drift guarantee for structured facts.
- The system prompt is rebuilt per request today (`AIEndpoint.py:1014`), so doc
  edits are already picked up without a restart. Keep that for docs, but keep
  the generated references deterministic so the startup warm-up prefix
  (`homepot/app/main.py:204`) stays identical and the KV cache still hits —
  see *Prompt-prefix caching* below for what it costs when that breaks.
- Retrieval-index rebuilds stay out of the request path (startup or an explicit
  reindex) to avoid per-query cost.

### Prompt-prefix caching (path-switch latency)

Ollama reuses its KV cache for the **common prefix** of two prompts: when the
leading bytes of a request match the previous one, only the new tail is
evaluated; when they diverge early, the whole prompt is re-evaluated.
Prompt-eval on the demo host (`llama3.2` on 4 CPU cores) runs at ~30 tok/s and
is the dominant cost of a query that is not cache-warm:

| case | tokens evaluated | prompt-eval time |
| --- | --- | --- |
| prefix matches the previous request | ~450 (the tail) | ~17 s |
| prefix is cold (never seen / model reloaded) | ~3,500 (whole prompt) | 111-132 s |
| exact same prompt repeats | ~0 | 0.2-0.9 s |

`main.py` warms the model at startup by sending the **diagnostic** prompt, so
for that warm-up to be worth anything, every other path must *start with those
same bytes*. Both paths therefore begin with `SystemKnowledge._shared_prefix()`
— the static system context, the command-payload reference and the role
definitions — and only then add their mode-specific identity, capability list
and instructions. The diagnostic-only `[DOCUMENTATION]` block sits after that
fork on purpose: including it earlier would break the prefix for `knowledge`,
which deliberately omits it.

This is enforced, not just intended: `backend/tests/test_ai_system_prompt_cache.py`
asserts that the shared block leads all three prompts (diagnostic, knowledge,
knowledge + repo tools) and stays byte-identical between calls.

Before the paths were aligned, they forked at character 30 — the first sentence
of the identity line ("...System Diagnostics AI" vs "...Knowledge Assistant") —
so switching from a diagnostic to a knowledge question re-evaluated the entire
~3.2k-token system prompt. Measured with the model unloaded between runs, so
both prefixes started genuinely cold:

```
switch diagnostic -> knowledge, prompt evaluation
  before: 111,887 ms
  after :  17,020 ms      (6.6x faster, ~95 s saved per switch)
```

Rotating a conversation between the two paths is the normal demo case, so this
is the difference between a ~2-3 minute answer and a ~1 minute one. Note what
the fix does *not* do: everything after the fork — the mode-specific
instructions plus the per-query user turn (retrieved docs, live status) — is
still evaluated on every request at ~30 tok/s. Shrinking the prompt or the
retrieved context is the lever for that.

Consequences for future edits:

- Keep the shared block first and deterministic. A per-request value inside it
  (timestamp, request counter, unsorted directory walk) would silently disable
  prefix reuse for *every* query on every path.
- Mode-specific text belongs in the tail: `[RELEVANT DOCUMENTATION]`, the
  `[VALIDATION TRUST STATUS]` protocol and the repo-tool guidance are all
  tail-only today.
- When adding a new path, start its system prompt with `_shared_prefix()`.


### Relationship to the routing design

`knowledge` uses Tier A + Tier C (and optionally B); the `diagnostic`/`action`
paths are unaffected — they stay anchored to live data through the gates. The
model must still never present live operational state in `knowledge` mode, even
if a retrieved snippet mentions a device.

## 9. Trust reporting

For `knowledge` queries the response `trust` is **informational**, not a gate
result:

- `trust_mode`: a new non-gate mode (e.g. `informational` / `none`),
- `trust_score`: `null` (or omitted),
- `actionable`: `false`, `failed_gate`: `null`.

This is accurate (no device data was validated because none was needed) and
prevents the UI from rendering a "failed gate" banner for a how-to answer. The
delegation UI is unaffected: it only acts on plans, which only exist on the
operational path.

## 10. Safety & RBAC

- `require_user` auth, memory scoping, and site/device access rules are
  unchanged and apply to all modes.
- The knowledge path is **read-only by construction**: no fleet scan, no gates,
  no proposal tool, no execution.
- **Bias to safety:** any ambiguity resolves to `diagnostic`. A query that hints
  at action ("just restart it for me") matches the action signals and follows the
  operational path, where the full gate + approval + execution controls apply.

## 11. Configuration & rollout

- **Flag:** `AI_QUERY_ROUTING` (`heuristics` default, `off` to disable) so the
  behaviour can be rolled back without a code change.
- **Config:** the pattern lists and mode defaults live in one tunable module.
- **Phases:**
  1. Add the `mode` field + resolver + knowledge path behind the flag, with
     tests; log the resolved mode. Default remains effectively current
     behaviour for diagnostic queries.
  2. Add the chat UI mode selector (Auto / Knowledge / Diagnostic) and surface
     the resolved mode in the response.
  3. Expand the knowledge corpus + relevance selection; review misroutes.

## 12. Observability

- Log the resolved mode and the deciding signal at INFO.
- Add a `routing_mode` field to the `ai_query` audit event metadata.
- Metrics: request latency by mode, share of `knowledge` queries, override rate,
  and any user-reported misroutes (to tune the patterns).

## 13. Testing

- **Router unit tests:** table-driven matrix — knowledge/diagnostic/action
  phrasings; override beats heuristics; `device_id` ⇒ diagnostic; ambiguous ⇒
  diagnostic; continuation inherits mode (if implemented).
- **API tests:** a `knowledge` query performs **no** gate/insight DB access
  (assert the gate/envelope path is not invoked) and returns informational
  `trust`; a `diagnostic` query is byte-for-byte the current behaviour; proposals
  are only ever produced on the operational path.
- **Grounding tests (Tier C) — implemented:** `backend/tests/test_ai_doc_retrieval.py`
  exercises the real ChromaDB index with a deterministic embedder (retrieval
  relevance + real source, heading metadata, reindex on corpus change,
  stable-corpus no-op, empty query, distance cutoff, long-section windowing,
  missing docs dir); the knowledge-path tests assert the `[RELEVANT DOCUMENTATION]`
  block, the `sources` response field, and that the fixed-doc fallback is not used
  on a retrieval hit; the frontend tests cover the UI source chips. See
  [AI Documentation Retrieval § Testing](ai-doc-retrieval.md#testing).
5. **Naming:** `knowledge` vs `informational` vs `general`; and the new
   `trust_mode` label.
6. **Grounding scope:** do we ship Tier A alone in v1, or A + C? (Proposed: A
   first — it removes the real drift — then C.)
5. **Tier-B code tools:** enable read-only `read_file`/`search_code` in v1, or
   defer until Tier A/C are in place? (Proposed: defer.)
7. **Retrieval details:** chunk size, embedding model, and index refresh cadence
   (startup vs explicit reindex).
8. **Citations in the UI:** render `path:line` / `doc#anchor` as links, or plain
   text?
- **Grounding tests (Tier A / Tier B — not yet implemented):** a drift test
  asserting generated Tier-A references match `COMMAND_TYPES`/`ACTION_REGISTRY`;
  Tier-B tools reject paths outside the allowlist, `.env`, and oversized reads.
  (Tier C retrieval is covered by the grounding tests above.)

## 14. Open questions

1. **Follow-up continuity:** inherit mode from `history`, or rely on the
   override for v1? (Proposed: override only in v1.)
2. **"How do I enroll *my* device X"** (device_id present but a how-to):
   accept that this routes to `diagnostic`, or add a "device-scoped knowledge"
   sub-case? (Proposed: route to `diagnostic`, override available.)
3. **Doc selection:** static expanded list vs keyword-scored relevance in v1?
   (Proposed: keyword-scored within a bounded budget.)
4. **Should `knowledge` recall long-term memory?** (Proposed: yes, same scoped
   recall — it can carry useful prior answers — but never invent live state.)
5. **Naming:** `knowledge` vs `informational` vs `general`; and the new
   `trust_mode` label.

## 14.1 Operational query granularity (open design question)

A binary `knowledge` / `diagnostic` split is not always enough. A query such as
"How many active devices are online?" is operational, but its answer is a simple
aggregate count derived from the `devices` table. Running the full telemetry
gate chain (Gate B completeness, freshness, continuity, validity) and then
capping trust at Mode 2 when the fleet has zero online devices can make a
correct count look untrustworthy.

### Observed example

Query: "How many active devices are online?"

- Route: `diagnostic` (matches `online` in `OPERATIONAL_PATTERNS`; `active` is
  not itself a pattern).
- Gate B connectivity fails when there are no online devices, because the check
  treats "no online devices" as "fleet telemetry is unavailable". This is
  distinct from the existing zero-fleet short-circuit, which applies only when
  there are no active devices at all.
- Result: Mode 2 / best-effort analytics, with cautionary framing. The observed
  example carried a trust score around 44%, though the exact score depends on
  the other gate results. The count itself is a valid fleet observation.

### Terminology to make explicit

The backend already distinguishes these terms, but the prompt does not define
them. The AI infers meaning only from labels such as `Total Active Devices` and
`Online Devices`, which is not reliable enough for small models or mixed
questions.

- **Active**: the device record is enabled and visible in the fleet
  (`Device.is_active = true`).
- **Online**: an active device whose latest heartbeat is inside the configured
  offline threshold, computed by `compute_connectivity()`. Online is a subset
  of active.
- **Offline / Unknown**: an active device whose heartbeat is stale or absent.
- **Healthy**: a separate health-state field (`health_state`), not the same as
  online.

Before implementation, the fleet-summary context block should define these
terms and use a clearer label such as
`Online Devices (active with fresh heartbeat)`. When a question mixes "active"
and "online" (for example, "How many active devices are online?"), the answer
should state both counts briefly: "There are N active devices, of which M are
online."

### Possible differentiation axes

1. **Intent granularity.** Add a third operational class such as `fleet_summary`
   or `status` for inventory/count questions. This class would remain
   operational, but would not need telemetry-integrity validation or AI
   insights.
2. **Data dependency.** Split Gate B by what the answer actually depends on:
   - Fleet count / inventory: Gate A + Gate B connectivity only; skip telemetry
     integrity. Connectivity currently lives inside Gate B, so this would mean
     treating it as a separately selectable check.
   - Telemetry trend / health: Gate A + full Gate B + Gate C.
   - Anomaly analysis: Gate A + full Gate B + Gate C + insights.
   - Device-specific diagnosis: Gate A + target connectivity + telemetry gates.
   - Action / proposal: full gates plus policy controls.
3. **Connectivity semantics.** For fleet-scoped counts, "0 online devices" can
   be a valid observation rather than a data-integrity failure. For
   device-scoped queries, an offline target should still fail because that
   device cannot be diagnosed.
4. **Trust presentation.** Aggregate/status answers could use a non-cautionary
   trust presentation, while telemetry-dependent diagnostics keep the current
   Mode 2 / Mode 3 framing.
5. **Explicit control.** Extend the UI mode selector or add a `needs` /
   `scope` field (`inventory` vs `telemetry`) so the technician can state the
   required evidence instead of relying only on natural-language heuristics.

### Trade-offs

- Skipping gates can hide real data-quality problems. A count of zero online
  devices may be correct, or it may indicate a heartbeat pipeline failure.
- Heuristic routing is already conservative and can misclassify. More classes
  increase that risk, so the default should remain `diagnostic`.
- Trust scores need a clear meaning: a count can be trusted even when telemetry
  is stale, but users must be able to see that distinction.
- Action and proposal paths must remain fully gated.
- Any new class should be validated with soak tests and trust-score checks
  before it affects production answers.

### Open questions

- Should "How many active devices are online?" be `knowledge`, `diagnostic`, or
  a new `fleet_summary` class?
- Should Gate B's connectivity check pass for fleet-scoped counts when zero
  devices are online, while telemetry checks still fail independently?
- Should aggregate counts use a lighter gate set (Gate A + connectivity) and
  skip completeness, freshness, continuity, and validity?
- Should the system prompt's cautionary mandate apply only to
  telemetry-dependent diagnostics?
- Would an explicit `scope` or `needs` parameter be more reliable than
  natural-language routing?

Status: **Resolved** by the `fleet_summary` route; see §14.2.

## 14.2 Implementation plan (implemented in phases 1-4)

The following sequence keeps each change reviewable and avoids altering action
or proposal behavior while the new route is being validated.

### Phase 1 — Router classification only

**Files:** `ai/query_router.py`, `backend/tests/test_ai_query_routing.py`

- Add `MODE_FLEET_SUMMARY = "fleet_summary"` and include it in `VALID_MODES`.
- Add `FLEET_SUMMARY_PATTERNS` ahead of `OPERATIONAL_PATTERNS` for aggregate /
  inventory questions: `how many`, `count of`, `number of`, `total`,
  `list devices`, `list sites`, `which devices`, `online devices`,
  `offline devices`, `healthy devices`, `fleet status`, `device inventory`.
- Add negative patterns so telemetry questions stay diagnostic: `cpu`,
  `memory`, `disk`, `latency`, `metric`, `telemetry`, `heartbeat gap`.
- Keep the full diagnostic pipeline for now; this phase only classifies and
  echoes `routing.resolved = "fleet_summary"`.

Tests to add:
- "How many active devices are online?" -> `fleet_summary`.
- "How many devices are active?" -> `fleet_summary` (active count, not online).
- "How many devices are online?" -> `fleet_summary` (online count).
- "How many devices reported high CPU?" -> `diagnostic`.
- "Why is device X offline?" -> `diagnostic` (device scope wins).
- "How do I enroll a device?" -> `knowledge`.
- "Restart device X" -> `diagnostic` / action.

### Phase 2 — Backend gate selection

**Files:** `ai/gates/gate_b.py`, `ai/gates/envelope.py`, `ai/gates/config.py`,
`backend/src/homepot/app/api/API_v1/Endpoints/AIEndpoint.py`, new
`backend/tests/test_ai_fleet_summary_gates.py`.

- Extend `DataIntegrityGate` with `telemetry_checks` and
  `connectivity_required` options.
- For `fleet_summary`, run Gate A, Gate B connectivity only, and Gate C:
  - `B.connectivity` is an informational PASS carrying `online_count` and
    `offline_count` as evidence.
  - Completeness, freshness, continuity, validity, and the per-device digest
    are skipped.
- Skip anomaly detection and failure prediction for `fleet_summary`.
- Disable agentic / proposal handling for `fleet_summary`:
  `effective_agentic = request.agentic and routing.resolved == MODE_DIAGNOSTIC`.
- Leave the zero-fleet short-circuit unchanged: no active devices still means
  status-only refusal.

Expected result for the example query: Gate A pass, connectivity evidence pass,
Gate C pass, grounded trust, high score, no cautionary framing, and the answer
uses the existing `Online Devices` count from `site_context`.

### Phase 3 — Prompt and UI alignment

**Files:** `ai/system_knowledge.py`, `frontend/src/hooks/useAIConversation.js`,
`frontend/src/components/Dashboard/AskAIWidget.jsx`, frontend tests.

- Apply the "Actionable is no => cautionary" prompt mandate only to
  non-actionable trust modes, not to a grounded `fleet_summary` answer.
- Define active, online, offline/unknown, and healthy in the fleet-summary
  context block, using the terminology in section 14.1.
- Rename the context line `Online Devices` to
  `Online Devices (active with fresh heartbeat)` and keep `Total Active
  Devices` explicitly labelled as the enabled/visible fleet count.
- Instruct the model that a mixed active/online question should report both
  counts: "There are N active devices, of which M are online."
- Add `Fleet summary` to the mode selector alongside Auto, Knowledge, and
  Diagnostic.
- Show a `Fleet summary` chip for the new route; keep the existing trust UI for
  diagnostic answers.
- Keep `fleet_summary` answers non-actionable at the tool level: no proposal
  tools, no approval flow, even if trust is grounded.

### Phase 4 — Enable, status and acceptance

**Files:** `ai/query_router.py`, `backend/tests/test_ai_query_routing.py`,
`backend/src/homepot/app/api/API_v1/Endpoints/AIEndpoint.py`,
`docs/ai-delegation-plan.md`, this document.

- Flip `AI_FLEET_SUMMARY_ROUTING` to default on. Setting it to an off-value
  still restores the original binary knowledge/diagnostic split.
- Log `routing.resolved` and the selected gate IDs on every query.
- Add the status-matrix row in `docs/ai-delegation-plan.md` §17.7.
- Run and record the acceptance checks below after server rollout.

### Proposal-creation invariant

The current endpoint already enforces the rule that a proposal is created only
after the full validation envelope passes:

- The canonical envelope runs Gate A -> B -> C -> D -> E, then repeats Gate C
  against the final context after AI insights are appended.
- `trust.is_actionable` is true only for `MODE_GROUNDED`, which is returned only
  when no gate failed. Any gate failure selects a non-actionable mode.
- When validation is not actionable, the endpoint passes a
  `proposal_block_reason` into the agent loop; `propose_device_action` and
  `propose_fleet_action` return without appending an `ActionProposal`.
- The endpoint persists an `AIActionPlan` only when `trust.is_actionable` and
  the agent did not fall back to direct generation.
- Knowledge and direct paths never offer proposal tools. The action registry,
  RBAC check, target-online check, and honesty guard remain additional
  downstream controls.

This must remain true for compose-command proposals such as `start_program`,
`restart_service`, and `run_command`: they are registered actions, but they are
still only reachable through the fully gated diagnostic/action path.

Because `fleet_summary` skips telemetry gates, it must not be allowed to create
proposals even if its own trust label is "grounded" for inventory questions.
Phase 2 must therefore set `effective_agentic = False` for `fleet_summary` and
pass an unconditional `proposal_block_reason` such as "fleet summary is
informational; no proposals". Phase 3 must not expose a proposal/action
control on the fleet-summary route.

### Verification and rollout

- `AI_FLEET_SUMMARY_ROUTING` is on by default; an off-value restores the
  original binary split without a code change.
- `routing.resolved` and the selected gate IDs are logged on every query.
- Add a status row to `docs/ai-delegation-plan.md` section 17.7 when the work is
  implemented.
- Acceptance checks:
  1. "How many active devices are online?" returns a grounded answer without
     telemetry gate checks or cautionary framing, and states both the active
     count and the online count.
  2. "How many devices are active?" returns the active count, not the online
     count.
  3. "How many devices are online?" returns the online count.
  4. "How many healthy devices are online?" does not conflate `health_state`
     with connectivity.
  5. "Why is device X offline?" stays on the full diagnostic path.
  6. "How many devices have high memory?" stays diagnostic and still runs
     telemetry gates.
  7. "How do I enroll a device?" stays on the knowledge path.
  8. "Restart device X" keeps the existing action / proposal path, including
     full gates and a registered compose-command action.
  9. A compose-command request immediately after a fleet-summary answer still
     routes to the diagnostic/action path; the fleet-summary answer itself
     creates no proposal.

Status: **Partial**. Phases 1-4 are implemented and
`AI_FLEET_SUMMARY_ROUTING` is on by default. Server acceptance results in
§14.3 are pending rollout.

## 14.3 Acceptance results

Server acceptance is run after the phase 4 rollout. Each row records the
observed `routing.resolved` value, selected gates, and answer behavior.

| # | Check | Result |
|---|---|---|
| 1 | "How many active devices are online?" -> grounded, both counts stated | Pending rollout |
| 2 | "How many devices are active?" -> active count, not online count | Pending rollout |
| 3 | "How many devices are online?" -> online count | Pending rollout |
| 4 | "How many healthy devices are online?" -> health and connectivity distinct | Pending rollout |
| 5 | "Why is device X offline?" -> diagnostic, full gates | Pending rollout |
| 6 | "How many devices have high memory?" -> diagnostic, telemetry gates | Pending rollout |
| 7 | "How do I enroll a device?" -> knowledge | Pending rollout |
| 8 | "Restart device X" -> action path, full gates, registered action | Pending rollout |
| 9 | Compose-command request after a fleet-summary answer -> action path; fleet-summary answer creates no proposal | Pending rollout |

## 15. References

- `backend/src/homepot/app/api/API_v1/Endpoints/AIEndpoint.py` — `/ai/query`
  handler (context assembly, gates, insights, trust injection, proposals).
- `ai/system_knowledge.py` — system prompt, documentation context (fallback),
  command reference.
- `ai/doc_retriever.py` — the Tier C documentation index/retrieval
  (`DocRetriever`); configured by the `docs:` section of `ai/config.yaml`.
- `ai/tools.py` — the agent's tool set (live-data reads + proposal capture; no
  code access today).
- `ai/gates/` — the validation envelope (A–E) and `EnvelopeResult`.
- `frontend/src/components/Dashboard/AskAIWidget.jsx` and
  `frontend/src/services/api.js` (`api.ai.query`) — the chat surface and the
  mode plumbing described in § 6.1.
- [AI Documentation Retrieval](ai-doc-retrieval.md) — the implemented Tier C
  grounding layer.
- [AI Memory](ai-memory.md) — the shared ChromaDB stack.
- [Agentic AI](ai-agentic.md), [Trust & Validation Gates](ai-validation-gates.md),
  [Task Delegation](ai-delegation-plan.md), [Concurrency & Load](ai-concurrency.md).
