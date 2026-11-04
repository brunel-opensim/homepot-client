"""Per-step approval policy (Phase A, roadmap item 4).

Plan-level approval is always required. On top of that, steps whose risk tier
is listed here get their own gate: after the plan is approved the step pauses in
``awaiting_approval`` until an operator releases it individually. This lets a
technician approve step 1, review the result, then approve step 2 instead of
rubber-stamping a whole plan at once.

Disruptive (T3) actions are gated by default. The set is configurable because a
deployment may want no step gates (``""``) or to include reversible steps too.
"""

import os

#: Risk tiers that require an individual step approval.
STEP_APPROVAL_TIERS = {
    tier.strip().upper()
    for tier in os.getenv("HOMEPOT_AI_STEP_APPROVAL_TIERS", "T3").split(",")
    if tier.strip()
}


def requires_step_approval(risk_tier: str) -> bool:
    """Return True when a step with ``risk_tier`` needs its own approval."""
    return (risk_tier or "").upper() in STEP_APPROVAL_TIERS
