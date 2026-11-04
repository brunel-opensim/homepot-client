"""Smoke tests for Gate B tool-output annotation (B9)."""

import asyncio
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from ai.tools import _gate_b_note  # noqa: E402


def test_gate_b_note_returns_string_when_db_unavailable():
    """Gate B note degrades gracefully without a DB."""
    # Without a configured async DB service the helper must degrade gracefully.
    note = asyncio.run(_gate_b_note("NONEXISTENT-DEVICE"))
    assert isinstance(note, str)
    assert note.startswith("[Gate B:")
