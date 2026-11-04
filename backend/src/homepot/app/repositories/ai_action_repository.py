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

from typing import Any, Dict, Iterable, List, Optional, cast
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from homepot.app.ai_ops.approval import requires_step_approval
from homepot.app.ai_ops.retry import DEFAULT_MAX_RETRIES
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
        investigation_session_id: Optional[str] = None,
        investigation_run_id: Optional[str] = None,
        investigation_message_id: Optional[str] = None,
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
            investigation_session_id=investigation_session_id,
            investigation_run_id=investigation_run_id,
            investigation_message_id=investigation_message_id,
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
                    idempotency_key=str(uuid.uuid4()),
                    approval_required=requires_step_approval(
                        getattr(proposal, "risk_tier", "")
                    ),
                    max_retries=DEFAULT_MAX_RETRIES,
                )
            )

        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def claim_for_execution(self, plan_id: str) -> bool:
        """Atomically move an ``approved`` plan to ``executing``.

        Returns ``True`` only for the caller that won the race. This is the
        single-execution guard: a conditional ``UPDATE`` means two concurrent
        Execute requests cannot both queue the plan's commands.
        """
        result = self.db.execute(
            update(AIActionPlan)
            .where(
                AIActionPlan.plan_id == plan_id,
                AIActionPlan.status == "approved",
            )
            .values(status="executing")
        )
        self.db.commit()
        return cast(int, getattr(result, "rowcount", 0)) == 1

    def get_plan(self, plan_id: str) -> Optional[AIActionPlan]:
        """Return a plan by its business ``plan_id``, or ``None``."""
        return self.db.execute(
            select(AIActionPlan).where(AIActionPlan.plan_id == plan_id)
        ).scalar_one_or_none()

    def get_ready_steps(self, plan_id: str) -> List[AIActionStep]:
        """Return steps that are ready to be dispatched.

        A step is ready when its status is ``pending`` or ``approved`` and all
        its dependencies (via ``depends_on_step_id``) have status ``done``.
        """
        plan = self.get_plan(plan_id)
        if plan is None:
            return []
        ready = []
        step_map = {s.step_id: s for s in plan.steps}
        for step in plan.steps:
            if step.status not in ("pending", "approved"):
                continue
            dep_id = getattr(step, "depends_on_step_id", None)
            if dep_id is not None:
                dep = step_map.get(dep_id)
                if dep is None or dep.status != "done":
                    continue
            ready.append(step)
        return ready

    def claim_step_for_dispatch(self, step_id: str) -> bool:
        """Atomically move a ``pending`` step to ``queued``.

        Returns ``True`` only for the caller that won the race.
        """
        result = self.db.execute(
            update(AIActionStep)
            .where(
                AIActionStep.step_id == step_id,
                AIActionStep.status.in_(["pending", "approved"]),
            )
            .values(status="queued")
        )
        self.db.commit()
        return cast(int, getattr(result, "rowcount", 0)) == 1

    def cancel_plan(self, plan_id: str) -> bool:
        """Cancel an executing/approved/pending plan.

        Returns ``True`` if the plan was cancelled.
        """
        result = self.db.execute(
            update(AIActionPlan)
            .where(
                AIActionPlan.plan_id == plan_id,
                AIActionPlan.status.in_(["executing", "approved", "pending_approval"]),
            )
            .values(status="cancelled")
        )
        self.db.commit()
        return cast(int, getattr(result, "rowcount", 0)) == 1

    def plan_summary(
        self,
        *,
        accessible_device_ids: Optional[Iterable[str]] = None,
        created_by: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Aggregate plan counts by status for cross-session task overview.

        Returns counts per status, total plans, and recent plan list.
        """
        from datetime import datetime, timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)

        stmt = select(AIActionPlan).where(AIActionPlan.created_at >= cutoff)

        if accessible_device_ids is not None:
            device_ids = list(accessible_device_ids)
            if not device_ids:
                return {"total": 0, "by_status": {}, "recent": []}
            scoped = select(AIActionStep.plan_id).where(
                AIActionStep.target_device_id.in_(device_ids)
            )
            stmt = stmt.where(AIActionPlan.plan_id.in_(scoped))

        if created_by is not None:
            stmt = stmt.where(AIActionPlan.created_by == created_by)

        plans = list(self.db.execute(stmt).scalars().all())

        by_status: Dict[str, int] = {}
        for plan in plans:
            status_val = str(plan.status)
            by_status[status_val] = by_status.get(status_val, 0) + 1

        recent = [
            {
                "plan_id": p.plan_id,
                "status": p.status,
                "risk_tier": p.risk_tier,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "created_by": p.created_by,
                "step_count": len(p.steps),
            }
            for p in sorted(plans, key=lambda x: x.created_at, reverse=True)[:10]
        ]

        return {
            "total": len(plans),
            "by_status": by_status,
            "recent": recent,
            "period_days": days,
        }

    def list_plans(
        self,
        *,
        statuses: Optional[Iterable[str]] = None,
        accessible_device_ids: Optional[Iterable[str]] = None,
        session_id: Optional[str] = None,
        run_id: Optional[str] = None,
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

        if session_id is not None:
            stmt = stmt.where(AIActionPlan.investigation_session_id == session_id)
        if run_id is not None:
            stmt = stmt.where(AIActionPlan.investigation_run_id == run_id)

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
        plan.status = decision  # type: ignore[assignment]
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
