"""Telemetry payload utilities for the real device agent.

Provides system metric collection (CPU, memory, disk, uptime), a genuine
network-latency measurement against the backend, and a config-gated seam
for permitted POS/application signals.

Per the KPI evaluation roadmap, operational POS KPIs remain **excluded**
until a data-source agreement and side-by-side source validation exist;
``collect_pos_signals`` is inert unless a source path is configured.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, Dict, Optional

import psutil


def utc_now_iso() -> str:
    """Return current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def collect_uptime_seconds() -> float:
    """Return host OS uptime in seconds derived from the boot time."""
    try:
        return max(0.0, time.time() - psutil.boot_time())
    except Exception:
        return 0.0


def collect_system_telemetry() -> Dict[str, float]:
    """Collect basic CPU, memory, disk, and uptime metrics from the host."""
    return {
        "cpu_usage": float(psutil.cpu_percent(interval=0.1)),
        "memory_usage": float(psutil.virtual_memory().percent),
        "disk_usage": float(psutil.disk_usage("/").percent),
        "uptime_seconds": collect_uptime_seconds(),
    }


async def measure_network_latency_ms(
    client: Any, backend_url: str, *, timeout: float = 5.0
) -> Optional[float]:
    """Measure end-to-end round-trip latency to the backend in milliseconds.

    Sends a lightweight ``GET`` to the backend root URL and returns the
    elapsed time in milliseconds, or ``None`` when the backend is
    unreachable or the request fails.
    """
    url = f"{backend_url.rstrip('/')}/"
    start = time.perf_counter()
    try:
        await client.get(url, timeout=timeout)
    except Exception:
        # Transport errors (unreachable, timeout, DNS) yield no measurement.
        return None
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return elapsed_ms


def collect_pos_signals(source: Optional[str]) -> Optional[Dict[str, Any]]:
    """Collect permitted POS/application signals from a configured source.

    Reads a JSON file whose top level is an object of POS metrics (for
    example ``transaction_count``, ``transaction_volume``, ``error_rate``).
    Returns ``None`` when no ``source`` is configured (the default) so the
    agent never fabricates POS data.  This seam stays inert until a
    data-source agreement and side-by-side source validation exist.
    """
    if not source:
        return None
    try:
        data = json.loads(Path(source).read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data


def build_telemetry_payload(
    device_id: str,
    *,
    extra: Optional[Dict[str, Any]] = None,
    network_latency_ms: Optional[float] = None,
    collection_interval_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    """Build telemetry payload using host metrics and optional extra fields.

    The payload timestamp is the device sample time (UTC ISO-8601) used as
    the PF-02 latency reference point.
    """
    payload: Dict[str, Any] = {
        "device_id": device_id,
        "timestamp": utc_now_iso(),
    }
    payload.update(collect_system_telemetry())
    if network_latency_ms is not None:
        payload["network_latency_ms"] = network_latency_ms
    if collection_interval_seconds is not None:
        payload["collection_interval_seconds"] = collection_interval_seconds
    if extra:
        payload["extra"] = extra
    return payload
