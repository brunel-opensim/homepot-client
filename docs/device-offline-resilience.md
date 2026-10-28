# Device Offline Resilience & Failure Modes

How the **User App** (Electron) and the **on-device agent** (Python
`homepot.agent`) behave when connectivity to the Dashboard/backend degrades or
fails, and what must change so a real Windows device stays healthy through
those events.

This is an analysis document, not a design spec. The decisions that follow from
it are tracked as ADRs (see [Decisions](#decisions) below).

## Scope

We care about two distinct processes that must both "survive" an outage:

- **The User App** — the tray application that provisions the device, renders
  status, and *spawns the agent as a child process*.
- **The on-device agent** — the runtime that heartbeats, uploads telemetry,
  polls and executes commands against the host OS.

The communication paths that can break:

| Path | Representative failure modes |
| --- | --- |
| Agent → backend (heartbeat / telemetry / command results) | Wi-Fi drop, DHCP, DNS, proxy/VPN, firewall, server down, HTTP 5xx, SSL handshake drops |
| Backend → agent (commands) | Push (WNS/MQTT) unavailable → falls back to polling; server down = no commands |
| App (renderer) → backend (status pages) | Same network path, but a **separate** HTTP client with its own timeout |
| App (Electron) → agent | Local child process + a JSON config file; no local health IPC today |

## What already survives

These protections are real and should be preserved and built on:

| Mechanism | Where | Notes |
| --- | --- | --- |
| File-backed retry queue with exponential backoff | `agent/utils/retry_queue.py`, `retry_flush_loop` | Failed heartbeat/telemetry/command-status/ACK payloads persist to disk and retry (30s → 60m cap) |
| Persistent device identity | `agent/identity.py` | Survives restart **and** re-enrolment; no device-id churn after a crash |
| Credentials survive network errors | `user_app/src/services/api.ts` `verifyDeviceCredentials` | Returns `true` on network failure; only clears on explicit 401/404 |
| Idempotent unpair | `api.ts` `unpairDevice` | 404 treated as "already unpaired" |
| Verified unpair with local-reset fallback | `user_app/src/views/DeviceInfo.tsx` `handleUnpair` | Stops the agent, confirms OFFLINE with the Dashboard, then clears creds; a network failure falls back to "server revocation pending" |
| Fail-closed command permissions | `command_poller.py` `fetch_device_permissions` / `_check_permission` | Backend unreachable → `None` → privileged commands refused; cached grants only after a prior successful fetch |
| Graceful offline signal + server-side sweep | `send_final_offline_heartbeat`; `main.py` `_run_stale_device_detection_loop`; `_compute_connectivity` | Immediate OFFLINE on clean stop; otherwise `device_offline_threshold` (default 300s) |
| Backend command expiry | `main.py` `_run_command_expiry_loop`; `database.py` `expire_stale_commands` | Stale `PENDING`/`SENT` commands expire after TTL (default 300s), so queues for dead devices drain |
| Launch-at-login (packaged builds) | `user_app/electron/main.ts` `whenReady` | A reboot re-launches the app, but only **after a user logs in** — it is a login item, not a boot-time service |
| Renderer timeouts + cache | `api.ts` `fetchWithTimeout`; `telemetryCache.ts` | 15s abort; in-memory last-known snapshot for instant render |

## Stale devices (both directions)

A "stale" pairing is one where the Dashboard's view and the on-device runtime
disagree. Both directions are **expected** outcomes of soft deletion; the goal is
that they terminate cleanly instead of looping.

**Direction A — device removed from the DB, agent still running.** An operator
deletes/unpairs a device on the Dashboard while the Windows device keeps
running. The agent continues polling `GET /api/v1/devices/pending` and POSTing
heartbeats, and every request is rejected with 401/404 ("…not found in DB").
Today the agent treats that rejection exactly like a network error — it logs and
retries with backoff *forever* (see gap 6). This is visible in the live log as a
device auth-rejecting on a fixed cadence (~60s).

**Direction B — agent stopped, Dashboard still lists the device.** The device
process dies (crash, app quit, host power-off) while its record remains on the
Dashboard. The record is preserved (soft delete/unpair) and only flips to
OFFLINE after `device_offline_threshold` (default 300s); commands queued for it
stay `PENDING`/`SENT` until the backend command-expiry loop marks them `EXPIRED`
(TTL 300s).

Desired end states:

- **Direction A** should end in a terminal **"removed from backend" state** on
  the agent — stop retrying, surface "device removed" in the UI, and prompt
  re-enrolment — rather than retrying forever. This is the error-classification
  decision (gap 6).
- **Direction B** is already bounded by the offline sweep + command expiry; the
  residual risks are the transient "online" window (gap 5, the offline
  threshold) and a crashed agent lingering that way (gap 1).

## Gaps — scenarios that will *not* survive today

Ordered roughly by impact.

### 1. No agent supervision / auto-restart

`child.on('exit')` in `user_app/electron/main.ts` logs the exit and clears the
handle — it does **not** restart the agent. The agent config is written with
`watchdog_enabled: true` and `watchdog_interval_seconds: 10`, but
`_watchdog_loop` only calls `systemd.daemon.notify`, which is a **no-op on
Windows** (the `systemd` import fails).

- **Consequence:** any agent crash (unhandled exception, OOM, antivirus kill,
  `os._exit(1)` from the shutdown backstop) leaves the device offline
  indefinitely even though the app is still running in the tray.
- **Recommendation:** Electron supervises the child — restart on unexpected exit
  with crash-loop backoff (e.g. 3 restarts / 5 min, then surface an error), and
  only *skip* the restart when the stop was intentional (unpair / re-enrol /
  quit). See [ADR-0002](adr/0002-agent-supervision-and-lifetime.md).

### 2. ACK-then-execute can strand a command in `SENT`

`pending_commands_loop` orders operations as: permission-gate → `ack_command_backend`
→ execute. If the **ACK POST fails** (one lost packet during a blip), the agent
enqueues the ACK and `continue`s (skips execution). The later
`retry_flush_loop` then ACKs the command successfully, so the backend flips it
`PENDING → SENT` — but execution was never attempted and never will be, because
the command is no longer in the pending list.

- **Consequence:** a transient network failure at the exact ACK moment yields a
  command that is *acknowledged but never executed*, stuck in `SENT` with no
  result forever.
- **Recommendation:** persist a local "acked, pending execution" list and execute
  after the deferred ACK succeeds, or (preferred) execute-then-report with a
  durable "recently executed `command_id`" journal so re-polling can never
  double-execute. See [ADR-0001](adr/0001-command-delivery-semantics.md).

### 3. Command-result durability and the shutdown race

If a command executes but its result POST fails, the result is enqueued (good).
But if the agent is killed **between local execution and `enqueue()`**, the
result is lost → command stuck `SENT`. Compounding this,
`killAgent()` sends `SIGTERM` then `SIGKILL` after only **3 s**, while the
agent's `shutdown_timeout_seconds` is 30 s — so on app quit, the graceful
`send_final_offline_heartbeat` (which runs after task cancellation, potentially
a 10 s HTTP timeout) is very likely cut off by `SIGKILL` before it lands.

- **Consequence:** quitting/restarting the app frequently leaves the device
  "online" until the 300s window lapses, and in-flight command results can be
  lost.
- **Recommendation:** align the Electron kill grace period with the agent's
  shutdown timeout (or let the agent self-exit and have Electron *wait*), and
  persist command results to the durable journal *before* marking them reported.

### 4. `restart` / `shutdown` are inherently racy

`_system_control` reports `"restart initiated"` and then the host dies. If the OS
comes down faster than the report POST, the command shows `SENT` forever.

- **Recommendation:** treat these two commands as fire-and-forget — acknowledge
  them as "executed" the moment the action is *initiated*, before the actual
  reboot/power-off, and never expect a follow-up result.

### 5. Clock skew corrupts the online/offline signal

`update_heartbeat` stores the **device's** `payload.timestamp`, not server time
(`agent_repository.update_last_heartbeat(device, payload.timestamp, …)`), and
`_compute_connectivity` compares it against `datetime.now(utc)` on the server.
Meanwhile the emulator path uses server `now` (`agents.py`), so the two paths are
inconsistent.

- **Consequence:** a Windows device with a drifting clock (weak NTP, VM time-sync
  off, failing CMOS battery) is reported **falsely offline** (clock behind) or
  **falsely online** (clock ahead).
- **Recommendation:** make the server authoritative — set `last_heartbeat_at` to
  server receive time on the heartbeat endpoint, keeping `payload.timestamp`
  only for display; optionally report large client/server skew as a health
  signal.

### 6. Permanent errors are retried forever (an amplifier)

`post_json` treats every non-2xx the same as a network failure — it enqueues and
retries. So a **401/403 (revoked credential)** or **404 (unpaired on backend)**
is retried with backoff *indefinitely*, spamming the server with dead
credentials and never self-resolving. This is the exact failure behind a
removed device whose agent keeps polling (see *Stale devices*, direction A).

- **Consequence:** after a real outage recovers, devices with stale/revoked
  credentials become a persistent load source, and operators cannot distinguish
  "offline" from "permanently unenrolled".
- **Recommendation:** classify failures — retry only transient (timeout, 5xx,
  connection reset), and drop permanent (401/403/404/409) with a terminal
  log/state.

**Suspension is special (423 Locked).** Suspension is reversible, so it is
deliberately *not* in the permanent set. The backend's device-auth layer returns
`423 Locked` for a suspended device (and `403` only for unpaired/retired
devices). The agent maps 423 to `DeviceSuspendedError`, pauses its loops
(heartbeat, telemetry, alerts, live logs, jobs, command polling, retry flush),
and resumes reporting automatically once the device is resumed from the
Dashboard — no agent restart required.

### 7. Unbounded retry queue, O(n²) disk churn, no jitter

`RetryQueue` has no size/TTL cap, and `enqueue`/`save` rewrite the entire JSON
file on every operation. The backoff is deterministic (`30 * 2^n`) with **no
jitter**, so a fleet that lost connectivity together will retry in lockstep and
thunder-herd the server on recovery — the exact pool-exhaustion risk the backend
was just hardened against.

- **Consequence:** disk growth during long outages, a reconnect burst of stale
  data, and correlated recovery load on the server.
- **Recommendation:** cap queue length, add per-item TTL, dedupe by
  `(url, key)`, add random jitter to backoff, and prioritize command ACK/status
  over stale telemetry/heartbeats on reconnect (telemetry is timestamped and
  superseded anyway).

### 8. No local health signal during a server outage

The Electron-spawned agent runs with `ipc_enabled: false`, and the renderer only
reads state via the backend. So when the server is down, the app **cannot
distinguish "agent healthy locally, server unreachable" from "agent crashed"** —
both render as "offline".

- **Consequence:** during a server outage the operator gets a generic red state
  with no confidence signal, and cannot tell whether to wait for the server or
  intervene on the device.
- **Recommendation:** expose a minimal local health signal (re-enable a
  localhost IPC, or a small status file the agent maintains) so the UI can
  render a three-way state: *online / server-unreachable-but-agent-up /
  agent-down*.

### 9. Windows sleep / hibernate / network change

On wake: (a) httpx keep-alive connections are stale and the agent client has no
`pool_pre_ping` (the `pool_pre_ping` hardening was applied to the *backend*
engine, not the agent client); (b) the WNS push channel may be stale; (c) the
heartbeat gap makes the device briefly look offline. Electron has
`powerMonitor`, but the agent has no wake/network-change awareness.

- **Consequence:** resume from sleep shows a transient offline blip (up to one
  failed heartbeat + retry backoff), and WNS-pushed commands during/after sleep
  may be delayed or missed.
- **Recommendation:** on `powerMonitor` resume and/or network-interface change,
  signal the agent to reset its HTTP client and immediately heartbeat; refresh
  the WNS channel.

## Recommended resilience layers

1. **Supervision** — Electron restarts the agent on crash with backoff; an
   intentional-stop flag disables restart.
2. **Exactly-once / at-most-once commands** — durable in-flight/executed
   journal; fix the ACK-fail strand; treat `restart`/`shutdown` as
   fire-and-forget once initiated.
3. **Durable + bounded retry** — classify transient vs permanent errors,
   cap/TTL/dedupe/jitter the queue, prioritize command traffic over stale
   telemetry.
4. **Shutdown integrity** — align kill grace with the agent shutdown timeout so
   the final offline heartbeat actually lands.
5. **Clock authority** — server-receive time for `last_heartbeat_at`; flag client
   skew.
6. **Local observability** — a three-way local health state so outages are
   diagnosable on-device.
7. **Wake/network reconnection** — reset connections + heartbeat on resume and
   interface change.

## Recovery paths

These are the operator-facing flows that make the failure modes above
recoverable; they exist today and are the reference behaviour any resilience
work must preserve.

### Disconnect & Unpair Device (`DeviceInfo.tsx`)

The User App's primary teardown is a **verify-then-clear** sequence:

1. Stop the emulator/agent so telemetry stops (the agent posts a final OFFLINE
   heartbeat on graceful shutdown).
2. Best-effort, bounded confirmation: poll the device record until the
   Dashboard reports `connectivity_state: offline` (`waitForOffline`, 12s cap;
   aborts early on a fetch error).
3. `POST …/unpair` with an idempotency key (`unpair-<deviceId>`) — the server
   revokes credentials, marks the device unpaired, and returns an ack.
4. Only show "Disconnected" when the ack confirms `lifecycle_state == unpaired`.
5. Local teardown: stop processes, wipe the emulator stash, clear the
   credentials file, reset provisioned state.

On a network failure (step 3 throws a non-`ApiError`), the app falls back to a
**local reset** and shows **"server revocation pending"** — local credentials are
cleared, but the Dashboard may still list the device until it is removed or its
heartbeat window lapses. This is the correct behaviour: it never strands a
device that could otherwise silently keep polling under revoked credentials.

### Re-adding a device after unpair

Unpairing clears local credentials and the device's record is unpaired on the
Dashboard, so re-adding is a fresh enrolment:

1. On the Dashboard, copy a fresh **Site ID** and **Bootstrap Key** (both have
   copy buttons), or create an enrolment intent and copy its claim token.
2. In the User App, provision (`SetupWizard` → `bootstrapProvision`) or claim
   (`ClaimDevice` → `claimDevice`).
3. The app persists the new credentials and **restarts the agent**
   (`agent.start()` kills any stale process and spawns a fresh one) so it picks
   up the new device identity/API key.
4. Re-grant **Manage device** (`root_access`), which re-runs the scoped
   elevation installer (UAC prompt). Toggling Manage off/on is part of a safe
   Windows re-add: the elevation layer is torn down on revoke and reinstalled on
   grant.

### Reboot / Shut Down resume

`restart` and `shutdown` complete immediately (the agent reports
`restart initiated` / `shutdown initiated`), but the agent only comes back once
a user signs in — the app's Start-at-Login setting is a **login item**, so it
fires *after* login, not at boot. On a PIN/password-protected device this leaves
the device offline until a human logs in.

For unattended recovery, enable **Windows auto-logon** on the device
(`netplwiz` → uncheck "Users must enter a user name and password…", or
Sysinternals `Autologon`). Running the agent as a Windows service (deferred in
[ADR-0002](adr/0002-agent-supervision-and-lifetime.md)) would remove the login
dependency entirely.

## Device unresponsiveness detection

When a device becomes unresponsive — loses internet, shuts down, crashes,
or is force-killed by the owner — the Dashboard needs to become aware and
report it. This section catalogues what is already detected and what gaps
remain.

### What the Dashboard already detects

| Scenario | Detection mechanism | Latency | Dashboard shows |
|----------|-------------------|---------|-----------------|
| Graceful shutdown (agent sends `online=false`) | Final offline heartbeat | Immediate | Device marked OFFLINE |
| Agent process crash (no heartbeat) | `last_heartbeat_at` timeout (5× interval = 150s) | ~2.5 min | Device marked offline |
| Network partition (heartbeats stop) | Same timeout | ~2.5 min | Device marked offline |
| Stale device sweep (backend) | `_run_stale_device_detection_loop` (300s default) | ~5 min | Connectivity state updated |
| Command expiry | `_run_command_expiry_loop` (300s TTL) | ~5 min | Stale commands marked EXPIRED |
| Device suspended (423 Locked) | Backend returns 423; agent pauses loops | Immediate | Device shows suspended state |

### What the Dashboard cannot yet detect (gaps)

| Gap | Description | Impact |
|-----|-------------|--------|
| **Hung agent (deadlock)** | Agent process is alive but not heartbeating. Looks identical to powered-off. | Dashboard marks "offline" after 150s but cannot distinguish hang from power loss. |
| **Agent crash vs. network** | No heartbeat → could be crash, network, or power. No differentiation. | Technician cannot determine root cause from Dashboard alone. |
| **Prolonged offline escalation** | Device offline for 5 min, 1 hour, or 24 hours — no automatic alert. | Offline devices can go unnoticed if nobody checks the Dashboard. |
| **Force-kill / power loss** | No graceful shutdown → no `online=false`. Dashboard waits for timeout. | Same as crash — indistinguishable. |
| **Agent restart count** | Watchdog restarts are logged locally only. Dashboard sees continuous heartbeats. | An unstable agent (crashing every 5 min) looks "online" to the Dashboard. |
| **Command timeout** | A command in `SENT` status with no result stays `SENT` forever if device goes offline mid-execution. | Push History shows a command stuck in "sent" with no resolution. |
| **"Last known good" state** | Dashboard shows `last_seen` but not *why* the device went offline or whether it will recover. | Technician must manually investigate. |

### Recommended improvements (not yet implemented)

| Phase | What | Effort | Value |
|-------|------|--------|-------|
| 1 | Add `agent_uptime_seconds` and `agent_restart_count` to heartbeat payload. Dashboard shows "last restart" and "uptime". | Small | Medium — answers "did the agent restart?" |
| 2 | Command timeout: mark `SENT` commands as failed after N minutes if no result. | Small | High — prevents hanging commands |
| 3 | Offline escalation: backend background task creates alerts for devices offline > 5 min / 1 hr / 24 hr. | Medium | High — proactive awareness |
| 4 | Agent watchdog reporting: emit audit events when watchdog restarts tasks. | Medium | Medium — agent health visibility |
| 5 | Offline reason classification: use uptime tracking to distinguish crash vs. network vs. power loss. | Larger | Medium — root cause analysis |

### Existing provisions that help

- **Alert system**: `Alert` model with severity levels and categories (hardware, network, software, security). Used by `alerts_loop` for threshold breaches.
- **Live Logs**: Agent posts connectivity warnings ("Backend unreachable: heartbeat failed") and resource warnings. Dashboard polls every 2s.
- **Audit Trail**: Agent posts lifecycle events (agent_started, agent_stopped, permission_changed).
- **Retry queue**: Failed submissions are persisted to disk and retried with exponential backoff.
- **Command expiry**: Stale `PENDING`/`SENT` commands expire after TTL (default 300s).

### Key insight

The Dashboard's current awareness is **passive** — it infers device state from the *absence* of heartbeats. A comprehensive solution would add **active probing** (ping the device, check if the agent responds), **escalation** (automatic alerts for prolonged offline), and **reason classification** (distinguish crash from network from power loss).

## Decisions

The foundational decisions are recorded as ADRs; the rest are pending and will
get their own ADRs once the first two are agreed.

| Decision | Status | ADR |
| --- | --- | --- |
| Command delivery semantics (at-most-once vs at-least-once) | Proposed | [ADR-0001](adr/0001-command-delivery-semantics.md) |
| Agent supervision & lifetime (Electron supervisor vs Windows service) | Proposed | [ADR-0002](adr/0002-agent-supervision-and-lifetime.md) |
| Clock authority for `last_heartbeat_at` | Pending | — |
| Retry retention (how long unflushable payloads are retained) | Pending | — |
| Error classification (transient vs permanent retry policy) | Pending | — |

See the [ADR index](adr/overview.md) for format and status definitions.
