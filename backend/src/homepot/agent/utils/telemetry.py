"""Telemetry payload utilities for the real device agent."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import psutil


def utc_now_iso() -> str:
    """Return current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def collect_system_telemetry() -> Dict[str, float]:
    """Collect basic CPU, memory, and disk usage metrics from the host."""
    return {
        "cpu_usage": float(psutil.cpu_percent(interval=0.1)),
        "memory_usage": float(psutil.virtual_memory().percent),
        "disk_usage": float(psutil.disk_usage("/").percent),
    }


def build_telemetry_payload(
    device_id: str, *, extra: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build telemetry payload using host metrics and optional extra fields."""
    payload: Dict[str, Any] = {"device_id": device_id, "timestamp": utc_now_iso()}
    payload.update(collect_system_telemetry())
    if extra:
        payload["extra"] = extra
    return payload
