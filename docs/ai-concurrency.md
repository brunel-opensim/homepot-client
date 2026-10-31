# AI Concurrency & Load

How HOMEPOT behaves when more than one user (or tab) asks the AI a question at
the same time, and the small application-level gate that keeps that behaviour
bounded and predictable.

!!! info "Why this page exists"
    The production host has **no GPU** and runs a single Ollama inference slot.
    Everything here is about making a queue that already exists (inside Ollama)
    *visible* and **bounded**, rather than a silent 60-second hang.

---

## The bottleneck: one inference slot

`llama3.2:latest` runs on CPU on a 4-core / ~7.6 GB host. Ollama only runs as
many generations in parallel as it has KV-cache "slots", controlled by
`OLLAMA_NUM_PARALLEL`. That variable is **unset on the production host**, so
Ollama runs **one slot** — confirmed by `journalctl -u ollama` showing only
`slot id 0`.

Consequences:

- Every generation is served one at a time; extra requests **queue inside
  Ollama**, invisibly.
- A caller sees a 30-60s wait with no feedback and no upper bound.
- Generation runs at roughly **4.2-4.3 tok/s** on this CPU. Prompt evaluation is
  much faster at ~30 tok/s, but only when Ollama can reuse the previous
  request's key/value prefix — a matching prefix costs ~0.2-0.9s to re-enter,
  while one that diverges early costs ~110-130s for a ~3.5k-token prompt. That
  is why `main.py` warms the prefix at startup and every query path leads with
  the same shared block: see
  [Prompt-prefix caching](ai-query-routing.md#prompt-prefix-caching-path-switch-latency).

Without an application-level queue, a burst of N users each waits for the N-1
before them, and nobody can tell whether the service is busy or broken.

---

## What the backend does: a slot gate

Before it calls Ollama, the direct (non-agentic) query path takes a slot from a
process-wide gate. The gate is a `threading.Semaphore`, taken **inside the
worker thread** that runs the synchronous Ollama client:

```python
# backend/src/homepot/app/utils/ai_gate.py
class AIConcurrencyGate:
    def __init__(self, max_concurrent=1, queue_timeout_seconds=None):
        self._semaphore = threading.Semaphore(self.max_concurrent)
        ...

    def run(self, func, *args, **kwargs):
        acquired = self._semaphore.acquire(timeout=self.queue_timeout_seconds)
        if not acquired:
            raise AIBusyError(...)
        try:
            return func(*args, **kwargs)
        finally:
            self._semaphore.release()
```

```python
# backend/src/homepot/app/api/API_v1/Endpoints/AIEndpoint.py
response = await asyncio.to_thread(
    gate.run,
    llm.generate_response,
    prompt=request.query,
    context=full_context,
    system_prompt=system_prompt_text,
)
```

Why a thread semaphore and not `asyncio.Semaphore`:

- The Ollama client is synchronous and already runs in a worker thread, so the
  slot is acquired and released on that same thread.
- It is independent of the event loop, so it behaves identically under the
  single production loop and under the fresh loops pytest creates per test.

### Behaviour

| Config | Behaviour |
|---|---|
| Slot free | Runs immediately. |
| All slots busy, wait <= `queue_timeout_seconds` | Waits, then runs in order. |
| All slots busy, wait > `queue_timeout_seconds` | Returns **HTTP 503** with `Retry-After: 5` and a friendly "assistant is busy" message. |

A rejected request is rejected *before* calling Ollama, so it costs no CPU and
does not consume a place in Ollama's own queue.

Measured on the production host with the default single slot:

| Concurrent requests | Result |
|---|---|
| 2 | both complete, ~30s each |
| 4 | all complete within ~37s |
| 6 | all complete within ~33s |

The mixed latencies are the queue draining; the gate makes this explicit and
bounds the worst case at `queue_timeout_seconds`.

### Time-outs and what the user is told

The 503 above is the *fast* failure; the other is running out of time, which has
two independent ceilings:

| Bound | Value | Where |
|---|---|---|
| Client request timeout | `VITE_AI_QUERY_TIMEOUT`, default 600000 ms (10 min) | `frontend/src/utils/aiTimeouts.js` |
| Reverse-proxy timeout | Apache `ProxyTimeout 600` | server vhost |
| Queue budget before the 503 | `queue_timeout_seconds: 120` | `ai/config.yaml` |

The client and proxy ceilings are matched on purpose, so a time-out is reported
the same way whichever is reached first. They used to be 180 s, which a cold
start can exceed: a cold knowledge query measured **324 s** on the deployment
host, so both are now 10 minutes. Keeping the model warm (`llm.keep_alive`) is
the cheaper fix, since a resident model answers in 40-120 s.

Because "the assistant didn't answer" has several such causes,
`frontend/src/utils/aiErrorMessage.js` maps them to distinct, actionable
messages: busy slot (503 + `Retry-After`), timed out (client or proxy), expired
session (401), permission (403), server error (5xx, with the backend's
`detail`), or unreachable server (no response). The widget also shows a "still
working" hint after 90 s, so a slow cold start is not mistaken for a failure.

---

## Cancelling a query (Stop / Esc)

A technician who can see the assistant going the wrong way does not have to wait
it out. The widget's **Stop** button — or the **Esc** key — does two things:

1. aborts the HTTP request (`AbortController` → axios `signal`), so the page
   stops waiting immediately; and
2. posts the query's id back to `POST /api/v1/ai/query/cancel`, which flags the
   in-flight query server-side.

Both parts are needed, because aborting the request alone does **not** reach the
backend in this deployment:

- the API is wrapped in `AnalyticsMiddleware`, a `BaseHTTPMiddleware`, which
  re-wraps the ASGI `receive` callable — with it in the stack
  `request.is_disconnected()` never reports a disconnect (verified against the
  deployed uvicorn 0.54 / starlette 1.7 stack, with and without the middleware);
- in production Apache keeps a worker blocked reading the backend response and
  does not notice the browser abort either: an aborted request ran to completion
  and Apache logged a `502` only when its own `ProxyTimeout` expired.

So the id is the signal that counts. Every query carries a client-generated
`query_id`, and the cancel endpoint looks it up in a small in-flight registry
(`backend/src/homepot/app/utils/ai_cancel.py`). The handler checks the flag at
two points — before and after generation — which is what makes a cancel mean
something:

| Cancelled | What the server does |
|---|---|
| While queued, before generation | The generation is **never started**: no CPU is spent on an answer nobody will read. |
| While generating | The generation finishes (see below), but the answer is **discarded**: no memory write, no proposal, no "delivered" audit entry. |
| Either stage | Audited as `AI query cancelled` with `cancelled: true`, `cancel_stage` (`before_generation` / `after_generation`) and `cancel_source` (`explicit_cancel` / `client_disconnect`), so abandonment is measurable rather than invisible. |

`POST /ai/query/cancel` is answered while a generation is still running: it is a
tiny request that does not touch the generation gate. It replies
`{"cancelled": true}` only when it really did flag an in-flight query, and
`{"cancelled": false}` when the id is unknown or the query had already finished.
A `query_id` owned by another user is treated exactly like an unknown one, so the
endpoint cannot be used to probe for other users' queries. The widget uses that
answer to avoid claiming "nothing was saved" when the answer had in fact already
been stored.

The older disconnect check is still made (`cancel_source: client_disconnect`),
but only as a best-effort extra for callers that do not use the cancel endpoint.
It is not what the feature relies on: neither the analytics middleware nor Apache
forwards the abort, so a deployment with only that check would never cancel
anything.

The UI renders a distinct "Query cancelled" state — deliberately not an error,
and not the timeout message.

The one thing a cancel cannot do is stop a generation that is already running.
The Ollama client is synchronous and runs in a worker thread
(`asyncio.to_thread`), and **threads cannot be cancelled**; the slot is released
when the thread returns. That is bounded here because `num_predict: 160` caps
output at ~40-120 s warm, and the checks above make sure the abandoned work
leaves nothing behind.

Only the *side effects* are cancelled, in other words — not the arithmetic. So
cancelling is not free: the slot stays busy until the abandoned generation ends,
and an immediate retry queues behind it. `queue_timeout_seconds` is set to 120 s
for exactly that reason, so a retried question waits for the slot instead of
collecting a 503.

The relevant tests are `backend/tests/test_ai_query_cancellation.py`, the
`AskAIWidget cancelling a query in flight` block in
`frontend/src/components/Dashboard/AskAIWidget.test.jsx`, and
`frontend/src/utils/aiQueryId.test.js`.

---

## Configuration

`ai/config.yaml` -> `llm`:

```yaml
llm:
  max_concurrent: 1            # generations allowed to run at once
  queue_timeout_seconds: 120   # wait budget before HTTP 503; null/<=0 = wait forever
```

Keep `max_concurrent` aligned with Ollama's real slot count. Setting it higher
than Ollama's slots does not add throughput; it just moves the queue back inside
Ollama where callers get no feedback.

The gate is created lazily from this config on the first AI request
(`get_ai_gate()`), so changing it requires an API restart.

### External providers (OpenAI, Anthropic)

The gate is **provider-agnostic** — the same `max_concurrent` and
`queue_timeout_seconds` apply to every provider, and the gate is built once from
config, not rebuilt when the provider is switched.

That means a setting tuned for Ollama also throttles cloud providers:

- `max_concurrent: 1` is correct for a single local Ollama slot, but it also
  serialises fast cloud calls. If you run demos on OpenAI/Anthropic with several
  concurrent users, raise `max_concurrent` (e.g. 4–8) and keep
  `queue_timeout_seconds` generous.
- Changing the value still requires an API restart, even when the provider
  itself can be switched at runtime without one.

Provider-aware concurrency (different limits per provider) is a planned
follow-up; until then, pick a value that is safe for the provider you run most.
See [LLM Providers](ai-llm-providers.md#provider-specific-tuning).

### Raising Ollama's parallelism

Setting `OLLAMA_NUM_PARALLEL=2` (systemd override for `ollama`) allows two
concurrent generations. Each slot allocates its own KV cache for the configured
context window (`num_ctx` 8192 here), which costs **roughly another 3 GB of
RAM** — not safe on the current 7.6 GB host alongside the 3.1 GB model. If the
gate is set to 2, Ollama's `OLLAMA_NUM_PARALLEL` should be raised to match.

---

## What this does *not* cover

- **Fairness across users.** The gate is first-come, first-served. One client
  firing many requests can occupy the slot(s) ahead of others. Per-user rate
  limiting (reusing the slowapi `Limiter` already wired in `main.py`) is a
  follow-up.
- **Multiple API workers.** A `threading.Semaphore` is per-process. With more
  than one uvicorn worker, each process has its own gate, so the effective
  limit is `workers x max_concurrent`. The current deployment runs a single
  worker.
- **Feedback while queued.** A waiting caller still just waits up to the
  timeout; there is no progress stream yet.
- **Interrupting a running generation.** Stop/Esc is honoured before a
  generation starts and after it finishes (discarding the answer), but cannot
  abort the Ollama call in flight — the synchronous client blocks a worker
  thread, and threads cannot be cancelled. Doing better needs a streaming or
  async Ollama client, which would also change the gate from a thread semaphore
  to an event-loop one.

!!! note "Agentic mode is gated too"
    Each LLM call inside `run_agent` is routed through the same gate per call
    (`ai/agent.py` `_generate_with_gate`), so agentic queries share the slot
    budget and return the same 503 when saturated. Tool execution runs *outside*
    the slot, letting other requests interleave between an agent's reasoning
    steps. A saturated gate on the first generation raises `AIBusyError` (→ 503);
    saturation on the forced final-answer call is absorbed into the agent's
    fallback instead of failing the request.


---

## Verifying

Unit tests (no Ollama needed):

```bash
cd backend && python -m pytest tests/test_ai_concurrency.py -q
```

Manual, against a running API:

```bash
# Three at once; with max_concurrent=1, queue_timeout_seconds=120 the
# third should still be served (within the timeout), and a 7th under a
# tight timeout should get HTTP 503 + Retry-After.
for i in 1 2 3; do
  curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" \
    -X POST http://127.0.0.1:8000/api/v1/ai/query \
    -H "Authorization: Bearer $(cat /tmp/hp_token)" \
    -H "Content-Type: application/json" \
    -d '{"query":"status"}' &
done; wait
```
