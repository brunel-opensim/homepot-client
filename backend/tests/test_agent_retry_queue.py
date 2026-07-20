"""Tests for the RetryQueue with exponential backoff."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile

import pytest

from homepot.agent.utils.retry_queue import RetryQueue, _backoff_delay


def _make_item(
    url: str = "http://localhost/api/v1/agent/heartbeat",
    retry_count: int = 0,
    offset_seconds: float = 0,
) -> dict:
    """Build an item dict with optional retry metadata."""
    item: dict = {"url": url, "payload": {"device_id": "d1"}}
    if retry_count:
        item["retry_count"] = retry_count
    if offset_seconds:
        next_at = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
        item["next_retry_at"] = next_at.isoformat()
    return item


# ---------------------------------------------------------------------------
# Backoff helper
# ---------------------------------------------------------------------------


class TestBackoffDelay:
    """Tests for the exponential backoff delay helper."""

    def test_retry_0_is_30_seconds(self):
        """Retry count 0 yields a 30-second delay."""
        assert _backoff_delay(0) == 30.0

    def test_retry_1_is_60_seconds(self):
        """Retry count 1 yields a 60-second delay."""
        assert _backoff_delay(1) == 60.0

    def test_retry_2_is_120_seconds(self):
        """Retry count 2 yields a 120-second delay."""
        assert _backoff_delay(2) == 120.0

    def test_retry_3_is_240_seconds(self):
        """Retry count 3 yields a 240-second delay."""
        assert _backoff_delay(3) == 240.0

    def test_retry_4_is_480_seconds(self):
        """Retry count 4 yields a 480-second delay."""
        assert _backoff_delay(4) == 480.0

    def test_retry_5_is_960_seconds(self):
        """Retry count 5 yields a 960-second delay."""
        assert _backoff_delay(5) == 960.0

    def test_retry_6_is_1920_seconds(self):
        """Retry count 6 yields a 1920-second delay."""
        assert _backoff_delay(6) == 1920.0

    def test_retry_7_is_capped_at_3600(self):
        """Retry count 7 is capped at 3600 seconds."""
        assert _backoff_delay(7) == 3600.0

    def test_retry_10_is_capped_at_3600(self):
        """Retry count 10 is still capped at 3600 seconds."""
        assert _backoff_delay(10) == 3600.0


# ---------------------------------------------------------------------------
# RetryQueue
# ---------------------------------------------------------------------------


class TestRetryQueue:
    """Tests for the RetryQueue with exponential backoff and disk persistence."""

    @pytest.fixture
    def queue_file(self):
        """Yield a temporary path for the queue file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "retry_queue.json"

    @pytest.fixture
    def queue(self, queue_file):
        """Yield a RetryQueue backed by the temporary file."""
        return RetryQueue(queue_file=queue_file)

    # enqueue

    def test_enqueue_adds_item(self, queue, queue_file):
        """Enqueued item is persisted to disk and contains expected fields."""
        queue.enqueue(_make_item())
        data = json.loads(queue_file.read_text("utf-8"))
        assert len(data) == 1
        assert data[0]["url"] == "http://localhost/api/v1/agent/heartbeat"
        assert data[0]["payload"] == {"device_id": "d1"}
        assert data[0]["retry_count"] == 0
        assert "next_retry_at" in data[0]

    def test_enqueue_initialises_retry_count(self, queue, queue_file):
        """An item without retry_count gets initialised to 0."""
        queue.enqueue({"url": "http://example.com", "payload": {"k": "v"}})
        data = json.loads(queue_file.read_text("utf-8"))
        assert data[0]["retry_count"] == 0

    def test_enqueue_preserves_existing_retry_count(self, queue, queue_file):
        """An item with an existing retry_count keeps its value."""
        queue.enqueue(_make_item(retry_count=3))
        data = json.loads(queue_file.read_text("utf-8"))
        assert data[0]["retry_count"] == 3

    def test_enqueue_multiple_items(self, queue, queue_file):
        """Multiple enqueued items are all persisted."""
        queue.enqueue(_make_item(url="http://a.com"))
        queue.enqueue(_make_item(url="http://b.com"))
        data = json.loads(queue_file.read_text("utf-8"))
        assert len(data) == 2

    # requeue

    def test_requeue_increments_retry_count(self, queue, queue_file):
        """Requeuing an item increments its retry_count by 1."""
        queue.enqueue(_make_item())
        items = queue.dequeue_all()
        assert items[0]["retry_count"] == 0
        queue.requeue(items[0])
        data = json.loads(queue_file.read_text("utf-8"))
        assert data[0]["retry_count"] == 1

    def test_requeue_recalculates_next_retry_at(self, queue, queue_file):
        """Requeuing updates next_retry_at to a new future timestamp."""
        queue.enqueue(_make_item())
        items = queue.dequeue_all()
        first_next = items[0]["next_retry_at"]
        queue.requeue(items[0])
        data = json.loads(queue_file.read_text("utf-8"))
        assert data[0]["next_retry_at"] != first_next

    def test_requeue_preserves_url_and_payload(self, queue, queue_file):
        """Requeuing preserves the original url and payload."""
        queue.enqueue(_make_item(url="http://test.io", retry_count=0))
        items = queue.dequeue_all()
        queue.requeue(items[0])
        data = json.loads(queue_file.read_text("utf-8"))
        assert data[0]["url"] == "http://test.io"
        assert data[0]["payload"] == {"device_id": "d1"}

    # dequeue_ready

    def _save_with_offset(
        self, queue, offset_seconds: float, url: str = "http://example.com"
    ) -> None:
        """Save an item directly with a specific next_retry_at offset."""
        now = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
        queue.save(
            [
                {
                    "url": url,
                    "payload": {"device_id": "d1"},
                    "retry_count": 0,
                    "next_retry_at": now.isoformat(),
                }
            ]
        )

    def test_dequeue_ready_returns_past_items(self, queue):
        """Items with a past next_retry_at are returned as ready."""
        self._save_with_offset(queue, -10)
        ready = queue.dequeue_ready()
        assert len(ready) == 1

    def test_dequeue_ready_skips_future_items(self, queue):
        """Items with a future next_retry_at are not returned."""
        self._save_with_offset(queue, 600)
        ready = queue.dequeue_ready()
        assert len(ready) == 0

    def test_dequeue_ready_keeps_future_items_queued(self, queue, queue_file):
        """Future items remain on disk after dequeue_ready."""
        self._save_with_offset(queue, 600)
        queue.dequeue_ready()
        data = json.loads(queue_file.read_text("utf-8"))
        assert len(data) == 1

    def test_dequeue_ready_removes_past_items(self, queue, queue_file):
        """Past items are removed from disk after dequeue_ready."""
        self._save_with_offset(queue, -10)
        queue.dequeue_ready()
        data = json.loads(queue_file.read_text("utf-8"))
        assert len(data) == 0

    def test_dequeue_ready_mixed(self, queue):
        """Only past items are returned from a mixed set."""
        now = datetime.now(timezone.utc)
        queue.save(
            [
                {
                    "url": "http://a.com",
                    "payload": {"device_id": "d1"},
                    "retry_count": 0,
                    "next_retry_at": (now - timedelta(seconds=10)).isoformat(),
                },
                {
                    "url": "http://b.com",
                    "payload": {"device_id": "d1"},
                    "retry_count": 0,
                    "next_retry_at": (now + timedelta(seconds=600)).isoformat(),
                },
                {
                    "url": "http://c.com",
                    "payload": {"device_id": "d1"},
                    "retry_count": 0,
                    "next_retry_at": (now - timedelta(seconds=5)).isoformat(),
                },
            ]
        )
        ready = queue.dequeue_ready()
        assert len(ready) == 2

    def test_dequeue_ready_handles_missing_next_retry_at(self, queue):
        """Items without next_retry_at are treated as ready."""
        queue.save(
            [
                {
                    "url": "http://x.com",
                    "payload": {},
                    "retry_count": 0,
                }
            ]
        )
        ready = queue.dequeue_ready()
        assert len(ready) == 1

    # dequeue_all

    def test_dequeue_all_returns_all_and_clears(self, queue, queue_file):
        """dequeue_all returns every item and empties the file."""
        queue.enqueue(_make_item(url="http://a.com"))
        queue.enqueue(_make_item(url="http://b.com"))
        items = queue.dequeue_all()
        assert len(items) == 2
        assert json.loads(queue_file.read_text("utf-8")) == []

    def test_dequeue_all_ignores_backoff(self, queue):
        """dequeue_all returns future items regardless of backoff."""
        queue.enqueue(_make_item(offset_seconds=600))
        items = queue.dequeue_all()
        assert len(items) == 1

    # clear

    def test_clear_empties_queue(self, queue, queue_file):
        """Clear removes all items from the queue."""
        queue.enqueue(_make_item())
        queue.clear()
        assert json.loads(queue_file.read_text("utf-8")) == []

    def test_clear_on_empty_does_not_raise(self, queue):
        """Clear on an empty queue does not raise."""
        queue.clear()

    # __len__

    def test_len_returns_count(self, queue):
        """len(queue) reflects the number of enqueued items."""
        assert len(queue) == 0
        queue.enqueue(_make_item())
        assert len(queue) == 1
        queue.enqueue(_make_item(url="http://b.com"))
        assert len(queue) == 2

    # file operations

    def test_load_returns_empty_when_no_file(self, queue, queue_file):
        """Load returns [] when the queue file does not exist."""
        assert not queue_file.exists()
        assert queue.load() == []

    def test_load_returns_empty_on_corrupted_file(self, queue, queue_file):
        """Load returns [] when the queue file contains garbage."""
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        queue_file.write_text("garbage", encoding="utf-8")
        assert queue.load() == []

    def test_save_creates_parent_directory(self, queue_file):
        """Save creates intermediate parent directories."""
        nested = queue_file.parent / "sub" / "queue.json"
        queue = RetryQueue(queue_file=nested)
        queue.save([{"url": "http://x.com", "payload": {}}])
        assert nested.exists()
