"""Tests for EventStore database integration."""

import os
import sys
from unittest.mock import MagicMock, patch

# Add ai directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
ai_dir = os.path.join(workspace_root, "ai")
if ai_dir not in sys.path:
    sys.path.insert(0, ai_dir)

from event_store import EventStore  # noqa: E402


def test_persist_event_sql_generation():
    """Test that _persist_event generates correct SQL."""
    # Mock engine and connection
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # Initialize store with mock engine
    with patch("event_store.create_engine", return_value=mock_engine):
        store = EventStore(config_path="non_existent.yaml")
        store.engine = mock_engine  # Force engine assignment

        event = {
            "device_id": "dev1",
            "timestamp": "2025-01-01T12:00:00",
            "event": "metrics_update",
            "value": {
                "cpu_percent": 50.0,
                "memory_percent": 60.0,
                "disk_percent": 70.0,
                "network_latency_ms": 10.0,
                "error_rate": 0.01,
            },
        }

        store._persist_event(event)

        # Verify execute was called
        assert mock_conn.execute.called
        args, kwargs = mock_conn.execute.call_args

        # Check parameters
        params = args[1]
        assert params["device_id"] == "dev1"
        assert params["cpu"] == 50.0
        assert params["memory"] == 60.0


def test_get_recent_events_db_fallback():
    """Test that get_recent_events falls back to DB if cache is empty."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # Mock DB result
    MockRow = MagicMock()
    MockRow.device_id = "dev1"
    MockRow.timestamp = MagicMock()
    MockRow.timestamp.isoformat.return_value = "2025-01-01T12:00:00"
    MockRow.cpu_percent = 50.0
    MockRow.memory_percent = 60.0
    MockRow.disk_percent = 70.0
    MockRow.network_latency_ms = 10.0
    MockRow.error_rate = 0.01

    mock_conn.execute.return_value = [MockRow]

    with patch("event_store.create_engine", return_value=mock_engine):
        store = EventStore(config_path="non_existent.yaml")
        store.engine = mock_engine

        # Ensure cache is empty
        store.cache = {}

        events = store.get_recent_events("dev1")

        assert len(events) == 1
        assert events[0]["device_id"] == "dev1"
        assert events[0]["value"]["cpu_percent"] == 50.0
        assert mock_conn.execute.called
