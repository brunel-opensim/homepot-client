import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Subscribe to an investigation run's Server-Sent Events stream.
 *
 * Returns { events, latest, connected, error }.
 * - events: array of received events (in order).
 * - latest: the most recent event.
 * - connected: whether the stream is currently open.
 * - error: last error message (if any).
 *
 * Reconnection is handled by the browser's EventSource (auto-reconnect with
 * Last-Event-ID). The hook cleans up on unmount.
 */
export function useRunEvents(sessionId, runId) {
  const [events, setEvents] = useState([]);
  const [latest, setLatest] = useState(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState(null);
  const esRef = useRef(null);
  const lastSeqRef = useRef(0);

  useEffect(() => {
    if (!sessionId || !runId) {
      setEvents([]);
      setLatest(null);
      setConnected(false);
      setError(null);
      return undefined;
    }

    const url = `/api/v1/investigations/${encodeURIComponent(sessionId)}/runs/${encodeURIComponent(runId)}/events`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      setConnected(true);
      setError(null);
    };

    es.onerror = () => {
      setConnected(false);
      setError('Connection lost; retrying...');
    };

    // Generic message handler for any event type.
    const handler = (event) => {
      let data = null;
      try {
        data = JSON.parse(event.data);
      } catch {
        data = { raw: event.data };
      }
      const seq = data?.seq ?? lastSeqRef.current + 1;
      lastSeqRef.current = Math.max(lastSeqRef.current, seq);
      const ev = { id: event.lastEventId || String(seq), type: event.type, data, seq };
      setEvents((prev) => [...prev, ev]);
      setLatest(ev);
    };

    // Listen for all named events we publish.
    const eventTypes = [
      'session_created',
      'message_added',
      'run_queued',
      'run_started',
      'context_ready',
      'gates_complete',
      'llm_started',
      'llm_complete',
      'memory_written',
      'completed',
      'cancelled',
      'failed',
    ];
    eventTypes.forEach((t) => es.addEventListener(t, handler));

    // Also handle default 'message' events.
    es.onmessage = handler;

    return () => {
      es.close();
      esRef.current = null;
      setConnected(false);
    };
  }, [sessionId, runId]);

  const close = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
      setConnected(false);
    }
  }, []);

  return { events, latest, connected, error, close };
}
