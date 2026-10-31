# Architecture Decision Records

Lightweight ADRs for the Homepot edge/device layer. Each record captures one
decision, its context, the options considered, and the consequences. Records are
short and standalone; the cross-cutting analysis lives in
[Device Offline Resilience & Failure Modes](../device-offline-resilience.md).

## Index

| ADR | Title | Status |
| --- | --- | --- |
| [ADR-0001](0001-command-delivery-semantics.md) | Command Delivery Semantics (at-most-once vs at-least-once) | Proposed |
| [ADR-0002](0002-agent-supervision-and-lifetime.md) | Agent Supervision & Lifetime | Proposed |
| [ADR-0003](0003-llm-provider-abstraction.md) | Pluggable LLM Providers (Local + External) | Accepted |

## Status definitions

- **Proposed** — drafted, awaiting review/decision.
- **Accepted** — agreed and in effect.
- **Superseded** — replaced by a later ADR (recorded here with a link).

## Format

Each ADR follows this structure:

1. **Status** and **date**
2. **Context** — the problem and why a decision is needed now
3. **Decision drivers** — constraints and requirements
4. **Options considered** — with trade-offs
5. **Recommendation**
6. **Consequences** — what becomes easier, harder, or more constrained
