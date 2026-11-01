"""In-process event bus for investigation run activity.

Publishes structured Server-Sent Events keyed by (session, run, sequence) so
clients can reconnect and replay without duplicating messages. State is held
in memory; this is correct for the single-worker deployment
(``uvicorn ... --workers 1``). A multi-worker deployment would need a shared
backing store (e.g. Redis) — see docs/server-deployment.md.
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass
import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

logger = logging.getLogger(__name__)

# Events that terminate a run's stream.
TERMINAL_EVENTS = {"completed", "failed", "cancelled"}


@dataclass
class RunEvent:
    """A single structured event for a run."""

    seq: int
    event: str
    data: Dict[str, Any]
    session_id: str
    run_id: str
    timestamp: float

    def to_sse(self) -> str:
        """Render this event as an SSE-formatted chunk."""
        payload = {
            "seq": self.seq,
            "event": self.event,
            "session_id": self.session_id,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "data": self.data,
        }
        return f"id: {self.seq}\nevent: {self.event}\ndata: {json.dumps(payload, default=str)}\n\n"


class InvestigationEventBus:
    """Per-run event log + live subscriber queues.

    Single-worker in-process bus. Events are identified by (session, run,
    sequence) and replayed on reconnect.
    """

    def __init__(self, max_buffer: int = 1000, heartbeat_seconds: float = 15.0):
        """Initialise the bus with a bounded per-run replay buffer."""
        self._events: Dict[str, List[RunEvent]] = defaultdict(list)
        self._queues: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self._seq: Dict[str, int] = defaultdict(int)
        self._terminal: Dict[str, bool] = {}
        self._max_buffer = max_buffer
        self._heartbeat = heartbeat_seconds
        self._lock = asyncio.Lock()

    async def publish(
        self,
        session_id: str,
        run_id: str,
        event: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> RunEvent:
        """Publish an event for a run and push to live subscribers."""
        data = data or {}
        async with self._lock:
            self._seq[run_id] += 1
            seq = self._seq[run_id]
            ev = RunEvent(
                seq=seq,
                event=event,
                data=data,
                session_id=session_id,
                run_id=run_id,
                timestamp=time.time(),
            )
            buf = self._events[run_id]
            buf.append(ev)
            if len(buf) > self._max_buffer:
                buf.pop(0)
            if event in TERMINAL_EVENTS:
                self._terminal[run_id] = True
            for q in list(self._queues[run_id]):
                try:
                    q.put_nowait(ev)
                except asyncio.QueueFull:
                    logger.warning(
                        "Event queue full for run %s; dropping live push", run_id
                    )
        return ev

    def has_events(self, run_id: str) -> bool:
        """Return True if any events have been published for *run_id*."""
        return bool(self._events.get(run_id))

    def last_seq(self, run_id: str) -> int:
        """Return the last sequence number published for *run_id*."""
        return self._seq.get(run_id, 0)

    async def subscribe(
        self, session_id: str, run_id: str, last_event_id: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """Yield SSE-formatted events, replaying missed ones then streaming live."""
        start_seq = last_event_id or 0
        # Replay missed events from the buffer.
        for ev in list(self._events.get(run_id, [])):
            if ev.seq > start_seq:
                yield ev.to_sse()
                if ev.event in TERMINAL_EVENTS:
                    return
        # If already terminal, stop.
        if self._terminal.get(run_id):
            return
        # Live stream.
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._queues[run_id].append(q)
        try:
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=self._heartbeat)
                except asyncio.TimeoutError:
                    # Heartbeat comment to keep the connection alive.
                    yield ": heartbeat\n\n"
                    continue
                yield ev.to_sse()
                if ev.event in TERMINAL_EVENTS:
                    break
        except asyncio.CancelledError:
            # Client disconnected; leave the run running server-side.
            raise
        finally:
            try:
                self._queues[run_id].remove(q)
            except ValueError:
                pass


# Process-wide singleton. Single worker => safe.
_bus: Optional[InvestigationEventBus] = None


def get_event_bus() -> InvestigationEventBus:
    """Return the process-wide event bus singleton."""
    global _bus
    if _bus is None:
        _bus = InvestigationEventBus()
    return _bus
