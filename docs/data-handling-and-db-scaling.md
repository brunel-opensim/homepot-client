# Data Handling & Database Scaling

This document tracks how the HomePot backend writes to PostgreSQL, where the
scaling pressure points are, and the recommended mitigation roadmap. It is a
living design note — update it when a mitigation lands or a new write path is
added.

Related: `docs/database-guide.md`, `docs/server-deployment.md`
(pool tuning section), `docs/device-offline-resilience.md`.

---

## 1. Write frequency to Postgres (steady state)

### Per device (agent, ~30 s cadence)

| Source | Cadence | Write | Engine | Notes |
|---|---|---|---|---|
| Heartbeat | 30 s | `Device` UPDATE (`last_heartbeat_at`, `status`) | async | 2/min/device |
| Telemetry | 30 s | `DeviceMetrics` INSERT | async | 2/min/device |
| Live Logs (status) | 30 s, deduped by signature | `ErrorLog` INSERT (only when metrics change) | async | ~1-2/hr/device in practice |
| Alerts | on condition change | `ErrorLog` INSERT | async | rare |
| Command status | on completion | `DeviceCommand` UPDATE | async | on demand |
| Job updates | orchestrator-driven | `Job` UPDATE | async | on demand |
| Permissions poll (User App) | 30 s | read only | sync (`get_db`) | no write, but holds a sync connection |
| Heartbeat/telemetry/logs (analytics) | — | skipped by analytics middleware | — | `/api/v1/agent/*` is in `_SKIP_PATHS` |

**Per device total: ~4 writes/min at steady state** (heartbeat + telemetry dominate).

### Dashboard (per open tab)

The Device Details page polls **6 endpoints every 2 s** (metrics, logs, audit,
jobs, commands, alerts) plus device status every 10 s.

The analytics middleware writes an `api_request_logs` row for each of those
(agent paths are skipped, but `/api/v1/devices/*` and `/api/v1/jobs/*` are
**not**). That is roughly **3 writes/sec per open dashboard tab**
(~10,800 writes/hour per technician session) — **the dominant write source
today**, larger than all per-device telemetry combined.

### Other background writers

- `run_api_request_log_retention_loop`: trims `api_request_logs` past the
  configured retention (default 30 days) every 6 h, in bounded batches.
- `run_api_request_log_retention_loop` and the orchestrator job workers run in
  the same process that serves the API.

---

## 2. What is already in place

