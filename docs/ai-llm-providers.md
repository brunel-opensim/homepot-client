# LLM Providers (Ollama, OpenAI, Anthropic)

HomePot's AI can run against a **local Ollama** model or an **external**
provider (OpenAI, Anthropic). The provider is a runtime choice: it affects
latency, cost and data residency, but **not** how memory, context or the trust
gates work. Those are assembled by the backend and handed to whichever provider
is active.

| | Ollama (local) | OpenAI | Anthropic |
|---|---|---|---|
| **Runs** | On the HomePot host | Vendor cloud | Vendor cloud |
| **Data leaves server** | No | Yes | Yes |
| **Typical latency** | ~100–180 s (CPU-only host) | ~2–5 s | ~2–5 s |
| **Cost** | Free (hardware) | Pay per token | Pay per token |
| **Default** | ✅ | – | – |

!!! tip "When to use which"
    Use **Ollama** for production and any real device data: prompts never leave
    the host. Use **OpenAI/Anthropic** for demos, reviews and training where
    response time matters and the data is not sensitive.

---

## Architecture

```text
AIEndpoint.query_ai()                    backend/src/homepot/app/api/API_v1/Endpoints/AIEndpoint.py
   └── LLMService                        ai/llm.py
         └── create_llm_provider(config) ai/llm_providers.py
               ├── OllamaProvider
               ├── OpenAIProvider
               └── AnthropicProvider
```

`LLMService` loads `ai/config.yaml`, asks `ai/provider.py` for the runtime
preference, writes it into `llm.provider`, and constructs the matching provider.
Every provider implements the same three methods:

- `check_health()` — is the provider reachable?
- `generate_response(prompt, context, system_prompt)` — one-shot answer.
- `generate_with_tools(messages, tools)` — agentic tool calling.

Because the call surface is identical, the query path, memory recall, trust
gates and agent loop are **provider-agnostic**.

### Provider precedence

`ai/provider.py:get_provider()` resolves the active provider in this order:

1. `ai/provider.json` → `{"provider": "<name>"}` (runtime preference)
2. `ai/config.yaml` → `llm.provider` (default)
3. `"ollama"` (hard-coded fallback)

The runtime file is written when an admin switches providers from the Dashboard
or the API. It survives restarts, so the selected provider is sticky until it is
changed again.

---

## Providers

| Provider | Default model | Endpoint | API key env var |
|---|---|---|---|
| `ollama` | `llama3.2` | `http://localhost:11434` | – |
| `openai` | `gpt-4o-mini` | `https://api.openai.com/v1` | `OPENAI_API_KEY` |
| `anthropic` | `claude-haiku-4-5-20251001` | `https://api.anthropic.com` | `ANTHROPIC_API_KEY` |

The model ID is read from `llm.external.<provider>.model` and can be changed
without touching code. Vendor model names change over time — if a provider
returns `404 model not found`, check the vendor's model list and update the
config value.

!!! note "Model availability differs by account"
    A key can be valid while the model is not enabled for that account. Anthropic
    in particular exposes different model IDs per plan. The defaults in
    `ai/config.yaml` are known-good starting points, not a guarantee.

---

## Selecting a provider

### Dashboard (recommended)

The **AI widget header dropdown** (Dashboard → AI) lists *Local (Ollama)*,
*OpenAI* and *Anthropic*. Switching requires an **Admin** account. The widget
shows `(no key)` next to a provider that has no API key configured.

Switching is immediate: the backend resets the AI service singleton, so no
restart is needed.

### API

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/ai/provider` | Any authenticated user | Current provider, model, health, options |
| `PUT` | `/api/v1/ai/provider?provider=<name>` | **Admin** | Switch the active provider |
| `PUT` | `/api/v1/ai/provider/key?provider=<name>&api_key=<key>` | **Admin** | Store an API key for a provider |

```bash
TOKEN="<bearer token>"
BASE="https://homepot.cabera.com/api/v1/ai"

# What is active right now?
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/provider"

# Switch to OpenAI
curl -s -X PUT -H "Authorization: Bearer $TOKEN" "$BASE/provider?provider=openai"

# Store a key (alternative to .env.local; see the security note below)
curl -s -X PUT -H "Authorization: Bearer $TOKEN" \
  "$BASE/provider/key?provider=openai&api_key=sk-..."
```

`GET /provider` returns, for example:

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

### Configuration default

Set the default in `ai/config.yaml`:

```yaml
llm:
  provider: "ollama"          # "ollama" | "openai" | "anthropic"

  external:
    openai:
      model: "gpt-4o-mini"
      api_key_env: "OPENAI_API_KEY"
      base_url: "https://api.openai.com/v1"
    anthropic:
      model: "claude-haiku-4-5-20251001"
      api_key_env: "ANTHROPIC_API_KEY"
      base_url: "https://api.anthropic.com"
