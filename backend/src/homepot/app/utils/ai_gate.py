"""Bounded-concurrency gate for AI (LLM) generation.

Ollama serves generations through a small number of inference slots
(``OLLAMA_NUM_PARALLEL``, which defaults to a single slot). Without an
application-level gate, every incoming request is handed to Ollama at once and
simply queues there, invisibly: the caller waits 30-60s with no feedback and no
bound, and there is no fairness between users.

This gate caps how many generations the backend runs at once and bounds how
long a request will wait for a slot before the API answers "busy" instead of
hanging. See ``docs/ai-concurrency.md`` for the full design.
"""

import logging
import threading
from typing import Any, Callable, Optional

from ai.exceptions import AIBusyError

logger = logging.getLogger(__name__)

# Re-exported so existing imports of ``ai_gate.AIBusyError`` keep working.
__all__ = ["AIBusyError", "AIConcurrencyGate"]


class AIConcurrencyGate:
    """Caps concurrent AI generations and bounds the wait for a free slot.

    The primitive is a ``threading.Semaphore`` on purpose (not an
    ``asyncio.Semaphore``): the Ollama client is synchronous and runs in a
    worker thread, so the slot is acquired and released on that same thread.
    This keeps the gate independent of the event loop (safe across the loops
    pytest creates) and means the semaphore only ever guards the blocking call.

    Args:
        max_concurrent: Maximum generations allowed to run at once. Keep this
            aligned with Ollama's actual slot count so the gate (which can
            return a friendly "busy") is what queues requests, not Ollama.
        queue_timeout_seconds: How long a request may wait for a slot before
            ``AIBusyError`` is raised. ``None`` (or <= 0) waits indefinitely.
    """

    def __init__(
        self,
        max_concurrent: int = 1,
        queue_timeout_seconds: Optional[float] = None,
    ) -> None:
        """Initialise the gate from the given limits."""
        self.max_concurrent = max(1, int(max_concurrent))
        self.queue_timeout_seconds = (
            float(queue_timeout_seconds) if queue_timeout_seconds else None
        )
        self._semaphore = threading.Semaphore(self.max_concurrent)

    @property
    def free_slots(self) -> int:
        """Best-effort count of currently free slots (diagnostics only)."""
        # threading.Semaphore exposes no public counter; CPython's is _value.
        try:
            return int(getattr(self._semaphore, "_value", 0))
        except Exception:  # pragma: no cover - defensive
            return 0

    def run(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Run ``func`` while holding an AI slot, waiting for one if needed.

        Raises:
            AIBusyError: if the wait for a slot exceeds ``queue_timeout_seconds``.
        """
        if self.queue_timeout_seconds:
            acquired = self._semaphore.acquire(timeout=self.queue_timeout_seconds)
        else:
            self._semaphore.acquire()
            acquired = True

        if not acquired:
            logger.warning(
                "AI gate full: no slot within %.1fs (max_concurrent=%d)",
                self.queue_timeout_seconds,
                self.max_concurrent,
            )
            raise AIBusyError(
                f"no AI slot within {self.queue_timeout_seconds}s "
                f"(max_concurrent={self.max_concurrent})"
            )

        try:
            return func(*args, **kwargs)
        finally:
            self._semaphore.release()
