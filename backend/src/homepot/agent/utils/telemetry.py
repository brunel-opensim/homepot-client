"""Telemetry payload utilities for the real device agent.

Provides system metric collection (CPU, memory, disk, uptime), a genuine
network-latency measurement against the backend, and a config-gated seam
for permitted POS/application signals.

Per the KPI evaluation roadmap, operational POS KPIs remain **excluded**
until a data-source agreement and side-by-side source validation exist;
``collect_pos_signals`` is inert unless a source path is configured.
"""

from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock
import time
from typing import Any, Deque, Dict, Optional, Tuple

import psutil

# A minimum elapsed time before a disk I/O delta is treated as a rate.
_DISK_IO_MIN_INTERVAL_SECONDS = 1.0

# Disk throughput is reported over a sliding window the size of the telemetry
# cadence, so the rate is stable regardless of how often this module is
# sampled between telemetry posts (other loops also collect host metrics).
_DISK_IO_WINDOW_SECONDS = 30.0
_DISK_IO_MAX_SAMPLES = 10_000

# Seed psutil's blocked-CPU baseline at import so the first interval-average
# sample reflects utilization since process start instead of returning 0.0.
psutil.cpu_percent(interval=None)

# Sliding history of (wall-clock, (read_bytes, write_bytes)) snapshots. The
# stored baseline behind a window-sized ``dt`` is used to report throughput
# that is independent of how frequently a caller samples this module.
_disk_io_baseline_lock = Lock()
DiskIoSample = Tuple[float, Tuple[float, float]]
_disk_io_samples: Deque[DiskIoSample] = deque()

try:
    counters = psutil.disk_io_counters()
    if counters is not None:
        _disk_io_samples.append(
            (time.time(), (counters.read_bytes, counters.write_bytes))
        )
except Exception:  # noqa: BLE001 - unreadable counters degrade to zero rate
    pass


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
    """Return combined disk read/write throughput (bytes/s) over a sliding window.

    The rate is computed between the most recent counter snapshot and an
    anchor snapshot roughly ``_DISK_IO_WINDOW_SECONDS`` in the past.  Because
    the anchor is retained across rapid successive calls, the reported rate
    reflects genuine disk activity since the last meaningful interval rather
    than a sub-second sliver (which would round to ``0.0`` for callers that
    sample immediately after another loop).

    Returns ``0.0`` when the OS exposes no per-disk counters, too little time
    has elapsed since the anchor, or the counters are unavailable.
    """
    global _disk_io_samples
    with _disk_io_baseline_lock:
        now_ts = time.time()
        now_io = psutil.disk_io_counters()
        if now_io is None:
            return 0.0
        now_sample: DiskIoSample = (
            now_ts,
            (now_io.read_bytes, now_io.write_bytes),
        )
        _disk_io_samples.append(now_sample)

        # Drop front samples until the front is at least a window behind now,
        # but never empty the history: the retained front acts as the anchor.
        while (
            len(_disk_io_samples) >= 2
            and now_ts - _disk_io_samples[1][0] >= _DISK_IO_WINDOW_SECONDS
        ):
            _disk_io_samples.popleft()
        if len(_disk_io_samples) > _DISK_IO_MAX_SAMPLES:
            # Preserve the current anchor sample at index 0 and evict the
            # oldest non-anchor samples until within the cap.
            while len(_disk_io_samples) > _DISK_IO_MAX_SAMPLES:
                _disk_io_samples.rotate(-1)
                _disk_io_samples.popleft()
                _disk_io_samples.rotate(1)

        anchor_ts, anchor_io = _disk_io_samples[0]
        dt = now_ts - anchor_ts
        if dt < _DISK_IO_MIN_INTERVAL_SECONDS:
            return 0.0
        read_bytes = max(0.0, now_io.read_bytes - anchor_io[0])
        write_bytes = max(0.0, now_io.write_bytes - anchor_io[1])
        return (read_bytes + write_bytes) / dt


def collect_system_telemetry() -> Dict[str, float]:
    """Collect basic CPU, memory, disk, and uptime metrics from the host.

    ``cpu_usage`` is the average utilization since the previous call in the
    same process (honest per-read sample over the collection interval) rather
    than a short blocking snapshot; the baseline is seeded at import.
    ``disk_io_bytes_s`` is the combined read/write throughput (bytes per
    second) over a sliding window matching the telemetry cadence, so it
    stays meaningful even when other loops sample metrics in between.
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
