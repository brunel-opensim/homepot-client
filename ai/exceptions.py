"""Shared AI-layer exceptions.

Kept dependency-free (stdlib only) so both the ``ai`` package (agent, tools)
and the ``homepot`` app layer (the concurrency gate, API endpoints) can import
the same class object without creating an import cycle.
"""


class AIBusyError(Exception):
    """Raised when a request waited too long for an AI generation slot.

    Raised by the concurrency gate when every inference slot is busy and the
    caller's queue budget has elapsed. Callers at the API boundary translate it
    into an HTTP 503 so a burst gets an explicit "busy" instead of hanging.
    """