- **Pool settings applied to both engines** (async + sync): `pool_size`,
  `max_overflow`, `pool_timeout`, `pool_recycle`, `pool_pre_ping`. Previously
  the async engine ignored them. (PR #572)
- **Analytics logging is async, bounded, best-effort**: writes run as detached
  tasks on the async engine, capped by a semaphore (16), dropped under
  backpressure. Previously a synchronous `SessionLocal` commit ran inside the
  async event loop on every request. (PR #572)
- **High-frequency agent paths skipped by analytics**: `/api/v1/agent/*`,
  `/health`, `/metrics`, docs. (PR #572)
- **`api_request_logs` retention trim**: 30 days default, every 6 h, batched
  deletes. (PR #573)
- **In-memory caches**: `smart_filter.py` (process-local, with a TODO to
  replace with Redis). No shared cache exists.
- **Pool defaults raised**: `pool_size` 5→15, `max_overflow` 10→25,
  `pool_timeout` 30→60. (PR #610)
- **`DevicePermissionsEndpoint` migrated to async** so the 30 s permission poll
  no longer touches the sync pool. (PR #611)

---

## 3. Scaling concerns (more devices, more dashboards)

| Concern | At current scale | At 10× (100+ devices, several open dashboards) |
|---|---|---|
| Per-device writes (heartbeat + telemetry) | ~4/min/device → ~240/hr for 10 devices | ~2,400/hr for 100 devices — manageable for Postgres |
| Dashboard polling writes | ~10,800/hr per open tab | 10 tabs → ~108,000/hr — **dominant** |
| Pool pressure | 15+25 per engine | Sync engine still used by some endpoints; needs further migration |
| `api_request_logs` growth | trimmed at 30 days | trim loop runs every 6 h; table can grow large between passes |
| `DeviceMetrics` growth | unbounded (no retention) | **unbounded** — will become the largest table; needs a retention/TTL policy |
| Single uvicorn process | 1 worker, threadpool | single process is a ceiling; needs multiple workers + a real cache for shared state |

### Observed failure mode

Production hit `QueuePool limit of size 5 overflow 10 reached, connection timed
out, timeout 30.00`. Root cause: small default pool + slow remote DB (Postgres
at `51.161.114.195`) + burst load (commands + heartbeats + dashboard polling +
SSE streams). Sessions sat in `idle in transaction` because requests blocked
waiting for a connection, which held their already-checked-out connection,
creating a spiral. Fixed by the pool bump (PR #610) and the async migration
(PR #611).

---

## 4. Midpoint cache options

### Option A — Redis (configured but not deployed)

- `RedisSettings` exists in `config.py` (`redis://localhost:6379/0`), but
  Redis is **not installed** on the server and nothing uses it.
- Best for: session/cache sharing across workers, rate limiting, pub/sub for
  push wake, caching device permissions and device records.
- Effort: medium (install Redis, wire a client, replace in-memory caches).
- Highest leverage for horizontal scaling (multiple uvicorn workers).

### Option B — In-memory with TTL (process-local)

- Already partially done (`smart_filter.py`). Cheap, no new infra.
- Limitation: does not share across workers/processes; each worker has its own
  cache. Fine for single-process today.
- Good for: hot read paths (device permissions, device record) with short TTL.

### Option C — Read replicas / DB-side caching

- Postgres materialized views or read replicas for dashboard reads. Overkill
  at current scale.

### Option D — Reduce write amplification at the source (no cache needed)

- Increase dashboard polling cadence (2 s → 5–10 s) — biggest single win for
  write load, zero infra.
- Skip analytics logging for dashboard read paths (or log only mutations) —
  removes the dominant write source entirely.
- Batch telemetry inserts (bulk insert per interval instead of one row per
  device).
- Add a retention policy for `DeviceMetrics` (e.g. keep raw 7 days, aggregate
  older).

---

## 5. Recommendations (priority order)

1. **Reduce dashboard polling cadence** (2 s → 5–10 s) — biggest immediate
   win, zero infra. Metrics/logs are already "live enough" at 5 s.
2. **Skip analytics logging for dashboard read paths** (or log only mutations)
   — removes the dominant write source entirely.
3. **Add `DeviceMetrics` retention** (e.g. 30 days raw, then aggregate) —
   prevents unbounded growth of the largest table.
4. **Bump pool defaults** (PR #610 — in flight).
5. **Migrate remaining sync endpoints to async** (PR #611 started this;
   `get_device` is next).
6. **Deploy Redis + replace in-memory caches** when moving to multiple workers
   or needing shared state — not needed yet at single-process scale.

### Bottom line

At today's scale (single device + a few technicians), the system is fine once
the pool is sized correctly. The first real scaling wall is **dashboard
polling write amplification** (Option D, items 1–2), not per-device telemetry.
Redis (Option A) becomes valuable when going multi-worker or needing shared
caches. Hold off on Redis until the cheaper wins are exhausted.

---

## 6. Status tracker

| Item | Status |
|---|---|
| Pool settings applied to async engine | Done (#572) |
| Analytics non-blocking + bounded | Done (#572) |
| Analytics skips agent/health/metrics paths | Done (#572) |
| `api_request_logs` retention trim | Done (#573) |
| Pool tuning documented | Done (#574) |
| Pool defaults bumped (15/25/60) | PR #610 (open) |
| `DevicePermissionsEndpoint` async | PR #611 (open) |
| Dashboard polling cadence reduction (2s → 5s) | Done (PR #613) |
| Analytics skip for dashboard reads (GET) | Done (PR #613) |
| `DeviceMetrics` retention policy (30 days, trim loop) | Done (PR #614) |
| `get_device` async migration | Proposed (not started) |
| Redis deployment + cache wiring | Deferred (not needed yet) |
