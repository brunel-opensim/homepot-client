"""Explicit cancellation for in-flight AI queries (technician Stop/Esc).

A TCP disconnect is not a usable cancellation signal in this deployment, so
cancellation is requested out of band instead:

* The API is wrapped in ``AnalyticsMiddleware``, a ``BaseHTTPMiddleware``, which
  re-wraps the ASGI ``receive`` callable and breaks the immediate-cancel trick
  inside Starlette's ``Request.is_disconnected``. With that middleware in the
  stack the check never reports a disconnect (verified against the deployed
  stack: uvicorn 0.54 + starlette 1.7, with and without the middleware).
* In production the API also sits behind Apache, which keeps a worker blocked
  reading the backend response and does not notice a browser abort: an aborted
  request ran to completion while Apache logged a 502 at its own ProxyTimeout.

So the widget sends a client-generated ``query_id`` with the question and, on
Stop/Esc, posts that id back. ``POST /ai/query/cancel`` flags the matching
in-flight query, and the handler checks the flag at the same two points it used
to check for a disconnect (before and after generation). That is enough to make
a cancel mean something in both cases:

* before generation: skip the inference entirely;
* after generation: discard the answer instead of remembering it.

The generation itself still cannot be interrupted - the Ollama client is
synchronous and runs in a worker thread - so only the side effects are
cancelled. See ``docs/ai-concurrency.md``.

The primitive is a ``threading.Event`` in a module-level registry guarded by a
lock, mirroring ``utils/ai_gate.py``: the token is set from the cancel request's
task and read from the query's task, and it must stay independent of the event
loop (pytest creates a loop per test).
"""

import logging
import threading
from typing import Any, Dict

logger = logging.getLogger(__name__)

__all__ = ["AICancelToken", "cancel_query", "register_query", "release_query"]

# Cap on simultaneously tracked queries. The registry only holds queries that
# are actually in flight, so this is a safety net for a client that never
# cancels (or a leaked registration): the oldest entry is dropped first, which
# at worst makes a very old query non-cancellable.
_MAX_TRACKED_QUERIES = 256


class AICancelToken:
    """Cancellation handle for one in-flight AI query."""

    def __init__(self, query_id: str, user_id: Any = None) -> None:
        """Track a query id, optionally owned by ``user_id``."""
        self.query_id = query_id
        self.user_id = user_id
        self._event = threading.Event()

    def cancel(self) -> None:
        """Flag this query as abandoned. Idempotent and thread-safe."""
        self._event.set()

    @property
    def cancelled(self) -> bool:
        """Whether a Stop/Esc has been recorded for this query."""
        return self._event.is_set()


_lock = threading.Lock()
_tokens: Dict[str, AICancelToken] = {}


def register_query(query_id: str, user_id: Any = None) -> AICancelToken:
    """Track ``query_id`` as in flight and return its cancellation token."""
    token = AICancelToken(query_id, user_id)
    with _lock:
        _tokens[query_id] = token
        while len(_tokens) > _MAX_TRACKED_QUERIES:
            oldest = next(iter(_tokens))
            logger.warning(
                "AI cancel registry full; evicting query_id=%s (max=%d)",
                oldest,
                _MAX_TRACKED_QUERIES,
            )
            _tokens.pop(oldest, None)
    return token


def release_query(token: AICancelToken) -> None:
    """Stop tracking a finished query.

    Only drops the entry when it is still this token, so an id reused by a later
    query keeps its own registration.
    """
    with _lock:
        if _tokens.get(token.query_id) is token:
            _tokens.pop(token.query_id, None)


def cancel_query(query_id: str, user_id: Any = None) -> bool:
    """Record a Stop/Esc for ``query_id``.

    Returns ``True`` when an in-flight query was flagged. An unknown id, or one
    owned by another user, returns ``False`` and is deliberately
    indistinguishable from the other, so the endpoint cannot be used to probe
    for live queries.
    """
    with _lock:
        token = _tokens.get(query_id)
    if token is None:
        return False
    if token.user_id is not None and token.user_id != user_id:
        return False
    token.cancel()
    return True
