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
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a standardized heartbeat payload for backend submission."""
    payload: Dict[str, Any] = {
        "device_id": device_id,
        "timestamp": utc_now_iso(),
        "status": status,
    }
    if site_id:
        payload["site_id"] = site_id
    if extra:
        payload["extra"] = extra
    return payload
