# ADR-0001: Command Delivery Semantics

- **Status:** Proposed
- **Date:** 2026-10-24

## Context

The on-device agent polls `GET /api/v1/devices/pending`, acknowledges each
command (`POST …/ack`), executes it locally, then reports the result
(`PUT /api/v1/devices/{id}/status`). This pipeline crosses a lossy,
intermittently unavailable network (see
[Device Offline Resilience](../device-offline-resilience.md)).

Two correctness bugs exist today:

1. If the initial ACK POST fails, the agent enqueues the ACK and skips
   execution. The deferred ACK later succeeds, flipping the command
   `PENDING → SENT`, but the command is never executed — a transient network
   blip strands it in `SENT` forever.
2. If the result POST fails and the agent is killed before the result is
   enqueued, the command is stuck `SENT` with no result.

Both stem from the ACK boundary not being aligned with a durable execution
state. We need to choose the delivery guarantee before fixing the loop.

## Decision drivers

- Commands include destructive / non-idempotent operations: `run_command`,
  `run_script`, `restart`, `shutdown`. Re-running one by accident is worse than
  dropping one.
- Read-only diagnostics (`ping`, `health_check`, `list_processes`,
  `list_connections`, `status_request`) are safe to retry or drop.
- The fleet can be large; the design must not amplify server load on recovery.

## Options considered

### A. At-most-once (never double-execute; may lose)

Execute the command and persist its result to a durable journal **before**
attempting the ACK/status report. On re-poll, skip any `command_id` already
present in the "recently executed" journal.

- **Pros:** no double execution of destructive commands; simple, bounded journal.
- **Cons:** a command can be lost if the device dies after execute but before the
  result is delivered and the journal is the only source of truth; risk is
  bounded by the journal write being the commit point.

### B. At-least-once (never lose; may double-execute)

ACK only after execution completes and the result is persisted. Re-poll
re-executes any command whose execution was interrupted.

- **Pros:** no command is silently lost.
- **Cons:** a crash between "executed" and "result delivered" causes the command
  to be re-executed on the next poll — unacceptable for `restart`/`shutdown`/
  `run_command`.

### C. Exactly-once (requires backend idempotency)

Add an idempotency key to command delivery and a backend dedup table keyed on
`(device_id, command_id)`, so re-delivery is a no-op.

- **Pros:** strongest guarantee.
- **Cons:** requires backend schema + API changes and careful replay handling;
  more surface area than the immediate fix needs.

## Recommendation

Adopt **at-most-once (A)** for the edge, with the durable "recently executed
`command_id`" journal as the commit point, and treat `restart`/`shutdown` as
fire-and-forget (acknowledged at initiation). This directly fixes both bugs,
eliminates the double-execute risk for destructive commands, and keeps the
change local to the agent. Exactly-once (C) can be layered on later if fleet
telemetry shows unacceptable command loss.

## Consequences

- **Easier:** destructive commands can no longer double-run; the ACK-fail strand
  disappears; results are durable across agent crashes.
- **Harder:** we must define journal retention/eviction (bounded size) and the
  exact "commit before ACK" ordering.
- **Constrained:** read-only commands may occasionally be dropped during
  outages (acceptable); `restart`/`shutdown` are no longer expected to return a
  terminal result.
