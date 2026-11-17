"""Readiness checks in ``tools/ai-soak-test.py``.

A run started while the soak device was offline sent all 24 prompts, had every
proposal refused by the connectivity gate, and measured nothing — the readiness
report had listed the stale poll as a *warning* and started anyway.

``evaluate_readiness`` is loaded straight from the script so these tests pin the
behaviour the operator sees, not a copy of it.
"""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "ai-soak-test.py"


@pytest.fixture(scope="module")
def soak():
    """Load the soak script as a module without running it."""
    spec = importlib.util.spec_from_file_location("ai_soak_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_offline_device_blocks_the_run(soak):
    """An offline device refuses every proposal, so do not start."""
    ready, problems, _ = soak.evaluate_readiness(
        {"lifecycle_state": "active", "connectivity_state": "offline"}, []
    )
    assert not ready
    assert any("connectivity_state is 'offline'" in p for p in problems), problems


def test_suspended_connectivity_state_blocks_the_run(soak):
    """Any non-online state refuses proposals, not only 'offline'."""
    ready, problems, _ = soak.evaluate_readiness(
        {"lifecycle_state": "active", "connectivity_state": "Suspended"}, []
    )
    assert not ready
    assert any("'suspended'" in p for p in problems), problems


def test_online_device_is_ready(soak):
    """The happy path still passes."""
    ready, problems, _ = soak.evaluate_readiness(
        {
            "lifecycle_state": "active",
            "connectivity_state": "online",
            "last_seen": "2026-11-16T15:04:00+00:00",
        },
        [],
    )
    assert ready, problems


def test_missing_connectivity_state_stays_a_warning(soak):
    """Older records may not carry the field; last-seen staleness only warns."""
    ready, problems, warnings = soak.evaluate_readiness(
        {"lifecycle_state": "active"}, []
    )
    assert ready, problems
    assert any("last_seen" in w for w in warnings), warnings