```

!!! warning "`ai/provider.json` wins over `config.yaml`"
    If a runtime preference already exists, editing `llm.provider` has no effect
    until `ai/provider.json` is removed or the provider is switched again. The
    same file may also contain API keys written via the API (see below).

---

## API keys and secret management

`ai/provider.py:get_api_key()` resolves a key in this order:

1. The process environment variable named by
   `llm.external.<provider>.api_key_env` (e.g. `OPENAI_API_KEY`).
2. A `KEY=value` line in `.env.local` (searched at the repo root,
   `backend/.env.local`, and the deployed path).
3. `ai/provider.json` → `api_keys.<provider>` (written by `PUT /provider/key`).

In the deployed backend, pydantic-settings loads `.env` and then `.env.local`
into the environment (`backend/src/homepot/config.py`), so keys placed in
`.env.local` are available to the AI service on startup.

### The hybrid `.env` model

| File | Owner / mode | Who writes | Purpose |
|---|---|---|---|
| `backend/.env` | `homepot:homepot`, `640` | Server admin | Production secrets |
| `backend/.env.local` | `demouser:homepot`, `664` | Deploy user | Dev/demo overrides (API keys) |

`.env.local` is loaded **after** `.env`, so it overrides. Both are gitignored.
See [Server Deployment → Credentials](server-deployment.md#credentials-gitignored-deploy-only)
for the one-time setup.

```bash
# As demouser, no sudo needed
echo 'OPENAI_API_KEY=sk-...'    >> /var/www/homepot.cabera.com/backend/.env.local
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> /var/www/homepot.cabera.com/backend/.env.local

# Restart to pick up the new environment
sudo /usr/bin/systemctl stop homepot-api
sudo /usr/bin/systemctl start homepot-api
```

!!! warning "`ai/provider.json` stores keys in plaintext"
    Keys written via `PUT /provider/key` are persisted unencrypted in
    `ai/provider.json`. That file is **gitignored** and must never be committed.
    Prefer `.env.local` (or `.env`) for managed deployments, and treat
    `provider.json` as a convenience for ad-hoc testing. Rotate a key
    immediately if it is ever exposed.

!!! note "Restart semantics"
    Keys added to `.env.local` require an API restart because the environment is
    read at process start. Switching an already-configured provider does **not**
    require a restart.

---

## Memory behaviour (provider-independent)

Memory is built in the backend and injected into the prompt before the provider
is called. **Switching providers changes the generator, not the memory.**

| Layer | What it is | Where | Provider impact |
|---|---|---|---|
| **Short-term** | Last 5 conversation turns | Client sends `history`; backend renders `[CONVERSATION HISTORY]` | None |
| **Long-term** | Semantic recall of past Q/A | ChromaDB (`ai/device_memory.py`) | None |

- **Embeddings are local.** Long-term memory uses ChromaDB's default
  `all-MiniLM-L6-v2` embedder, which runs on the HomePot host regardless of the
  answer provider. Recall quality is therefore identical across providers.
- **Knowledge answers skip memory entirely** (docs-only grounding), for every
  provider. See [AI Memory](ai-memory.md#long-term-memory-vector-recall).
- **Memory is scoped by role** (admin / site / device) before it reaches any
  provider, so no provider sees memories the caller may not.

!!! note "Short-term memory is client-supplied"
    The API accepts `history`, but the Dashboard's `AskAIWidget` does not
    currently send it, so short-term memory is effectively empty in the UI today.
    Long-term memory works regardless. See [AI Memory](ai-memory.md).

---

## Provider-specific tuning

The backend reads a single set of `llm.*` settings and each provider uses the
ones that apply to it.

### Design rationale: shared baseline, configurable ceilings

All providers share the same context building, memory recall, and trust gates.
This is deliberate: it keeps the comparison between providers fair and avoids
provider-specific code paths. A question answered by Ollama and the same
question answered by OpenAI receive the **same** context, memory, and
validation data — only the generator differs.

However, the shared values are conservative defaults tuned for the weakest
provider (Ollama on a CPU-only host with an 8K window). External models can
absorb far more, so the ceilings are **configurable**:

| Setting | Why it is shared | Why it is configurable |
|---|---|---|
| `context_budget` | Same context for all (fair comparison) | Cloud models have 128K+ windows; raising gives richer answers |
| `num_predict` (output cap) | Uniform default | Cloud models are fast; 120 tokens truncates detailed answers |
| `max_concurrent` | Single gate for simplicity | Cloud APIs handle 4-8 concurrent; 1 serializes fast calls |
| `memory.n_results` | Same recall for all | Cloud models could recall 5-10 memories without window pressure |

### Observed behaviour (three-provider comparison)

With identical settings, all three providers receive the same context and produce
the same trust score (0.333, gate B fail). But:

- **Ollama (llama3.2):** ~230 s, hallucinated "inactive / no devices" despite
  correct data in context (model comprehension degrades with large context).
- **OpenAI (gpt-4o-mini):** ~4 s, accurate fleet summary + alerts.
- **Anthropic (claude-haiku-4-5):** ~5 s, accurate fleet summary + alerts.

External models are already more accurate and ~50× faster with the same config.
Raising `context_budget`, `num_predict`, and `max_concurrent` for cloud
providers would further improve richness and throughput without affecting Ollama.

| Setting | Ollama | OpenAI | Anthropic | Notes |
|---|---|---|---|---|
| `context_window` | `num_ctx` | model default | model default | Ollama truncates first; fleet summary is restated at the end of the context to survive truncation |
| `context_budget` | caps enriched context (chars) | same | same | Shared default 2000; overridable via `external.<provider>.context_budget` |
| `num_predict` | `num_predict` | `max_tokens` | `max_tokens` | Caps **output** for all; overridable via `external.<provider>.num_predict` |
| `memory_n_results` | recalled memories | same | same | Shared default 3; overridable via `external.<provider>.memory_n_results` |
| `temperature` | ✅ | ✅ | not sent | Installed Anthropic SDK rejects it |
| `keep_alive` | ✅ | ignored | ignored | Keeps local model resident (Ollama only) |
| `max_concurrent` | ✅ | ✅ | ✅ | Overridable via `external.<provider>.max_concurrent`; per-provider gate |

!!! note "Provider-specific overrides"
    The settings above use shared defaults unless an override is set under
    `llm.external.<provider>`. Dashboard conversation history is not yet wired
    into the AI widget, so short-term memory is unavailable there.

---

## Operations and demo runbook

### Pre-demo checklist

1. `GET /provider` reports the intended provider and `"healthy": true`.
2. For external providers, confirm billing credits are available (see
   [Troubleshooting](#troubleshooting)).
3. Run one warm-up query — cloud calls are fast but the first call pays TLS and
   client setup.
4. Confirm `ai/config.yaml` still has the expected `keep_alive` (server drift is
   preserved across deploys; see [Server Deployment](server-deployment.md)).

### Switch back to local after a demo

```bash
curl -s -X PUT -H "Authorization: Bearer $TOKEN" \
  "https://homepot.cabera.com/api/v1/ai/provider?provider=ollama"
