"""Intent router for AI queries (see docs/ai-query-routing.md).

Classifies an incoming query into a ``knowledge`` or ``diagnostic`` path so
informational / how-to questions can be answered from documentation without
paying the device-data validation pipeline (fleet scans, gates A-E, insights).

The router is deliberately **deterministic and LLM-free** (keeps the CPU-only
inference host fast) and **conservative**: anything ambiguous falls back to
``diagnostic`` so today's safe, gate-backed behaviour is the default.

Resolution order (first match wins):

1. explicit override (``requested`` = ``knowledge`` / ``diagnostic``);
2. ``action`` signal (imperative capability verb) -> diagnostic/agentic path;
3. a concrete ``device_id`` -> diagnostic (the query is about that device);
4. operational vocabulary (status/alerts/anomaly/...) -> diagnostic;
5. how-to / definition signal -> knowledge;
6. otherwise -> diagnostic.

The pattern lists below are the single, tunable source of truth for the
heuristics.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Optional, Sequence

MODE_AUTO = "auto"
MODE_KNOWLEDGE = "knowledge"
MODE_DIAGNOSTIC = "diagnostic"

VALID_MODES = frozenset({MODE_AUTO, MODE_KNOWLEDGE, MODE_DIAGNOSTIC})

# Values of AI_QUERY_ROUTING that disable heuristic routing (every query then
# takes the diagnostic path, preserving pre-routing behaviour).
_ROUTING_OFF_VALUES = frozenset({"off", "0", "false", "no", "disabled", "none"})

# ---------------------------------------------------------------------------
# TUNABLE: classification signals.
# ---------------------------------------------------------------------------

# How-to / definition / product questions answerable from documentation.
KNOWLEDGE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bhow (do|can|to|does|should)\b",
        r"\bwhat (is|are|does|do|mean)\b",
        r"\bexplain\b",
        r"\bmeaning of\b",
        r"\bwhere (can|do) i\b",
        r"\bwhich command\b",
        r"\benroll(ment)?\b",
        r"\bpermission\b",
        r"\bdocumentation\b",
        r"\bhow it works\b",
    )
)

# Imperative signals that a query wants an action carried out. These follow the
# operational path so the full gate + approval + execution controls apply.
ACTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\brestart\b",
        r"\breboot\b",
        r"\bapply\b",
        r"\bset .* to\b",
        r"\bchange .* config",
        r"\bpush .* config",
        r"\bshut ?down\b",
    )
)

# Operational vocabulary that always means "diagnostic": a question about live
# or historical state is never answerable from documentation. This keeps broad
# knowledge interrogatives ("what is ...") from capturing status questions such
# as "What is the system status?" or "any anomalies today?".
OPERATIONAL_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bstatus\b",
        r"\bonline\b",
        r"\boffline\b",
        r"\balerts?\b",
        r"\banomal",
        r"\bhealth\b",
        r"\bheartbeat\b",
        r"\buptime\b",
        r"\bperformance\b",
        r"\bstale\b",
        r"\berrors?\b",
        r"\bdenied\b",
        r"\bfailed\b",
        r"\blatenc",
        r"\bcurrent state\b",
        r"\bright now\b",
        r"\btoday\b",
        r"\bfleet\b",
    )
)


@dataclass(frozen=True)
class RoutingDecision:
    """Outcome of routing a query: what was asked for vs. what was resolved."""

    requested: str
    resolved: str  # MODE_KNOWLEDGE | MODE_DIAGNOSTIC
    reason: str


def routing_enabled(raw: Optional[str] = None) -> bool:
    """Return whether heuristic routing is enabled.

    Reads ``AI_QUERY_ROUTING`` (default ``heuristics``); any of the off-values
    disables routing so every query takes the diagnostic path.
    """
    value = raw if raw is not None else os.environ.get("AI_QUERY_ROUTING", "heuristics")
    return (value or "").strip().lower() not in _ROUTING_OFF_VALUES


def _first_match(
    patterns: Sequence[re.Pattern[str]], text: str
) -> Optional[re.Match[str]]:
    """Return the first pattern that matches ``text`` (or None)."""
    for pattern in patterns:
        match = pattern.search(text)
        if match is not None:
            return match
    return None


def resolve_query_mode(
    query: str,
    requested: Optional[str] = None,
    device_id: Optional[str] = None,
    history: Optional[Sequence[object]] = None,
    enabled: Optional[bool] = None,
) -> RoutingDecision:
    """Resolve the query path (``knowledge`` or ``diagnostic``).

    Args:
        query: The user's raw question.
        requested: Explicit override (``auto`` / ``knowledge`` / ``diagnostic``).
            Unknown values fall back to ``auto``.
        device_id: Optional device scope; a concrete device means the user is
            asking about that device, so it routes to ``diagnostic``.
        history: Optional conversation history. Reserved for follow-up
            continuity (not yet used in v1 -- ambiguous follow-ups fall back to
            ``diagnostic``).
        enabled: Override for the ``AI_QUERY_ROUTING`` flag (mainly for tests).

    Returns:
        A :class:`RoutingDecision` with the requested mode, the resolved mode
        and a short human-readable reason for logging.
    """
    requested_norm = (requested or MODE_AUTO).strip().lower()
    if requested_norm not in VALID_MODES:
        requested_norm = MODE_AUTO

    # 1. Explicit override.
    if requested_norm == MODE_KNOWLEDGE:
        return RoutingDecision(
            requested_norm, MODE_KNOWLEDGE, "explicit override: knowledge"
        )
    if requested_norm == MODE_DIAGNOSTIC:
        return RoutingDecision(
            requested_norm, MODE_DIAGNOSTIC, "explicit override: diagnostic"
        )

    if not (enabled if enabled is not None else routing_enabled()):
        return RoutingDecision(requested_norm, MODE_DIAGNOSTIC, "routing disabled")

    text = query or ""

    # 2. Action intent -> operational path.
    for pattern in ACTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return RoutingDecision(
                requested_norm,
                MODE_DIAGNOSTIC,
                f"action signal: '{match.group(0).lower()}'",
            )

    # 3. Device-scoped query.
    if device_id:
        return RoutingDecision(requested_norm, MODE_DIAGNOSTIC, "device_id present")

    # 4. Operational vocabulary.
    for pattern in OPERATIONAL_PATTERNS:
        match = pattern.search(query)
        if match:
            return RoutingDecision(
                requested_norm,
                MODE_DIAGNOSTIC,
                f"operational signal: '{match.group(0).lower()}'",
            )

    # 5. How-to / definition.
    for pattern in KNOWLEDGE_PATTERNS:
        match = pattern.search(query)
        if match:
            return RoutingDecision(
                requested_norm,
                MODE_KNOWLEDGE,
                f"how-to signal: '{match.group(0).lower()}'",
            )

    # 6. Conservative default.
    return RoutingDecision(requested_norm, MODE_DIAGNOSTIC, "default")
