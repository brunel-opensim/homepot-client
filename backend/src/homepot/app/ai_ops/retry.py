"""Retry policy for AI action steps (Phase C, roadmap item 13).

A step whose *transport* fails (the device never acknowledged the command, or
the command expired/was cancelled) is retried with exponential backoff. Per-key
failures inside a completed command are **not** retried: they are deterministic
and handled by the rollback path instead.

The policy is intentionally small and side-effect free so the executor, the
verifier, and the plan repository can share it without import cycles.
"""

import os

#: Default retry budget for a newly created step.
DEFAULT_MAX_RETRIES = int(os.getenv("HOMEPOT_AI_STEP_MAX_RETRIES", "2"))

#: Base delay (seconds) before the first retry; doubled for each subsequent one.
BACKOFF_BASE_SECONDS = int(os.getenv("HOMEPOT_AI_STEP_RETRY_BASE_SECONDS", "30"))

#: Upper bound so a long-lived plan cannot stall for hours.
BACKOFF_MAX_SECONDS = int(os.getenv("HOMEPOT_AI_STEP_RETRY_MAX_SECONDS", "300"))


def backoff_seconds(retry_count: int) -> int:
    """Return the backoff delay before retry number ``retry_count``.

    ``retry_count`` is zero-based: 0 yields ``BACKOFF_BASE_SECONDS``, 1 yields
    2x base, and so on, capped at :data:`BACKOFF_MAX_SECONDS`.
    """
    exponent = max(retry_count, 0)
    delay: int = BACKOFF_BASE_SECONDS * (2**exponent)
    return int(min(delay, BACKOFF_MAX_SECONDS))
