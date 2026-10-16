"""Repository for AI action-delegation plans (proposal store + review).

This is the write/read path for ``ai_action_plan`` / ``ai_action_step`` /
``ai_approval``. It deliberately contains **no execution logic**: a plan is
recorded with status ``pending_approval`` and a technician either approves or
rejects it (Phase 2). The executor (Phase 3) is a separate, later component.

The repository is backend-only and takes plain proposal-like objects (anything
with ``action``/``target_device_id``/``params``/``rationale``/``risk_tier``/
``reversible``), so it does not import the ``ai`` package and can be used from
any backend context.
"""

from typing import Any, Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from homepot.app.models.AnalyticsModel import (
    AIActionApproval,
    AIActionPlan,
    AIActionStep,
)
from homepot.models import Device


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

    def get_plan(self, plan_id: str) -> Optional[AIActionPlan]:
        """Return a plan by its business ``plan_id``, or ``None``."""
        return self.db.execute(
            select(AIActionPlan).where(AIActionPlan.plan_id == plan_id)
        ).scalar_one_or_none()

    def list_plans(
        self,
        *,
        statuses: Optional[Iterable[str]] = None,
        accessible_device_ids: Optional[Iterable[str]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AIActionPlan]:
        """List plans newest-first, optionally filtered by status and scope.

        When ``accessible_device_ids`` is provided (non-admin callers), only
        plans that have at least one step targeting an accessible device are
        returned. v1 plans are single-device, so this is exact; multi-device
        blast-radius scoping arrives with the policy engine in Phase 3.
        ``None`` means "no scope filter" (admin).
        """
        stmt = select(AIActionPlan).order_by(AIActionPlan.created_at.desc())
        if statuses is not None:
            status_list = list(statuses)
            if not status_list:
                return []
            stmt = stmt.where(AIActionPlan.status.in_(status_list))

        if accessible_device_ids is not None:
            device_ids = list(accessible_device_ids)
            if not device_ids:
                return []
            scoped = select(AIActionStep.plan_id).where(
                AIActionStep.target_device_id.in_(device_ids)
            )
            stmt = stmt.where(AIActionPlan.plan_id.in_(scoped))

        stmt = stmt.limit(limit).offset(offset)
        return list(self.db.execute(stmt).scalars().all())

    def accessible_device_ids(
        self, accessible_site_pks: Optional[Iterable[int]]
    ) -> Optional[List[str]]:
        """Return business device_ids in the given site PKs.

        ``None`` propagates ``None`` (admin: unscoped). An empty iterable yields
        an empty list (the caller can access no device).
        """
        if accessible_site_pks is None:
            return None
        site_pks = list(accessible_site_pks)
        if not site_pks:
            return []
        stmt = select(Device.device_id).where(Device.site_id.in_(site_pks))
        return list(self.db.execute(stmt).scalars().all())

    def record_decision(
        self,
        plan: AIActionPlan,
        *,
        actor: str,
        decision: str,
        reason: Optional[str] = None,
        device_scope: Optional[Any] = None,
    ) -> AIActionApproval:
        """Record a technician's approve/reject decision and transition the plan.

        The caller must validate that the plan is still ``pending_approval`` and
        that the actor is scoped to every target device; this method only writes
        the approval row and moves the plan's status.
        """
        if decision not in ("approved", "rejected"):
            raise ValueError(f"Invalid decision: {decision!r}")

        approval = AIActionApproval(
            plan_id=plan.plan_id,
            actor=actor,
            decision=decision,
            reason=reason,
            device_scope=device_scope,
        )
        plan.status = decision
        self.db.add(approval)
        self.db.commit()
        self.db.refresh(approval)
        return approval

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
