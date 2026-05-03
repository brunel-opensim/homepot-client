"""Simple persistent retry queue for offline agent submissions."""

import json
from pathlib import Path
from typing import Any, Dict, List, cast


class RetryQueue:
    """Small file-backed retry queue for payload delivery retries."""

    def __init__(self, queue_file: str = ".agent_retry_queue.json") -> None:
        """Initialize queue with a local JSON file path."""
        self.path = Path(queue_file)

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
        self.path.write_text(json.dumps(items, indent=2), encoding="utf-8")

    def enqueue(self, item: Dict[str, Any]) -> None:
        """Add a payload to the retry queue."""
        items = self.load()
        items.append(item)
        self.save(items)

    def dequeue_all(self) -> List[Dict[str, Any]]:
        """Return all queued payloads and clear the queue."""
        items = self.load()
        self.save([])
        return items
