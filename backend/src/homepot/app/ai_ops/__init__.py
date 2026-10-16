"""Deterministic execution layer for AI action delegation (Phase 3).

The AI only ever *proposes*: this package turns an approved
:class:`~homepot.app.models.AnalyticsModel.AIActionPlan` into real device
commands, verifies the result, rolls back on failure and records the outcome.

Design rules (see ``docs/ai-delegation-plan.md`` section 7):

* **No LLM here.** Every decision is deterministic and driven by the action
  registry (``ai/actions.py``) and the device's stored state.
* **Single audited mutate path.** Commands are queued through the same
  ``DeviceCommand`` queue the operator UI uses, so every device change has one
  audit trail.
* **Never invent a capability.** Only actions declared in the registry may run.
"""

from homepot.app.ai_ops.executor import start_execution
from homepot.app.ai_ops.policy import PolicyResult, evaluate_plan
from homepot.app.ai_ops.rollback import begin_rollback
from homepot.app.ai_ops.verifier import reconcile_plan

__all__ = [
    "PolicyResult",
    "evaluate_plan",
    "start_execution",
    "reconcile_plan",
    "begin_rollback",
]
