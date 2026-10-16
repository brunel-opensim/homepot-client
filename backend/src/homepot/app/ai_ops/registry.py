"""Registry access for the AI ops executor (Phase 3).

The declared capabilities live in ``ai/actions.py`` (Phase 1) — one source of
truth shared with the proposal layer. This module only re-exposes them to the
backend so the executor can map a plan step to a real command type without
duplicating (and risking drift from) the risk/permission metadata.
"""

import os
import sys

# Add the project root to sys.path so the top-level ``ai`` package imports.
# File: backend/src/homepot/app/ai_ops/registry.py -> root is 5 levels up.
_project_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../../")
)
if _project_root not in sys.path:
    sys.path.append(_project_root)

from ai.actions import (  # noqa: E402
    ACTION_REGISTRY,
    ActionProposal,
    ActionSpec,
    all_reversible,
    get_action_spec,
    max_risk_tier,
)

__all__ = [
    "ACTION_REGISTRY",
    "ActionProposal",
    "ActionSpec",
    "all_reversible",
    "get_action_spec",
    "max_risk_tier",
]
