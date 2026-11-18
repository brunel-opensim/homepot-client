"""Intent router for AI queries (see docs/ai-query-routing.md).

Classifies an incoming query into a ``knowledge``, ``fleet_summary`` or
``diagnostic`` path so informational / how-to questions can be answered from
documentation without paying the device-data validation pipeline (fleet scans,
gates A-E, insights).

``fleet_summary`` is an opt-in classification for aggregate inventory questions
("how many devices are online?", "list sites"). It is deliberately flag-gated:
phase 1 classifies only, while the endpoint still follows the existing
diagnostic pipeline.

The router is deliberately **deterministic and LLM-free** (keeps the CPU-only
inference host fast) and **conservative**: anything ambiguous falls back to
``diagnostic`` so today's safe, gate-backed behaviour is the default.

Resolution order (first match wins):

1. explicit override (``requested`` = ``knowledge`` / ``fleet_summary`` /
   ``diagnostic``);
2. ``action`` signal (imperative capability verb) -> diagnostic/agentic path;
3. a concrete ``device_id`` -> diagnostic (the query is about that device);
4. aggregate/inventory signal -> fleet_summary (when the opt-in flag is on and
   no telemetry signal is present);
5. operational vocabulary (status/alerts/anomaly/...) -> diagnostic;
6. how-to / definition signal -> knowledge;
7. otherwise -> diagnostic.

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
MODE_FLEET_SUMMARY = "fleet_summary"
MODE_DIAGNOSTIC = "diagnostic"

VALID_MODES = frozenset(
    {MODE_AUTO, MODE_KNOWLEDGE, MODE_FLEET_SUMMARY, MODE_DIAGNOSTIC}
)

# Values that disable heuristic routing (every query then takes the diagnostic
# path, preserving pre-routing behaviour). The same vocabulary is reused for
# the fleet-summary opt-in flag.
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

# Aggregate / inventory vocabulary that can be answered from the devices table
# without telemetry validation. Enabled by default via
# AI_FLEET_SUMMARY_ROUTING; set that flag to an off-value to restore the
# original binary knowledge/diagnostic split.
FLEET_SUMMARY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bhow many\b",
        r"\bcount of\b",
        r"\bnumber of\b",
        r"\btotal\b",
        r"\blist (all )?(devices|sites)\b",
        r"\bwhich devices\b",
        r"\bonline devices\b",
        r"\boffline devices\b",
        r"\bactive devices\b",
        r"\bhealthy devices\b",
        r"\bdevice inventory\b",
        r"\bfleet (status|overview|inventory|summary)\b",
        r"\bstatus of (the )?fleet\b",
    )
)

# Telemetry-dependent vocabulary. A count/list question containing one of these
# is not an inventory question: its answer needs the full Gate B telemetry
# checks, so it stays on the diagnostic path even when fleet summaries are on.
FLEET_SUMMARY_TELEMETRY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bcpu\b",
        r"\bmemory\b",
        r"\bdisk\b",
        r"\blatenc",
        r"\bmetric",
        r"\btelemetry\b",
        r"\bheartbeat",
        r"\bstale\b",
        r"\buptime\b",
        r"\bperformance\b",
        r"\balerts?\b",
        r"\banomal",
        r"\berrors?\b",
        r"\bdenied\b",
        r"\bfailed\b",
        r"\bhealth\b",
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
    resolved: str  # MODE_KNOWLEDGE | MODE_FLEET_SUMMARY | MODE_DIAGNOSTIC
    reason: str


def query_has_action_intent(query: str) -> bool:
    """Return True when ``query`` contains an imperative action signal.

    This is the same conservative signal the router uses to keep action requests
    on the diagnostic path. The API calls it separately because a client may
    pin ``mode="diagnostic"`` explicitly (as the soak harness does); in that
    case routing itself reports "explicit override" and would otherwise hide
    the fact that the query still asks the AI to do something.
    """
    text = query or ""
    return any(pattern.search(text) for pattern in ACTION_PATTERNS)


def routing_enabled(raw: Optional[str] = None) -> bool:
    """Return whether heuristic routing is enabled.

    Reads ``AI_QUERY_ROUTING`` (default ``heuristics``); any of the off-values
    disables routing so every query takes the diagnostic path.
    """
    value = raw if raw is not None else os.environ.get("AI_QUERY_ROUTING", "heuristics")
    return (value or "").strip().lower() not in _ROUTING_OFF_VALUES


def fleet_summary_routing_enabled(raw: Optional[str] = None) -> bool:
    """Return whether `fleet_summary` classification is enabled.

    Reads ``AI_FLEET_SUMMARY_ROUTING`` (default ``on``). The same off-values as
    ``AI_QUERY_ROUTING`` disable it; any other value enables the classification.
    The main ``AI_QUERY_ROUTING`` flag still takes precedence: when heuristic
    routing is disabled, every query remains diagnostic.
    """
    default = "on"
    value = (
        raw if raw is not None else os.environ.get("AI_FLEET_SUMMARY_ROUTING", default)
    )
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
    fleet_summary_enabled: Optional[bool] = None,
) -> RoutingDecision:
    """Resolve the query path (``knowledge``, ``fleet_summary`` or ``diagnostic``).

    Args:
        query: The user's raw question.
        requested: Explicit override (``auto`` / ``knowledge`` /
            ``fleet_summary`` / ``diagnostic``). Unknown values fall back to
            ``auto``.
        device_id: Optional device scope; a concrete device means the user is
            asking about that device, so it routes to ``diagnostic``.
        history: Optional conversation history. Reserved for follow-up
            continuity (not yet used in v1 -- ambiguous follow-ups fall back to
            ``diagnostic``).
        enabled: Override for the ``AI_QUERY_ROUTING`` flag (mainly for tests).
        fleet_summary_enabled: Override for ``AI_FLEET_SUMMARY_ROUTING``
            (mainly for tests).

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
    if requested_norm == MODE_FLEET_SUMMARY:
        return RoutingDecision(
            requested_norm, MODE_FLEET_SUMMARY, "explicit override: fleet_summary"
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

    # 4. Aggregate inventory query (opt-in). Telemetry words win first: a
    # count that depends on metrics is still a full diagnostic question.
    fleet_enabled = (
        fleet_summary_enabled
        if fleet_summary_enabled is not None
        else fleet_summary_routing_enabled()
    )
    if fleet_enabled and not _first_match(FLEET_SUMMARY_TELEMETRY_PATTERNS, text):
        match = _first_match(FLEET_SUMMARY_PATTERNS, text)
        if match:
            return RoutingDecision(
                requested_norm,
                MODE_FLEET_SUMMARY,
                f"fleet summary signal: '{match.group(0).lower()}'",
            )

    # 5. Operational vocabulary.
    for pattern in OPERATIONAL_PATTERNS:
        match = pattern.search(query)
        if match:
            return RoutingDecision(
                requested_norm,
                MODE_DIAGNOSTIC,
                f"operational signal: '{match.group(0).lower()}'",
            )

    # 6. How-to / definition.
    for pattern in KNOWLEDGE_PATTERNS:
        match = pattern.search(query)
        if match:
            return RoutingDecision(
                requested_norm,
                MODE_KNOWLEDGE,
                f"how-to signal: '{match.group(0).lower()}'",
            )

    # 7. Conservative default.
    return RoutingDecision(requested_norm, MODE_DIAGNOSTIC, "default")
