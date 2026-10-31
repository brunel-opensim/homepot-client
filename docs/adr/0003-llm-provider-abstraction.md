# ADR-0003: Pluggable LLM Providers (Local + External)

- **Status:** Accepted
- **Date:** 2026-10-31

## Context

The AI service originally talked to a single local **Ollama** model. That is
the right default for production: prompts, device status and recalled memory
never leave the host. But on the reference CPU-only server a diagnostic answer
takes ~100–180 s, which is painful for demos, reviews and training.

We need faster answers for non-sensitive sessions **without** forking the AI
pipeline. Memory, context assembly, trust gates, query routing and the agent
loop are substantial and must not be duplicated per provider.

## Decision drivers

- **Latency for demos** — external models answer in seconds.
- **Data residency** — production must be able to keep everything on-premise.
- **Cost control** — external usage must be opt-in and easy to turn off.
- **Single pipeline** — memory, context, gates and agent must stay shared.
- **Operational simplicity** — switch at runtime; no redeploy.
- **Access control** — only admins may switch providers or set keys.

## Options considered

1. **Ollama only (status quo).** Simple and private, but too slow for demos.
2. **Cloud only.** Fast, but sends device data off-host and adds a hard
   third-party dependency.
3. **Pluggable abstraction with runtime selection** (chosen). A common
   `LLMProvider` interface, three implementations, and a runtime preference
   file; the rest of the AI pipeline is unchanged.
4. **Per-provider code paths.** Maximum flexibility, but duplicates memory,
   context and gate logic and drifts over time.

## Recommendation

Adopt option 3:

- `ai/llm_providers.py` defines `LLMProvider` and the Ollama, OpenAI and
  Anthropic implementations.
- `ai/llm.py` (`LLMService`) delegates to the active provider.
- `ai/provider.py` stores the runtime choice in `ai/provider.json`, falling back
  to `llm.provider` in `ai/config.yaml`, then `ollama`.
- Provider selection and key storage are exposed through admin-only endpoints:
  `GET/PUT /api/v1/ai/provider` and `PUT /api/v1/ai/provider/key`, plus a
  Dashboard dropdown.
- Memory remains **provider-independent**: it is assembled in the backend and
  embedded locally with ChromaDB (`all-MiniLM-L6-v2`).

## Consequences

**Easier**

- Demos and reviews get second-level responses by switching to a cloud model.
- Production keeps the private local default; switching back is one call.
- New providers can be added behind the same interface.
- Memory, context, gates and the agent loop have one implementation.

**Harder / risks**

- API keys must be managed. `ai/provider.json` stores keys in plaintext when set
  via the API, so it is gitignored and treated as a testing convenience;
  `.env.local` is preferred for managed deployments.
- External providers receive the full assembled prompt, including device status
  and recalled memory — acceptable for demos, not for sensitive production data.
- Provider-specific limits (output cap, concurrency, recall depth) are still
  uniform and conservative; tuning them per provider is a follow-up.
- Vendor model IDs drift and must be kept current in `ai/config.yaml`.

**Follow-ups**

- Per-provider output cap, concurrency and recall depth.
- Send conversation history from the Dashboard widget (short-term memory).
- Key rotation guidance and, if needed, encrypted key storage.

See [LLM Providers](../ai-llm-providers.md) for the operator-facing guide.
