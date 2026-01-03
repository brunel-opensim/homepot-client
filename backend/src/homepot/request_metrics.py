"""Module for tracking request metrics."""

import time

# Global Request Counter (Simple in-memory metric)
# In production, use Prometheus/StatsD
_request_count = 0
_last_reset_time = time.time()
_requests_per_minute = 0


def increment_request_count() -> None:
    """Increment the global request counter."""
    global _request_count
    _request_count += 1


def get_request_metrics() -> int:
    """Get current request metrics."""
    global _request_count, _last_reset_time, _requests_per_minute

    # Calculate RPM
    current_time = time.time()
    elapsed = current_time - _last_reset_time

    # If more than 60s passed, reset window
    if elapsed > 60:
        _requests_per_minute = _request_count
        _request_count = 0
        _last_reset_time = current_time
    else:
        # Estimate RPM based on current count and elapsed time
        if elapsed > 0:
            _requests_per_minute = int((_request_count / elapsed) * 60)

    return _requests_per_minute
