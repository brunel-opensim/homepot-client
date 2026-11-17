"""Device context carried forward from AI conversation history.

A technician asked about Brunel Device 001 but the chat had earlier mentioned
a device that was later removed. The endpoint copied that id into
``[FOCUS DEVICE]`` without checking it, Gate D rejected it, and no proposal
could be created — for a device that did exist. The history helper must only
carry forward ids that still resolve.
"""

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from homepot.app.api.API_v1.Endpoints import AIEndpoint  # noqa: E402

STALE = "DEVICE-Z9SG-UZBS-58S2"
VALID = "DEVICE-HSZK-T24Y-TSCX"
OTHER = "DEVICE-ABCD-EFGH-JKMN"


class FakeResolver:
    """Resolve only the ids still present in the registry."""

    def __init__(self, session):
        """Record the session; the real resolver needs one."""
        self.session = session

    async def resolve(self, device_id):
        """Return an integer id for registered devices, None otherwise."""
        return 42 if device_id in (VALID, OTHER) else None


def _messages(*contents):
    """Build minimal history messages with a ``content`` attribute."""
    return [SimpleNamespace(content=text) for text in contents]


@pytest.mark.asyncio
async def test_newest_registered_device_wins():
    """Normal carry-forward still picks the most recent turn."""
    history = _messages(f"Check {OTHER}", f"Now check {VALID}")
    with patch.object(AIEndpoint, "DeviceResolver", FakeResolver):
        assert await AIEndpoint._resolve_history_device_id(history, object()) == VALID


@pytest.mark.asyncio
async def test_stale_device_is_skipped_in_favour_of_an_older_valid_one():
    """A removed device must not block a question about a real one."""
    history = _messages(f"Check {VALID}", f"Earlier I checked {STALE}")
    with patch.object(AIEndpoint, "DeviceResolver", FakeResolver):
        assert await AIEndpoint._resolve_history_device_id(history, object()) == VALID


@pytest.mark.asyncio
async def test_all_stale_returns_none():
    """No valid device in history means no focus device, not a blocked query."""
    history = _messages(f"Check {STALE}")
    with patch.object(AIEndpoint, "DeviceResolver", FakeResolver):
        assert await AIEndpoint._resolve_history_device_id(history, object()) is None


@pytest.mark.asyncio
async def test_last_id_in_one_message_still_wins():
    """Preserve the previous behaviour within a single message."""
    history = _messages(f"Compare {OTHER} with {VALID}")
    with patch.object(AIEndpoint, "DeviceResolver", FakeResolver):
        assert await AIEndpoint._resolve_history_device_id(history, object()) == VALID


@pytest.mark.asyncio
async def test_unrelated_text_is_ignored():
    """Free text without a canonical id carries nothing forward."""
    history = _messages("What does Gate D do?", "DEVICE-not-a-real-id")
    with patch.object(AIEndpoint, "DeviceResolver", FakeResolver):
        assert await AIEndpoint._resolve_history_device_id(history, object()) is None
