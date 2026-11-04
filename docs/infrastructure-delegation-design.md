# Infrastructure delegation design (Phase F)

This document captures the design discussion for extending HOMEPOT's AI
delegation from **device** tasks to **infrastructure/server** tasks (database
operations, service restarts, CLI tools, configuration edits, deploys). It is a
design note only — no code has been written. It pairs with
`docs/ai-delegation-plan.md` (Phases A–E) and `docs/security-llm-providers.md`.

## Motivation

The ultimate aim of the project is to delegate tasks to the AI so it can
complete them end-to-end. Phases A–E cover device management. Operators also
spend significant time on server-side remediation: checking DB connections,
terminating blocking queries, restarting services, running migrations,
editing configuration, deploying fixes. Delegating these to the AI — with
approval gates — would close the loop on incident response.

## What we want

The AI should be able to:

- Diagnose server-side issues (DB connections, service status, disk, logs).
- Propose a remediation (terminate a blocking query, restart a service, roll
  back a config, deploy a fix).
- Execute it **only after technician approval**, with the technician reviewing
  the exact command.
- Verify the result and report back ("did it work?").

The interaction is a **back-and-forth**: AI proposes step 1 → technician
approves → AI runs it and reports → AI proposes step 2 → technician approves
→ and so on. Nothing executes without explicit approval.

## What we can reuse from Phases A–E

- Task graph + dependencies (`ai_action_step`, `depends_on_step_id`).
- Per-step approval gates (A4) — exactly the back-and-forth model.
- Dry-run (C11) — show the exact command before it runs.
- Retry with backoff (C13) — transient SSH/DB failures.
- Rollback — where feasible.
- Audit trail + outcome recording (D17).
- Autonomy controller (D16) — applicable, but with stricter thresholds.
- Agent loop closure (#771) — agent proposes, then checks status and reports.

## What is genuinely new (and dangerous)

### 1. Execution targets

Today the executor queues device commands via `create_device_command`. Server-side
execution needs new backends: SSH sessions, `psql`, `systemctl`, file edits,
deploy scripts. Each has different failure modes and partial-success semantics.

### 2. Credential scope

The AI (or the backend on its behalf) would need SSH keys, DB passwords, sudo.
This is a much bigger secret-management problem than LLM API keys. Credentials
must be:

- Brokered per-action by the backend, scoped to the specific command.
- Short-lived and revoked after use.
- Stored in a secret manager, never in git or `provider.json`.
- Never exposed to the LLM itself — the LLM picks *which* registered action
  and *which* parameters; it never sees or writes the command.

### 3. Authorization model

Device actions are operator-scoped. Server actions should be **admin-only** (or
a new "infrastructure operator" role), and destructive operations should require
**two-person approval**.

### 4. Sandboxing and blast radius

A device command affects one device. A server command can affect everything.
Required guardrails:

- Read-only commands at lower approval tiers; write/destructive commands gated
  harder.
- Per-command allow-lists (e.g. only diagnostics, never `DROP`/`DELETE`).
- Time-boxed credentials.
- Honest rollback reporting ("not reversible" where applicable).

### 5. Verification

"Did it work?" is harder for server ops. Health endpoints, service status, and
log tailing become the verification step. The existing postcondition framework
(`ai_ops/verifier.py::_evaluate_postconditions`) can be extended.

### 6. Rollback limits

Config files and deploys can be reverted. Terminated queries and dropped tables
cannot. The rollback machinery must report "not reversible" honestly.

## Proposed action registry (infrastructure)

A separate registry alongside `ai/actions.py`, with risk tiers:

| Tier | Examples | Approval | Reversible |
|------|----------|----------|------------|
| I1 (read-only diagnostics) | `check_db_connections`, `tail_logs`, `service_status`, `disk_usage` | Auto or single | N/A (read-only) |
| I2 (reversible changes) | `restart_service`, `reload_config`, `clear_cache` | Single approval | Yes |
| I3 (destructive / irreversible) | `terminate_backend`, `run_migration`, `deploy` | Approval + confirmation (possibly two-person) | No |

Each action declares: command template, target host/service, reversibility,
verification check. The existing plan/step/approval/audit machinery handles the
rest.

## The back-and-forth flow

1. Technician: "The DB is slow, investigate."
2. AI runs I1 diagnostics (auto or approved), reports findings.
3. AI proposes I2/I3 remediation with exact command in dry-run preview.
4. Technician approves step 1.
5. AI executes, verifies, reports: "Terminated blocking query PID 4821; DB
   connections dropped from 180 to 12; latency back to normal."
6. If step 2 is needed, AI proposes it; technician approves; repeat.

This maps directly to per-step approval (A4) and the agent loop closure work.

## What we should NOT do

- **Give the AI standing SSH/DB credentials.** Credentials must be brokered
  per-action, scoped, and revoked.
- **Let the AI generate arbitrary shell.** Commands come from a registered,
  reviewed allow-list. The LLM picks which action and which parameters; it
  never writes the command itself.
- **Auto-execute infrastructure actions.** Even at Level 3 autonomy, keep a
  human in the loop for I2/I3. Level 3 auto-execute should be reserved for
  read-only diagnostics at most.
- **Skip the soak test.** Validate the delegation loop on the safer device
  surface first.

## Pros and cons

### Pros

- Closes the loop on incident response; reduces on-call toil.
- Reuses the proven orchestration, approval, audit, and rollback machinery.
- Per-step approval gives technicians fine-grained control.
- Dry-run shows exact commands before execution.

### Cons

- Much larger blast radius than device actions; a mistake can take down the
  whole site or corrupt data.
- Credential management is a significant new security surface.
- Rollback is limited for destructive operations.
- Verification is harder and less deterministic than device health checks.
- Requires a security review and likely two-person approval for I3.

## Relationship to existing work

- `docs/security-llm-providers.md` — the secrets and data-leakage discussion.
  Infrastructure credentials are an even bigger version of the same problem.
- `docs/real-device-ai-soak-test.md` — validate the delegation loop on devices
  first.
- `docs/ai-delegation-plan.md` §17 — Phases A–E (device delegation).

## Recommended sequence

1. Complete the device soak test (Brunel Device 001) and earn the first
   autonomy levels. This validates the orchestration loop on a safer surface.
2. Decide the credential broker (secret manager, short-lived tokens,
   per-action scoping).
3. Define the allow-list of infrastructure commands with a security review.
4. Design the I1/I2/I3 registry and executor backend.
5. Implement behind a feature flag, admin-only, with two-person approval for I3.
6. Soak test on a non-production server before any real use.

## Status

**Design only.** No code written. Tracked as a future phase (Phase F) pending
the device soak test and a security review of the credential broker.
PYEOF
echo written