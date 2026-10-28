"""Heartbeat payload utilities for the real device agent."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utc_now_iso() -> str:
    """Return current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def build_heartbeat_payload(
    device_id: str,
    *,
    site_id: Optional[str] = None,
    status: str = "ONLINE",
    online: bool = True,
    agent_uptime_seconds: Optional[int] = None,
    agent_restart_count: Optional[int] = None,
    task_health: Optional[Dict[str, bool]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a standardized heartbeat payload for backend submission."""
    payload: Dict[str, Any] = {
        "device_id": device_id,
        "timestamp": utc_now_iso(),
        "status": status,
        "online": online,
    }
    if site_id:
        payload["site_id"] = site_id
    if agent_uptime_seconds is not None:
        payload["agent_uptime_seconds"] = agent_uptime_seconds
    if agent_restart_count is not None:
        payload["agent_restart_count"] = agent_restart_count
    if task_health is not None:
        payload["task_health"] = task_health
    if extra:
        payload["extra"] = extra
    return payload
