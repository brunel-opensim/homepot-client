# Trustworthy AI delegation: from code assistant to device manager

This document captures a design discussion comparing two AI collaboration
models — an AI coding assistant (OpenCode) acting on a codebase, and HOMEPOT's
AI delegation stack acting on physical devices — and what each can learn from
the other. It is written as a design note and potential publication seed.

## 1. Two collaboration models

### 1.1 The code assistant (OpenCode / Beam)

When given a task, the assistant:

1. **Plans internally** — decides which files to read, what to change, in what
   order. There is no persisted plan object; the plan lives in reasoning.
2. **Acts directly** — calls tools (read, edit, shell, grep, …) and observes
   results. No approval gate per step.
3. **Iterates** — if a command fails or tests break, fixes and re-runs.
   No formal retry/backoff; just a loop.
4. **Verifies** — runs quality gates (mypy, tests, lint) and reports pass/fail.
5. **No rollback machinery** — fixes forward or reverts via git.
6. **Stateless across sessions** — conventions live in `AGENTS.md` and the
   repo; "memory" is the conversation plus files.

The assistant asks the human only when something is genuinely ambiguous or
risky (merging, destructive ops). Otherwise it just acts.

### 1.2 HOMEPOT's AI delegation stack

1. **Gather context** — the agent calls read-only device tools (status,
   metrics, logs, memory).
2. **Propose** — produces an `ActionProposal`, persisted as an `AIActionPlan`
   with steps, status `pending_approval`.
3. **Human gate** — a technician must approve (plan-level, and per-step for
   T3/disruptive actions).
4. **Execute** — separately, via "Execute" / "Execute & wait", queueing device
   commands through the existing command path.
5. **Verify** — the reconciler checks command results, postconditions,
   retry/rollback.
6. **Record outcome** — `AIActionOutcome` feeds reliability metrics and autonomy
   levels.
7. **Earn autonomy** — over many verified runs, an action type can be promoted
   from Level 0 (suggest) to Level 3 (auto-execute).

## 2. The correlation

| Dimension | Code assistant | HOMEPOT AI |
|---|---|---|
| Context gathering | Read files, grep, shell | Device tools (status, metrics, logs, memory) |
| Planning | Internal reasoning, no persisted artifact | Persisted plan with steps, dependencies, params |
| Approval | None — acts, human reviews the PR | Per-plan + per-step human approval |
| Execution | Direct tool calls | Command queue → device agent → async reconcile |
| Verification | Run tests/lint, observe output | Verifier checks command status + postconditions + outcome row |
| Rollback | Fix forward / git revert | Snapshot-based config rollback, per-step |
| Risk classification | Judgment ("this is risky, I'll ask") | Formal tiers T1/T2/T3 with enforced gates |
| Learning over time | None — stateless sessions | Reliability metrics + autonomy levels earned from outcomes |
| Memory | Conversation + `AGENTS.md` | Short-term history + ChromaDB long-term memory |
| Audit trail | Git history | `ai_approval`, `ai_action_outcome`, audit log events |

## 3. The key insight

HOMEPOT's autonomy levels (0 → 1 → 2 → 3) are a **formalization of exactly
what the code assistant does informally**:

- **Level 0 (suggest)** — describe what *should* be done. The assistant never
  does this; it always acts.
- **Level 1 (propose, human approves)** — propose a change and wait for "go."
  This is how the assistant handles risky edits.
- **Level 2 (execute if trust ≥ threshold)** — just do it if confident, but
  still show the human. How the assistant handles routine edits.
- **Level 3 (auto-execute)** — do it silently and report after. How the
  assistant handles trivial fixes.

The difference: the assistant uses **judgment**; HOMEPOT uses **measured
evidence** (verified outcomes). The soak test on a real device is how HOMEPOT
"earns" the right to act the way the assistant does.

## 4. Why the gating differs

1. **Blast radius.** Assistant mistakes affect code in a dev repo — recoverable
   via git. HOMEPOT mistakes affect physical devices and (in Phase F) servers —
   potentially irreversible.
