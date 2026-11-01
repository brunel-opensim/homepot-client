"""Tests for the investigation event bus (Stage 3 Phase A)."""

import asyncio

import pytest

from homepot.app.events.investigation_events import InvestigationEventBus


@pytest.mark.asyncio
async def test_publish_and_replay():
    bus = InvestigationEventBus()
    await bus.publish("s1", "r1", "run_started", {"x": 1})
    await bus.publish("s1", "r1", "completed", {"ok": True})

    # Replay from 0 returns both
    chunks = []
    async for c in bus.subscribe("s1", "r1", last_event_id=0):
        chunks.append(c)
    assert len(chunks) == 2
    assert "run_started" in chunks[0]
    assert "completed" in chunks[1]

    # Replay from 1 returns only the second
    chunks2 = []
    async for c in bus.subscribe("s1", "r1", last_event_id=1):
        chunks2.append(c)
    assert len(chunks2) == 1
    assert "completed" in chunks2[0]


@pytest.mark.asyncio
async def test_event_ids_monotonic():
    bus = InvestigationEventBus()
    e1 = await bus.publish("s1", "r1", "run_started", {})
    e2 = await bus.publish("s1", "r1", "completed", {})
    assert e2.seq == e1.seq + 1
    assert e1.seq == 1


@pytest.mark.asyncio
async def test_terminal_marks_stream_end():
    bus = InvestigationEventBus()
    await bus.publish("s1", "r1", "run_started", {})
    await bus.publish("s1", "r1", "completed", {})
    # After terminal, subscribe yields nothing new (already complete)
    chunks = []
    async for c in bus.subscribe("s1", "r1", last_event_id=2):
        chunks.append(c)
    assert chunks == []


@pytest.mark.asyncio
async def test_separate_runs_isolated():
    bus = InvestigationEventBus()
    await bus.publish("s1", "r1", "run_started", {})
    await bus.publish("s1", "r1", "completed", {})
    await bus.publish("s1", "r2", "run_started", {})
    await bus.publish("s1", "r2", "completed", {})
    assert bus.last_seq("r1") == 2
    assert bus.last_seq("r2") == 2
    chunks = []
    async for c in bus.subscribe("s1", "r1", last_event_id=0):
        chunks.append(c)
    assert len(chunks) == 2