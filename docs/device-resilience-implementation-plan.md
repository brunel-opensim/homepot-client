# Device Resilience — Review & Implementation Plan

This document records the outcome of the review of
[Device Offline Resilience & Failure Modes](device-offline-resilience.md) and the
first two ADRs
([ADR-0001](adr/0001-command-delivery-semantics.md),
[ADR-0002](adr/0002-agent-supervision-and-lifetime.md)), and turns the confirmed
gaps into a prioritised implementation backlog. It is the starting point for the
next implementation PR(s); work here should be split into small, independently
reviewable PRs rather than one large change.

## Review outcome

The analysis and both ADRs were reviewed line-by-line against the codebase.
**Verdict: accurate** — every technical claim was verified, and CI is green
(MkDocs `--strict`, code quality, and the full test matrix). Highlights of the
verification:

- Gap 1 (no supervision) — `user_app/electron/main.ts` `child.on('exit')` logs
  and clears the handle but never restarts; `watchdog_enabled: true` is a no-op
  on Windows (`_watchdog_loop` only calls `systemd.daemon.notify`).
- Gap 2 (ACK-then-execute strand) — confirmed in `pending_commands_loop`: a
  failed ACK enqueues the ACK and `continue`s (skips execution), so a later
  `retry_flush_loop` flips the command `PENDING → SENT` without it ever running.
- Gap 3 (shutdown race) — `killAgent()` SIGKILLs after **3 s** while the agent's
  `shutdown_timeout_seconds` is **30 s**.
- Gap 5 (clock skew) — `agent_service.update_heartbeat` persists
  `payload.timestamp` (device clock); `_compute_connectivity` compares it to
  server `datetime.now(utc)`.
- Gap 6 (permanent errors retried forever) — `post_json` treats every non-2xx
  identically and `RetryQueue` has no terminal state.
- Gap 7 (unbounded queue) — no size/TTL cap, full-file rewrite per `enqueue`,
  deterministic `30·2ⁿ` backoff with no jitter.