2. **Operators.** The assistant has one approving user. HOMEPOT has multiple
   technicians with different roles.
3. **Reversibility.** Code edits are trivially reversible. Device restarts and
   DB operations are not.
4. **Compliance.** "The AI restarted a device" needs an audit trail; "the AI
   edited a file" doesn't, beyond git.

The gating intensity matches the consequence. HOMEPOT is more careful because
it has to be.

## 5. Where HOMEPOT could learn from the code assistant

- **Faster iteration for low-risk reads.** The assistant does not ask permission
  to read files. HOMEPOT's T1 actions (health_check, etc.) could skip approval
  entirely once trust is established — that is what Level 2/3 is for.
- **Less ceremony for proposals.** The proposal → approve → execute flow is
  heavy. For Level 3 actions it should collapse to "done, here's what I did."
- **Conversational memory.** The assistant carries context across a session
  naturally. HOMEPOT's agent has memory tools but the delegation loop
  (propose → execute → verify → report) is still clunky — that is what Phase 2
  (agent loop closure) and the execute-and-wait button are starting to fix.

## 6. Where the code assistant could learn from HOMEPOT

- **Verification.** The assistant runs tests and calls it done. HOMEPOT
  actually checks the real-world outcome and records it. The assistant could be
  more rigorous about verifying that changes actually work, not just that tests
  pass.
- **Rollback.** The assistant does not snapshot before risky edits. HOMEPOT's
  snapshot-before-execute is a good pattern.
- **Audit trail.** The assistant's changes are tracked in git, but the
  *reasoning* and *alternatives considered* live in conversation, not in the
  repo. A decision log would help.
- **Risk classification.** The assistant uses judgment ("this is risky, I'll
  ask"). A formal tier system with enforced gates would make the judgment
  explicit and auditable.

## 7. The meta-point: trust relationships

Both systems work well because of a **trust relationship** between human and AI:

- The assistant works well because the user trusts it enough to act, and the
  assistant asks when uncertain.
- HOMEPOT is building the machinery to make that same trust relationship work
  between **technicians and the AI**, but with **evidence instead of judgment**.

The gap the user identified: HOMEPOT's delegation loop still has too much
friction for the "just do it and tell me" case. That is the Phase 2/3 work —
collapsing the loop as trust is earned. The soak test on Brunel Device 001 is
the first time that trust gets earned on real hardware.

## 8. Why this matters for trustworthy AI

Most "trustworthy AI" discussions focus on model-level properties: accuracy,
fairness, explainability. HOMEPOT's contribution is different — it is about
**operational trust**: how an AI earns the right to act on real systems, with
measurable evidence, graduated autonomy, and honest reporting of failures.

The key design choices that make this trustworthy:

1. **Autonomy is earned, not granted.** Levels 0–3 require measured outcomes,
   not configuration. You cannot flip a switch to make the AI autonomous.
2. **Verification is mandatory.** Every action produces an outcome row. "It
   probably worked" is not acceptable; "verified: true" is.
3. **Rollback is honest.** The system reports "not reversible" where
   applicable. It does not pretend to undo what it cannot undo.
4. **Risk tiers are enforced, not advisory.** T3 actions pause in
   `awaiting_approval` regardless of what the AI thinks.
5. **The human can always intervene.** Cancel, reject, and per-step approval
   are always available. Autonomy narrows the gate; it never removes it
   entirely (except read-only diagnostics at Level 3).
6. **The audit trail is complete.** Every proposal, approval, execution,
   outcome, and retry is recorded with actor and provenance.

This is the difference between "AI that is trusted" and "AI that has earned
trust." The first is a configuration choice; the second is an empirical process.

## 9. Conclusion

The code assistant and HOMEPOT's AI are solving the same problem at different
scales: how to let an AI act usefully while keeping the human in control of
consequences. The assistant does it informally through judgment and
conversation. HOMEPOT does it formally through measurement and graduated
autonomy. Each has something to learn from the other, and the convergence point
is the same: an AI that acts confidently on routine tasks, asks on uncertain
ones, and reports honestly on everything.
PYEOF
echo written