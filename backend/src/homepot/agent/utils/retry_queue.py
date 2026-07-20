"""File-backed retry queue with exponential backoff for offline submissions."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from homepot.agent.identity import identity_dir

_BASE_DELAY = 30.0
_MAX_DELAY = 3600.0


def _backoff_delay(retry_count: int) -> float:
    """Return the exponential backoff delay in seconds for the given retry count.

    Formula: min(30 * 2^retry_count, 3600)
    """
    return min(_BASE_DELAY * (2**retry_count), _MAX_DELAY)  # type: ignore[no-any-return]


def _compute_next_retry(retry_count: int) -> str:
    """Return an ISO-8601 UTC timestamp for the next allowed retry time."""
    return (
        datetime.now(timezone.utc) + timedelta(seconds=_backoff_delay(retry_count))
    ).isoformat()


def _default_queue_path() -> Path:
    """Return the default queue file path inside the homepot identity directory."""
    return identity_dir() / ".agent_retry_queue.json"


class RetryQueue:
    """File-backed retry queue with exponential backoff for payload delivery retries.

    Each item tracks ``retry_count`` and ``next_retry_at`` (ISO-8601 UTC).
    Use :meth:`dequeue_ready` to retrieve only items whose backoff has elapsed.
    """

    def __init__(self, queue_file: Optional[Path] = None) -> None:
        """Initialize queue.

        Parameters
        ----------
        queue_file:
            Path to the JSON file.  Defaults to
            ``<identity_dir>/.agent_retry_queue.json``.
        """
        self.path = queue_file or _default_queue_path()

    def load(self) -> List[Dict[str, Any]]:
        """Load queued payloads from disk."""
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return cast(List[Dict[str, Any]], data)
            return []
        except Exception:
            return []

    def save(self, items: List[Dict[str, Any]]) -> None:
        """Persist queued payloads to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(items, indent=2), encoding="utf-8")

    def enqueue(self, item: Dict[str, Any]) -> None:
        """Add a payload to the retry queue.

        If the item already contains ``retry_count`` it is kept;
        otherwise it is initialised to ``0``.  ``next_retry_at`` is
        recalculated from the current count.
        """
        retry_count = item.get("retry_count", 0)
        if not isinstance(retry_count, int):
            retry_count = 0
        enriched: Dict[str, Any] = {
            "url": item["url"],
            "payload": item["payload"],
            "retry_count": retry_count,
            "next_retry_at": _compute_next_retry(retry_count),
        }
        items = self.load()
        items.append(enriched)
        self.save(items)

    def requeue(self, item: Dict[str, Any]) -> None:
        """Re-enqueue a failed item, incrementing its retry count.

        Shortcut for ``enqueue`` after bumping ``retry_count`` by one.
        """
        retry_count = item.get("retry_count", 0)
        if not isinstance(retry_count, int):
            retry_count = 0
        item["retry_count"] = retry_count + 1  # type: ignore[typeddict-item]
        self.enqueue(item)

    def dequeue_ready(self) -> List[Dict[str, Any]]:
        """Return items whose backoff delay has elapsed.

        Items that are still within their backoff window remain queued.
        """
        now = datetime.now(timezone.utc)
        items = self.load()
        ready: List[Dict[str, Any]] = []
        pending: List[Dict[str, Any]] = []
        for item in items:
            next_at_str: Optional[str] = item.get("next_retry_at")
            if next_at_str:
                try:
                    next_at = datetime.fromisoformat(next_at_str)
                    if next_at <= now:
                        ready.append(item)
                    else:
                        pending.append(item)
                    continue
                except (ValueError, TypeError):
                    pass
            ready.append(item)
        self.save(pending)
        return ready

    def dequeue_all(self) -> List[Dict[str, Any]]:
        """Return all queued payloads regardless of backoff and clear the queue.

        Provided for compatibility; prefer :meth:`dequeue_ready` to
        respect exponential backoff.
        """
        items = self.load()
        self.save([])
        return items

    def clear(self) -> None:
        """Remove all items from the queue."""
        self.save([])

    def __len__(self) -> int:
        """Return the number of queued items."""
        return len(self.load())
