"""Repository for AI action-delegation plans (the Phase 1 proposal store).

This is the write path that turns the agent's in-memory
:class:`ai.actions.ActionProposal` objects into durable ``ai_action_plan`` /
``ai_action_step`` rows. It deliberately contains **no execution logic**: a plan
is recorded with status ``proposed`` and awaits a technician (Phase 2).

The repository is backend-only and takes plain proposal-like objects (anything
with ``action``/``target_device_id``/``params``/``rationale``/``risk_tier``/
``reversible``), so it does not import the ``ai`` package and can be used from
any backend context.
"""

from typing import Any, List, Optional

from sqlalchemy.orm import Session

from homepot.app.models.AnalyticsModel import AIActionPlan, AIActionStep


class AIActionRepository:
    """Persist AI-proposed action plans and their ordered steps."""

    def __init__(self, db: Session) -> None:
        """Initialize the repository with an active SQLAlchemy session."""
        self.db = db

    def create_plan(
        self,
        proposals: List[Any],
        *,
        risk_tier: Optional[str] = None,
        reversible: bool = False,
        source_query_id: Optional[str] = None,
        trust: Optional[Any] = None,
        created_by: Optional[str] = None,
        provenance: str = "ai_proposed",
        status: str = "proposed",
    ) -> AIActionPlan:
        """Create and persist one plan from an ordered list of proposals.

        A single AI turn yields one plan; each proposal becomes a step, in
        order. The trust-envelope snapshot is recorded inline so the durable row
        carries the exact grounding the proposal was based on.
        """
        plan = AIActionPlan(
            source_query_id=source_query_id,
            trust_mode=getattr(getattr(trust, "trust_mode", None), "label", None),
            trust_score=(float(trust.trust_score) if trust is not None else None),
            passed_gates=(list(trust.passed_gate_ids) if trust is not None else None),
            failed_gate=(trust.failed_gate_id if trust is not None else None),
            risk_tier=risk_tier,
            status=status,
            reversible=reversible,
            rationale=self._join_rationales(proposals),
            evidence={"proposals": [self._proposal_dict(p) for p in proposals]},
            created_by=created_by,
            provenance=provenance,
        )

        for seq, proposal in enumerate(proposals):
            plan.steps.append(
                AIActionStep(
                    seq=seq,
                    action=proposal.action,
                    target_device_id=proposal.target_device_id,
                    params=proposal.params or {},
                    status="pending",
                )
            )

        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    @staticmethod
    def _join_rationales(proposals: List[Any]) -> Optional[str]:
        """Combine per-proposal rationales into the plan-level rationale."""
        parts = [p.rationale for p in proposals if getattr(p, "rationale", None)]
        return "\n".join(parts) if parts else None

    @staticmethod
    def _proposal_dict(proposal: Any) -> dict:
        """Serializable snapshot of a proposal for the plan's evidence field."""
        return {
            "action": proposal.action,
            "target_device_id": proposal.target_device_id,
            "params": proposal.params or {},
            "rationale": proposal.rationale,
            "risk_tier": getattr(proposal, "risk_tier", None),
            "reversible": getattr(proposal, "reversible", None),
        }
