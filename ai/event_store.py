"""Event Store module for caching and retrieving device events."""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List

import yaml
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


class EventStore:
    """Manages storage and retrieval of device events."""

    def __init__(self, config_path: str | None = None) -> None:
        """Initialize the EventStore with configuration."""
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.yaml")

        self.config = self._load_config(config_path)
        self.db_url = self.config.get("database", {}).get("url")
        self.engine: Engine | None = None

        if self.db_url:
            try:
                self.engine = create_engine(self.db_url)
                logger.info("Connected to event database.")
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")

        # In-memory cache for recent events: {device_id: [events]}
        self.cache: Dict[str, List[Dict[str, Any]]] = {}
        self.cache_limit = 100

    def _load_config(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, "r") as f:
                config = yaml.safe_load(f)
                if isinstance(config, dict):
                    return config
                return {}
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}

    def add_event(self, event: Dict[str, Any]) -> None:
        """Add an event to the store and cache."""
        device_id = event.get("device_id")
        if not device_id:
            logger.warning("Event missing device_id, skipping.")
            return

        # Add to cache
        if device_id not in self.cache:
            self.cache[device_id] = []

        # Add timestamp if missing
        if "timestamp" not in event:
            event["timestamp"] = datetime.now().isoformat()

        self.cache[device_id].append(event)

        # Trim cache
        if len(self.cache[device_id]) > self.cache_limit:
            self.cache[device_id] = self.cache[device_id][-self.cache_limit :]

        # Persist to DB (Optional/Async in real impl)
        if self.engine:
            self._persist_event(event)

    def _persist_event(self, event: Dict[str, Any]) -> None:
        """Persist event to database."""
        if not self.engine:
            return

        try:
            # We map the generic 'event' to the 'device_metrics' table structure
            # Assuming 'value' contains the metrics dict
            metrics = event.get("value", {})
            if not isinstance(metrics, dict):
                # If value is not a dict, we might be storing a different type of event
                # For now, we only support metrics updates in this table
                return

            query = text(
                """
                INSERT INTO device_metrics (
                    device_id, timestamp, cpu_percent, memory_percent,
                    disk_percent, network_latency_ms, error_rate
                ) VALUES (
                    :device_id, :timestamp, :cpu, :memory, :disk, :latency, :error_rate
                )
            """
            )

            with self.engine.connect() as conn:
                conn.execute(
                    query,
                    {
                        "device_id": event.get("device_id"),
                        "timestamp": event.get("timestamp"),
                        "cpu": metrics.get("cpu_percent"),
                        "memory": metrics.get("memory_percent"),
                        "disk": metrics.get("disk_percent"),
                        "latency": metrics.get("network_latency_ms"),
                        "error_rate": metrics.get("error_rate"),
                    },
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to persist event: {e}")

    def get_recent_events(
        self, device_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent events for a device."""
        # Try cache first
        if device_id in self.cache and self.cache[device_id]:
            return self.cache[device_id][-limit:]

        # Fallback to DB if cache empty
        if self.engine:
            try:
                query = text(
                    """
                    SELECT * FROM device_metrics
                    WHERE device_id = :device_id
                    ORDER BY timestamp DESC
                    LIMIT :limit
                """
                )
                with self.engine.connect() as conn:
                    result = conn.execute(
                        query, {"device_id": device_id, "limit": limit}
                    )
                    events = []
                    for row in result:
                        # Convert row to event format
                        events.append(
                            {
                                "device_id": row.device_id,
                                "timestamp": (
                                    row.timestamp.isoformat() if row.timestamp else None
                                ),
                                "event": "metrics_update",
                                "value": {
                                    "cpu_percent": row.cpu_percent,
                                    "memory_percent": row.memory_percent,
                                    "disk_percent": row.disk_percent,
                                    "network_latency_ms": row.network_latency_ms,
                                    "error_rate": row.error_rate,
                                },
                            }
                        )
                    # Reverse to chronological order
                    return events[::-1]
            except Exception as e:
                logger.error(f"Failed to fetch events from DB: {e}")

        return []

    def get_events_summary(self, device_id: str) -> str:
        """Generate a text summary of recent events for LLM context."""
        events = self.get_recent_events(device_id)
        if not events:
            return "No recent events found."

        summary = []
        for e in events:
            timestamp = e.get("timestamp", "Unknown time")
            event_type = e.get("event", "Unknown event")
            value = e.get("value", "N/A")
            summary.append(f"- [{timestamp}] {event_type}: {value}")

        return "\n".join(summary)