- Gap 8 (no local health) — the Electron-spawned agent runs `ipc_enabled: false`.
- Gap 9 (sleep/hibernate) — no `pool_pre_ping` anywhere in the agent client.
- The "What already survives" table and the recovery-path flows
  (`waitForOffline` 12 s cap, `unpair-<deviceId>` idempotency, "server
  revocation pending" fallback) all match their cited source.

## Review refinements (fold into the analysis/ADRs)

Four non-blocking, one-line refinements to apply to
`device-offline-resilience.md` / ADR-0001 before or alongside implementation:

1. **Cadence precision** — the stale-devices section says the agent "continues
   polling `…/pending` and POSTing heartbeats" on a "~60s" cadence. Live-log
   analysis shows a single reject per minute — that is the **command poll**
   (60 s standalone / 15 s Electron), *not* the 30 s heartbeat. Suggested
   wording: *"…visible in the live log as a device auth-rejecting on a fixed
   ~60s cadence — the command poll (30s heartbeat rejects would also appear if
   that loop were still active)."*

2. **Summary/ADR alignment** — "Recommended resilience layers" item 2 says
   "Exactly-once / at-most-once commands" but ADR-0001 settles on **at-most-once**
   (exactly-once deferred). Reword the summary to "at-most-once command delivery
   (durable executed-command journal)".

3. **`{command_id}` disambiguation** — ADR-0001 writes
   `PUT /api/v1/devices/{id}/status`; the path segment is the **command** id
   (`PUT /api/v1/devices/{command_id}/status`), and the ACK endpoint is
   `POST /api/v1/devices/{device_id}/commands/{command_id}/ack`.

4. **`main.py` disambiguation** — the stale-device/command-expiry loops live in
   `backend/src/homepot/main.py` (entrypoint), not the FastAPI app
   `backend/src/homepot/app/main.py`. Cite them as `homepot/main.py`.

## Implementation roadmap

Ordered by impact. Each item lists the gap it closes, the change, the files
touched, and acceptance criteria. Gaps are numbered as in
`device-offline-resilience.md`.

### W1 — Error classification: stop retrying permanent failures (gap 6) — **first PR**

A removed/unpaired device whose agent is still running currently retries
forever (this is the live `DEVICE-5XE4-28KV-3PGB` noise). This is the smallest,
highest-value change and the natural first PR.

- **Change:** classify request failures as *transient* vs *permanent* at the
  agent HTTP layer (`post_json`, `post_json_parsed`, `get_json`,
  `ack_command_backend`, `update_command_status`, `fetch_device_permissions`).
  - Permanent → HTTP `401`/`403` (revoked credentials), `404` (unpaired/removed),
    `409` (conflict). Do **not** enqueue for retry; log once, set a terminal
    "removed from backend" state, and stop the affected loop(s).
  - Transient → `5xx`, `429`, `408`, network errors, timeouts, SSL drops. Keep
    the existing enqueue + exponential-backoff behaviour.
- **Files:** `backend/src/homepot/agent/real_device_agent.py`,
  `backend/src/homepot/agent/utils/command_poller.py`,
  `backend/src/homepot/agent/utils/retry_queue.py` (only if a terminal-state
  flag is stored here), plus agent tests.
- **Acceptance criteria:**
  - A device unpaired/removed on the Dashboard stops producing auth-reject log
    lines within one poll cycle of the change (≤60 s standalone, ≤15 s Electron).
  - A transient outage (server down / 5xx / timeout) still enqueues and recovers
    unchanged.
  - Unit test coverage for each permanent code (`401/403/404/409`) and a
    transient case (`500`, timeout).

### W2 — Electron agent supervisor (gap 1, ADR-0002)

- **Change:** Electron restarts the agent on *unexpected* exit with crash-loop
  backoff (e.g. 3 restarts / 5 min, then surface an error), and skips the
  restart when the stop was intentional (unpair / re-enrol / quit). Requires an
  intentional-stop signal from the renderer to `main.ts`.
- **Files:** `user_app/electron/main.ts` (`startAgentProcess`, `killAgent`),
  `user_app/src/views/DeviceInfo.tsx` and `SetupWizard`/`ClaimDevice` (signal the
  intentional stop), `user_app` IPC/preload if a new channel is added.
- **Acceptance criteria:** a killed/crashed agent comes back automatically; an
  unpair/quitting app does *not* resurrect the agent; crash-loop cap is honoured.

### W3 — Command delivery semantics (gap 2, ADR-0001)

- **Change:** adopt **at-most-once** with a durable "recently executed
  `command_id`" journal. Persist the result (or the executed `command_id`)
  *before* reporting, and skip any `command_id` already in the journal on
  re-poll. This fixes the ACK-fail strand and eliminates double-execution of
  destructive commands.
- **Files:** `backend/src/homepot/agent/real_device_agent.py`
  (`pending_commands_loop`, `command_result_loop`), a new durable journal helper,
  plus agent tests.
- **Acceptance criteria:** the "acknowledged but never executed" case can no
  longer strand a command in `SENT`; a `restart`/`shutdown`/`run_command` is
  never executed twice across crashes/re-polls.

### W4 — Shutdown integrity (gap 3)

- **Change:** align the Electron kill grace period with the agent's
  `shutdown_timeout_seconds` (30 s), or let the agent self-exit and have Electron
  *wait*, so the graceful final-OFFLINE heartbeat (`send_final_offline_heartbeat`)
  lands before SIGKILL.
- **Files:** `user_app/electron/main.ts` (`killAgent`), optionally the agent
  shutdown path.
- **Acceptance criteria:** app quit reliably flips the device OFFLINE immediately
  (no 300 s window) when the network is up.

### W5 — `restart`/`shutdown` fire-and-forget (gap 4)

- **Change:** acknowledge `restart`/`shutdown` as executed at *initiation*
  (`_system_control` already returns `"{type} initiated"`), and stop expecting a
  terminal result — so a host that dies mid-report no longer strands the command
  in `SENT`.
- **Files:** `backend/src/homepot/agent/utils/command_poller.py`
  (`_system_control`, `process_command`).
- **Acceptance criteria:** a reboot/power-off that races the report POST resolves
  to a non-stranded terminal state.

### W6 — Clock authority for `last_heartbeat_at` (gap 5)

- **Change:** set `last_heartbeat_at` to server receive time on the heartbeat
  endpoint (keep `payload.timestamp` for display), so connectivity cannot be
  corrupted by device clock drift. Optionally flag large client/server skew.
- **Files:** `backend/src/homepot/app/services/agent_service.py`,
  `backend/src/homepot/app/repositories/agent_repository.py`,
  `backend/src/homepot/app/api/API_v1/Endpoints/AgentHeartbeatEndpoint.py`.
- **Acceptance criteria:** a device with a skewing clock is reported online/
  offline by server time; emulator and real-device paths are consistent.

### W7 — Bounded, jittered, prioritised retry (gap 7)

- **Change:** cap queue length, add per-item TTL, dedupe by `(url, key)`, add
  random jitter to `30·2ⁿ` backoff, and prioritise command ACK/status over stale
  telemetry/heartbeat on reconnect (telemetry is superseded anyway).
- **Files:** `backend/src/homepot/agent/utils/retry_queue.py`,
  `backend/src/homepot/agent/real_device_agent.py` (`retry_flush_loop`).
- **Acceptance criteria:** bounded disk growth during long outages; no lockstep
  reconnect burst (jitter verified); stale telemetry does not delay command
  traffic.

### W8 — Local health signal (gap 8)

- **Change:** expose a minimal local health signal (re-enable localhost IPC, or a
  small status file the agent maintains) so the renderer can render a three-way
  state: *online / server-unreachable-but-agent-up / agent-down*.
- **Files:** `user_app/electron/main.ts` (`ipc_enabled`), the agent IPC/status
  writer, `user_app` status view.
- **Acceptance criteria:** during a server outage the app distinguishes
  "agent healthy, server unreachable" from "agent crashed".

### W9 — Wake / network-change reconnection (gap 9)

- **Change:** on `powerMonitor` resume and/or network-interface change, signal the
  agent to reset its HTTP client and immediately heartbeat, and refresh the WNS
  channel.
- **Files:** `user_app/electron/main.ts` (`powerMonitor`), the agent client.
- **Acceptance criteria:** resume from sleep produces at most one heartbeat gap;
  no stale keep-alive connection errors.

## Suggested first PR — W1 detail

The single highest-value, lowest-risk change is **error classification (W1)**.
It directly eliminates the live stale-device log spam (a removed device polling
forever under dead credentials) and is a local agent-only change with no
schema/API surface.

Suggested shape:

1. Add a classification helper (e.g. `is_permanent_status(code: int) -> bool`
   returning `True` for `{401, 403, 404, 409}`).
2. Thread the classification through `post_json` / `post_json_parsed` / `get_json`
   so callers can distinguish *transient* (enqueue + backoff) from *permanent*
   (terminal state, no retry).
3. On a permanent failure, log once at ERROR, record a "removed from backend"
   terminal flag, and stop the loop(s) that depend on the dead credential.
4. Verify against the stale device `DEVICE-5XE4-28KV-3PGB` (if still running):
   after the new binary is on that device it must stop emitting auth-reject lines
   within one poll cycle.

Dependencies and note for sequencing: W2 (supervisor) and W3 (delivery
semantics) are the next largest items and are independent of W1; W4/W5 are small
and pair naturally with W2/W3 respectively.
