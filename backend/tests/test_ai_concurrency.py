"""Tests for the AI concurrency gate (homepot.app.utils.ai_gate).

These exercise the gate directly with threads: the Ollama client is
synchronous and runs in a worker thread, so the gate's semantics (cap the
number of concurrent generations, bound the wait, always release) are thread
semantics and can be tested without touching Ollama or the event loop.
"""

import threading
import time

import pytest

from homepot.app.utils.ai_gate import AIBusyError, AIConcurrencyGate


def test_gate_serializes_to_one_slot():
    """max_concurrent=1 lets exactly one call run at a time."""
    gate = AIConcurrencyGate(max_concurrent=1)
    lock = threading.Lock()
    state = {"active": 0, "peak": 0}

    def work() -> None:
        with lock:
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
        time.sleep(0.03)
        with lock:
            state["active"] -= 1

    threads = [threading.Thread(target=lambda: gate.run(work)) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert state["peak"] == 1


def test_gate_caps_peak_concurrency_at_limit():
    """max_concurrent=3 never exceeds three simultaneous calls."""
    gate = AIConcurrencyGate(max_concurrent=3)
    lock = threading.Lock()
    state = {"active": 0, "peak": 0}

    def work() -> None:
        with lock:
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
        time.sleep(0.05)
        with lock:
            state["active"] -= 1

    threads = [threading.Thread(target=lambda: gate.run(work)) for _ in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert state["peak"] == 3


def test_gate_raises_busy_when_full_and_times_out():
    """A full gate raises AIBusyError once the queue timeout elapses."""
    gate = AIConcurrencyGate(max_concurrent=1, queue_timeout_seconds=0.1)
    started = threading.Event()
    release = threading.Event()

    def hold_slot() -> None:
        started.set()
        release.wait(2)

    holder = threading.Thread(target=lambda: gate.run(hold_slot))
    holder.start()
    assert started.wait(1)

    with pytest.raises(AIBusyError):
        gate.run(lambda: None)

    release.set()
    holder.join()


def test_gate_waits_indefinitely_without_timeout():
    """With no timeout a queued call proceeds once the slot frees."""
    gate = AIConcurrencyGate(max_concurrent=1)
    order = []
    holding = threading.Event()
    release = threading.Event()

    def first() -> None:
        order.append("first-start")
        holding.set()
        release.wait(2)
        order.append("first-end")

    holder = threading.Thread(target=lambda: gate.run(first))
    holder.start()
    assert holding.wait(1)

    def second() -> None:
        order.append("second")

    waiter = threading.Thread(target=lambda: gate.run(second))
    waiter.start()
    time.sleep(0.05)
    assert "second" not in order  # still waiting for the slot

    release.set()
    holder.join()
    waiter.join()

    assert order == ["first-start", "first-end", "second"]


def test_gate_returns_result_and_releases_after_error():
    """The gate forwards return values and always releases the slot."""
    gate = AIConcurrencyGate(max_concurrent=1)

    assert gate.run(lambda x: x + 1, 41) == 42

    with pytest.raises(ValueError):
        gate.run(lambda: (_ for _ in ()).throw(ValueError("boom")))

    assert gate.free_slots == 1


def test_get_ai_gate_reads_llm_config(monkeypatch):
    """The endpoint helper builds the gate from the LLM config block."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    monkeypatch.setattr(AIEndpoint, "_ai_gate", None)

    class FakeLLM:
        config = {"llm": {"max_concurrent": 3, "queue_timeout_seconds": 12}}

    gate = AIEndpoint.get_ai_gate(FakeLLM())

    assert gate.max_concurrent == 3
    assert gate.queue_timeout_seconds == 12.0

    monkeypatch.setattr(AIEndpoint, "_ai_gate", None)


def test_get_ai_gate_defaults_to_single_slot(monkeypatch):
    """Missing config falls back to a single slot and no timeout."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    monkeypatch.setattr(AIEndpoint, "_ai_gate", None)

    class FakeLLM:
        config = {}

    gate = AIEndpoint.get_ai_gate(FakeLLM())

    assert gate.max_concurrent == 1
    assert gate.queue_timeout_seconds is None

    monkeypatch.setattr(AIEndpoint, "_ai_gate", None)
