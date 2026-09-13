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

# A minimum elapsed time before a disk I/O delta is treated as a rate.
_DISK_IO_MIN_INTERVAL_SECONDS = 1.0

# Seed psutil's blocked-CPU baseline at import so the first interval-average
# sample reflects utilization since process start instead of returning 0.0.
psutil.cpu_percent(interval=None)

# Seed the disk I/O baseline at import so each read reports the genuine
# throughput since the previous read (bytes per second).
_last_disk_io_ts: Optional[float]

try:
    _last_disk_io = psutil.disk_io_counters()
    _last_disk_io_ts = time.time()
except Exception:  # noqa: BLE001 - unreadable counters degrade to zero rate
    _last_disk_io = None
    _last_disk_io_ts = None


def utc_now_iso() -> str:
    """Return current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def collect_uptime_seconds() -> int:
    """Return host OS uptime in whole seconds derived from the boot time.

    The backend ``AgentTelemetryRequest`` schema expects ``uptime_seconds``
    as an integer, so the fractional part is truncated here.
    """
    try:
        return int(max(0.0, time.time() - psutil.boot_time()))
    except Exception:
        return 0


def _disk_io_bytes_per_second() -> float:
    """Return combined disk read/write throughput (bytes/s) since the last read.

    Returns ``0.0`` when the OS exposes no per-disk counters or too little
    time has elapsed since the previous sample to form a meaningful rate.
    """
    global _last_disk_io, _last_disk_io_ts
    now_ts = time.time()
    now_io = psutil.disk_io_counters()
    rate = 0.0
    if (
        now_io is not None
        and _last_disk_io is not None
        and _last_disk_io_ts is not None
    ):
        dt = now_ts - _last_disk_io_ts
        if dt >= _DISK_IO_MIN_INTERVAL_SECONDS:
            read_bytes = max(0.0, now_io.read_bytes - _last_disk_io.read_bytes)
            write_bytes = max(0.0, now_io.write_bytes - _last_disk_io.write_bytes)
            rate = (read_bytes + write_bytes) / dt
    _last_disk_io = now_io
    _last_disk_io_ts = now_ts
    return rate


def collect_system_telemetry() -> Dict[str, float]:
    """Collect basic CPU, memory, disk, and uptime metrics from the host.

    ``cpu_usage`` is the average utilization since the previous call in the
    same process (honest per-read sample over the collection interval) rather
    than a short blocking snapshot; the baseline is seeded at import.
    ``disk_io_bytes_s`` is the combined read/write throughput (bytes per
    second) measured since the previous read.
    """
    return {
        "cpu_usage": float(round(max(0.0, psutil.cpu_percent(interval=None)), 1)),
        "memory_usage": float(psutil.virtual_memory().percent),
        "disk_usage": float(psutil.disk_usage("/").percent),
        "disk_io_bytes_s": float(round(_disk_io_bytes_per_second(), 1)),
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
