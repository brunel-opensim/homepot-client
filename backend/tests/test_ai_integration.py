"""Integration tests for AI Core Components."""

import os
import sys

# Add ai directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
ai_dir = os.path.join(workspace_root, "ai")
if ai_dir not in sys.path:
    sys.path.insert(0, ai_dir)

from analysis_modes import AnalysisMode, ModeManager  # noqa: E402
from event_store import EventStore  # noqa: E402


def test_event_store_caching():
    """Test that EventStore caches events correctly."""
    store = EventStore(config_path="non_existent.yaml")

    # Add event
    event = {"device_id": "dev1", "event": "test", "value": 123}
    store.add_event(event)

    # Retrieve
    events = store.get_recent_events("dev1")
    assert len(events) == 1
    assert events[0]["value"] == 123
    assert "timestamp" in events[0]


def test_event_store_limit():
    """Test that EventStore respects cache limit."""
    store = EventStore(config_path="non_existent.yaml")
    store.cache_limit = 5

    for i in range(10):
        store.add_event({"device_id": "dev1", "value": i})

    events = store.get_recent_events("dev1")
    assert len(events) == 5
    assert events[-1]["value"] == 9


def test_event_store_summary():
    """Test event summary generation."""
    store = EventStore(config_path="non_existent.yaml")
    store.add_event({"device_id": "dev1", "event": "error", "value": "timeout"})

    summary = store.get_events_summary("dev1")
    assert "error" in summary
    assert "timeout" in summary


def test_mode_manager_defaults():
    """Test ModeManager default state."""
    manager = ModeManager()
    assert manager.current_mode == AnalysisMode.MAINTENANCE
    assert "technical systems analyst" in manager.get_system_prompt()


def test_mode_manager_switching():
    """Test switching modes."""
    manager = ModeManager()

    manager.set_mode("predictive")
    assert manager.current_mode == AnalysisMode.PREDICTIVE
    assert "predictive maintenance expert" in manager.get_system_prompt()

    manager.set_mode("executive")
    assert manager.current_mode == AnalysisMode.EXECUTIVE
    assert "executive reporting assistant" in manager.get_system_prompt()


def test_mode_manager_invalid_mode():
    """Test setting invalid mode (should stay on current)."""
    manager = ModeManager()
    original_mode = manager.current_mode

    manager.set_mode("invalid_mode")
    assert manager.current_mode == original_mode
