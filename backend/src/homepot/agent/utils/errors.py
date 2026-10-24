"""Delivery-failure classification for the on-device agent.

The agent talks to the backend over a lossy, intermittently available network.
Some failures are transient (timeouts, connection resets, ``5xx``) and should
be retried with backoff; others are permanent (the device credential/lifecycle
is dead, or the target resource is gone/conflicted) and must **not** be
retried — retrying them forever spams the backend with dead credentials (see
``docs/device-offline-resilience.md``, gap 6, and the stale-device scenario).
"""

from typing import Optional

# Statuses that mean "this request will never succeed as-is; do not retry".
PERMANENT_STATUS_CODES = frozenset({401, 403, 404, 409})

# Statuses that mean "the device credential/lifecycle is dead — stop polling".
# 401 = unknown device / invalid API key, 403 = lifecycle not active (suspended
# or unpaired). These are returned by the backend's device-auth layer.
DEVICE_TERMINAL_STATUS_CODES = frozenset({401, 403})


def is_permanent_status(status_code: int) -> bool:
    """Return ``True`` for a status that must never be retried."""
    return status_code in PERMANENT_STATUS_CODES


def is_device_terminal_status(status_code: int) -> bool:
    """Return ``True`` for a status that means the device credential is dead."""
    return status_code in DEVICE_TERMINAL_STATUS_CODES


class PermanentFailureError(Exception):
    """Base class for permanent (non-retryable) delivery failures.

    Never raised directly — catch the concrete subclasses below.
    """


class PermanentDeliveryError(PermanentFailureError):
    """The request target is gone/conflicted (404/409); drop it, do not retry."""

    def __init__(self, url: str, status_code: int) -> None:
        """Record the failing URL and HTTP status for diagnostics."""
        self.url = url
        self.status_code = status_code
        super().__init__(f"Permanent delivery failure (HTTP {status_code}) for {url}")


class DeviceRemovedError(PermanentFailureError):
    """The device credential/lifecycle is dead (401/403); stop polling.

    Raised when the backend's device-auth layer rejects the device. The agent
    should stop its backend loops and surface a terminal "removed from backend"
    state rather than retrying forever.
    """

    def __init__(self, url: str, status_code: int) -> None:
        """Record the failing URL and HTTP status for diagnostics."""
        self.url = url
        self.status_code = status_code
        super().__init__(f"Device removed from backend (HTTP {status_code}) for {url}")


def classify_status(url: str, status_code: int) -> Optional[PermanentFailureError]:
    """Return a typed error for a permanent status, or ``None`` for transient."""
    if is_device_terminal_status(status_code):
        return DeviceRemovedError(url, status_code)
    if is_permanent_status(status_code):
        return PermanentDeliveryError(url, status_code)
    return None
