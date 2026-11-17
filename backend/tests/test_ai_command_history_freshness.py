"""Regression tests for freshness labelling of command history in AI context.

Old command results must stay available for audit but must not reach the model
as if they were live readings. These tests pin the split introduced for the
real-device soak: results inside the fresh window are shown, older results are
labelled historical and stripped of their payload.
"""

from datetime import datetime, timedelta, timezone
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from ai.agent import AGENT_SYSTEM_PROMPT  # noqa: E402
from ai.context_builder import (  # noqa: E402
    COMMAND_HISTORY_FRESH_WINDOW_MINUTES,
    ContextBuilder,
    command_age_seconds,
    format_command_age,
)
from ai.tools import get_command, get_command_history  # noqa: E402


def _command(age_seconds: float, marker: str) -> SimpleNamespace:
    """Build a lightweight command row with a given age and result marker."""
    created = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    return SimpleNamespace(
        command_id=f"cmd-{marker}",
        command_type="tail_system_log",
        status="completed",
        created_at=created,
        executed_at=created,
        issued_by="tech@example.test",
        device_id=7,
        payload={"lines": 20},
        result={"message": marker},
    )


def _session_with(commands: list) -> AsyncMock:
    """Return a mock session whose execute calls resolve device and commands."""
    device_result = MagicMock()
    device_result.scalar_one_or_none.return_value = 7
    command_result = MagicMock()
    command_result.scalars.return_value.all.return_value = commands
    session = AsyncMock()
    session.execute.side_effect = [device_result, command_result]
    return session


@pytest.mark.asyncio
async def test_command_context_omits_stale_result_but_keeps_fresh_one():
    """Only results inside the fresh window reach the model."""
    session = _session_with(
        [_command(60, "FRESH_MARKER"), _command(7200, "STALE_MARKER")]
    )

    context = await ContextBuilder._get_command_context_impl(session, "DEV-1", 5)

    assert "FRESH_MARKER" in context
    assert "STALE_MARKER" not in context
    assert "fresh" in context
    assert "historical" in context
    assert "not live readings" in context
    assert f"{COMMAND_HISTORY_FRESH_WINDOW_MINUTES} minutes" in context


@pytest.mark.asyncio
async def test_command_context_uses_execution_time_for_freshness():
    """A command queued earlier but just executed is still a fresh result."""
    command = _command(3 * 3600, "RECENT_EXEC")
    command.executed_at = datetime.now(timezone.utc) - timedelta(seconds=60)

    context = await ContextBuilder._get_command_context_impl(
        _session_with([command]), "DEV-1", 5
    )

    assert "RECENT_EXEC" in context
    assert "fresh" in context


@pytest.mark.asyncio
async def test_command_context_keeps_metadata_for_stale_commands():
    """A stale command remains visible as audit metadata, with an age label."""
    stale = _command(3 * 3600, "OLD_MARKER")

    context = await ContextBuilder._get_command_context_impl(
        _session_with([stale]), "DEV-1", 5
    )

    assert "tail_system_log" in context
    assert "3h ago" in context
    assert "historical" in context
    assert "payload=" in context
    assert "OLD_MARKER" not in context


@pytest.mark.asyncio
async def test_get_command_history_passes_freshness_note_through():
    """The agent-facing tool returns the labelled context unchanged."""
    with patch("ai.tools.ContextBuilder") as mock_cb:
        mock_cb.get_command_context = AsyncMock(return_value="[labelled history]")
        result = await get_command_history("DEV-1")

    assert result == "[labelled history]"
    assert "30 minutes" in get_command_history.__doc__


@pytest.mark.asyncio
async def test_get_command_marks_old_result_as_not_live():
    """Detailed command lookups also carry an explicit historical warning."""
    db = AsyncMock()
    db.get_command = AsyncMock(return_value=_command(3 * 3600, "OLD_DETAIL"))
    db.get_device_by_device_id = AsyncMock(return_value=SimpleNamespace(id=7))

    with patch("homepot.database.get_database_service", AsyncMock(return_value=db)):
        result = await get_command("DEV-1", "cmd-OLD_DETAIL")

    assert "OLD_DETAIL" in result
    assert "not a live reading" in result
    assert "3h ago" in result
    assert "fresh window" in result


def test_agent_prompt_forbids_answers_from_past_command_results():
    """The system prompt must state that command records are not live data."""
    assert (
        "get_command_history and get_command return historical command records"
        in AGENT_SYSTEM_PROMPT
    )
    assert "Propose a fresh action instead" in AGENT_SYSTEM_PROMPT


def test_command_age_helpers_handle_naive_timestamps_and_missing_values():
    """Naive timestamps are UTC and absent timestamps render as unknown."""
    now = datetime.now(timezone.utc)
    naive = (now - timedelta(minutes=5)).replace(tzinfo=None)

    assert command_age_seconds(naive, now) == pytest.approx(300, abs=1)
    assert command_age_seconds(None, now) is None
    assert format_command_age(None) == "unknown age"
    assert format_command_age(90) == "1m ago"
