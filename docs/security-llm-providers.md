# Securing LLM providers and device data

This document captures the security discussion for HomePot's AI stack: how we
keep LLM API keys secret, how we prevent device data from leaking to
third-party providers, and the trade-offs we accepted for the demo. It pairs
with the roadmap in `docs/ai-delegation-plan.md` (Phase D, item 16).

## Current state

- The active provider is selected at runtime via `ai/provider.json` (admin-only
  via `PUT /api/v1/ai/provider`) and falls back to `ai/config.yaml`
  (`llm.provider`). Valid providers: `ollama`, `openai`, `anthropic`.
- Ollama runs locally on the server (CPU-only, no data leaves the host).
- OpenAI (`gpt-4o-mini`) and Anthropic (`claude-haiku-4-5-20251001`) are the
  cloud options for speed.
- API keys come from environment variables (or `.env.local` / `provider.json`
  in dev). `ai/provider.json` is gitignored.
- No commercial API keys are committed to git; demo secrets live server-side only.

## What actually leaves the server

When a technician asks the AI a question, `ContextBuilder` assembles a prompt
containing device metadata, metrics, error logs, config history, fleet
summaries and memory-retrieved incidents. That entire string is sent to the
selected provider. The leakage surface is **whatever context the agent gathers
for a query**, not just the user's question.

## Threats

1. **Secrets exposure** — keys in git, config, logs, or error messages.
2. **Device data to a third party** — metrics, logs, config values, device IDs
   and memory incidents may contain operational details a customer does not
   want a cloud provider to see.
3. **Cross-tenant leakage** — in a multi-site deployment, context for one
   site must never bleed into a query scoped to another (per-device RBAC
   already exists; the agent loop must honour it).
4. **Logs and audit trails** — prompts/responses captured for debugging are
   themselves a leakage channel.
5. **Provider retention and training** — whether the provider stores or trains
   on submitted data.
6. **Cost and abuse** — an unbounded tool loop can generate large cloud bills.

## Options considered

### A. Secrets hygiene (low effort — do always)

- Keys only via environment variables or a secret manager (AWS Secrets Manager,
  GCP Secret Manager, HashiCorp Vault); never in git.
- Separate keys per environment (demo vs. production) with least privilege.
- Startup validation that refuses to boot (or warns loudly) when a cloud
  provider is selected but has no key.
- Documented key rotation procedure.

Pros: cheap, removes the biggest avoidable risk, no impact on responses.
Cons: does not protect device data once a key is present.

### B. Data minimisation before cloud calls (medium effort, high value)

- A redaction layer in `ContextBuilder` / tool output that strips or hashes
  device identifiers, IP addresses and customer-specific config values before
  the prompt is sent to an external provider.
- Send summaries/aggregates to cloud; raw telemetry only to local Ollama.
- Per-field allow-list so the provider only receives what it needs.

Pros: directly limits leakage.
Cons: large, error-prone change; risks degrading answer quality if over-applied;
hard to test without a real customer.

### C. Provider routing policy (medium effort)

- Default to Ollama for any query whose context touches device data; allow
  cloud only for generic/knowledge queries or when an admin explicitly opts in.
- Per-site or per-device "cloud-allowed" flag.
- Record which provider handled each query in the audit trail.

Pros: keeps the safe default while preserving cloud speed where it is safe.
Cons: routing heuristics can be wrong; adds branching to the query path.

### D. Operator transparency and consent (low-medium effort)

- UI badge showing "Answered by OpenAI" vs "Answered locally".
- Admin-only provider switching (already the case) with a confirmation that
  names the data that will be sent.
- Provider data-retention notice in the admin settings page.

Pros: no impact on responses; builds trust.
Cons: does not by itself prevent leakage.

### E. Provider-side controls (configuration, not code)

- Use provider endpoints with zero-data-retention / no-training options.
- Short retention, disable prompt logging at the provider.
- Sign data-processing agreements before any real customer data flows.

### F. Outbound DLP (higher effort)

- Scan the assembled prompt for patterns (IPs, serial numbers, emails) and
  block or redact before sending.
- Audit log of every outbound prompt hash for forensics.

## Decision for this project

The demo runs on Ollama by default and the cloud providers are opt-in by an
admin. We therefore chose a **two-tier** approach that does not degrade demo
responses:

1. **Always do A** — secrets hygiene and startup validation.
2. **Do D** — provider transparency in the UI and audit trail.
3. **Defer B, C (routing) and F** until a real customer asks for them. They are
   documented here as the production path. C in particular would slow the demo
   down by forcing Ollama on device queries, which defeats the purpose of having
   cloud providers available.

B is the most valuable production improvement and should be the first thing
implemented for a real deployment; F is the last.

## What is implemented now

- `ai/provider.py::validate_provider_secrets()` — checks the active provider
  has a usable key and logs a clear error when it does not (called at startup,
  non-blocking).
- The query response carries `provider` so the UI can show which model answered.
- Each AI query is audited with the provider name.

## What is deliberately not implemented (and why)

- **No redaction layer (B).** Applying it naively would strip the context the
  LLM needs and degrade answer quality. It needs a per-field allow-list designed
  with a real customer's data map.
- **No forced routing to Ollama (C).** Would make the demo slower and removes
  the value of having cloud providers configured.
- **No outbound DLP (F).** Pattern-based scanning has a high false-positive rate
  on device identifiers and would block legitimate queries.

## Production checklist (before real customer data)

- [ ] Move keys from `.env.local`/`provider.json` into a secret manager.
- [ ] Enable provider zero-data-retention / no-training modes and sign DPAs.
- [ ] Implement B (redaction) with a per-customer allow-list.
- [ ] Add per-site "cloud-allowed" flags (C) and route accordingly.
- [ ] Add outbound DLP (F) as a safety net.
- [ ] Review audit logs for provider usage and prompt hashes.
- [ ] Confirm cross-tenant isolation: no query context crosses site boundaries.
PYEOF
echo written