```

This is the safe default for production: no data leaves the host.

### Cost expectations

External cost is per query and depends on prompt size (context + memory +
status). For the reference host's typical diagnostic prompt, a single
`gpt-4o-mini` or `claude-haiku` query costs a fraction of a cent. A demo with
tens of queries costs well under a dollar. Check current vendor pricing before
large sessions.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `healthy: false`, query returns `AI error (OpenAI): 401` | Key missing or wrong | Set `OPENAI_API_KEY` in `.env.local`; restart |
| `429 ... no credits remaining` / `credit balance is too low` | Valid key, no billing credit | Add credits in the vendor console |
| `404 ... model: <id>` | Model not available to the account | Update `llm.external.<provider>.model` |
| `400 ... unexpected keyword argument 'temperature'` | Older Anthropic SDK | Temperature is omitted for Anthropic; upgrade the SDK if it recurs |
| `403 Admin role required` | Non-admin tried to switch/store a key | Use an Admin account |
| `503 The assistant is busy` | Concurrency gate saturated | Retry; raise `max_concurrent` (restart required) |
| Queries slow after switching to cloud | Request still routed to Ollama | Re-check `GET /provider`; `provider.json` may point elsewhere |
| `(no key)` in the Dashboard dropdown | Key not detected | Add key to `.env.local` and restart, or use `PUT /provider/key` |

!!! note "Health check semantics"
    `GET /provider` reports `healthy` from the active provider: a `models.list()`
    call for OpenAI, and a 1-token `messages.create` for Anthropic. A `false`
    usually means an auth, billing or network problem, not necessarily a bad
    provider configuration.

---

## Verifying a provider

```bash
TOKEN="<bearer token>"
BASE="https://homepot.cabera.com/api/v1/ai"

# 1. Inspect the active provider and health
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/provider" | python3 -m json.tool

# 2. Switch (Admin)
curl -s -X PUT -H "Authorization: Bearer $TOKEN" "$BASE/provider?provider=openai"

# 3. Ask a question and confirm the answer is grounded
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  "$BASE/query" -d '{"query": "What is the current fleet status?"}'
```

For an end-to-end UI check, use the Dashboard AI widget and confirm the answer
arrives, the trust banner renders, and the model named in the dropdown matches
the configured provider.

---

## Limitations and roadmap

- **Secrets in `ai/provider.json`** are plaintext (mitigated by `.gitignore`).
- **Short-term memory** is not wired into the Dashboard widget.
- **Model IDs drift** — external defaults may need updating as vendors retire
  models.
- **Data residency** — external providers receive the full assembled prompt
  (device status, alerts, memory). Do not use them with sensitive production
  data.

Related: [AI Memory](ai-memory.md) · [AI Concurrency](ai-concurrency.md) ·
[AI API Reference](ai-api-reference.md) ·
[ADR-0003](adr/0003-llm-provider-abstraction.md).
