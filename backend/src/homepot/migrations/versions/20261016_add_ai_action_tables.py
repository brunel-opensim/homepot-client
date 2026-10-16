"""Add the AI action-delegation tables.

Introduces the durable substrate for approval-gated device delegation (see
``docs/ai-delegation-plan.md``):

* ``ai_action_plan``  - an AI-proposed action (or batch), with a snapshot of
  the trust envelope, risk tier, state, and rationale.
* ``ai_action_step``  - the ordered operations a plan would perform.
* ``ai_approval``     - a technician's approve/reject decision.
* ``ai_outcome``      - the verified real-world result (one per plan).

No behaviour is wired to these tables yet; this migration only creates the
schema so later phases have a stable anchor. Creation is guarded because the
application also builds its schema with ``Base.metadata.create_all`` at
startup, which may have created these tables already on a fresh database.

Revision ID: 20261016_add_ai_action_tables
Revises: 20260929_add_command_issued_by
Create Date: 2026-10-16
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20261016_add_ai_action_tables"
down_revision = "20260929_add_command_issued_by"
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    """Return whether ``table`` already exists in the target database."""
    return table in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, index: str) -> bool:
    """Return whether ``index`` already exists on ``table``."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return index in {i["name"] for i in inspector.get_indexes(table)}


def _create_index(table: str, index: str, columns: list[str]) -> None:
    """Create ``index`` on ``table`` unless it is already present."""
    if not _has_index(table, index):
        op.create_index(index, table, columns)


def upgrade() -> None:
    """Create the AI action-delegation tables when they are missing."""
    if not _has_table("ai_action_plan"):
        op.create_table(
            "ai_action_plan",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("plan_id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("source_query_id", sa.String(length=36), nullable=True),
            sa.Column("trust_mode", sa.String(length=50), nullable=True),
            sa.Column("trust_score", sa.Float(), nullable=True),
            sa.Column("passed_gates", sa.JSON(), nullable=True),
            sa.Column("failed_gate", sa.String(length=50), nullable=True),
            sa.Column("risk_tier", sa.String(length=10), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("reversible", sa.Boolean(), nullable=False),
            sa.Column("rationale", sa.Text(), nullable=True),
            sa.Column("evidence", sa.JSON(), nullable=True),
            sa.Column("created_by", sa.String(length=255), nullable=True),
            sa.Column("provenance", sa.String(length=20), nullable=True),
            sa.UniqueConstraint("plan_id", name="uq_ai_action_plan_plan_id"),
        )
        _create_index("ai_action_plan", "idx_ai_action_plan_status", ["status"])
        _create_index("ai_action_plan", "idx_ai_action_plan_risk_tier", ["risk_tier"])
        _create_index(
            "ai_action_plan", "idx_ai_action_plan_source_query", ["source_query_id"]
        )

    if not _has_table("ai_action_step"):
        op.create_table(
            "ai_action_step",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("step_id", sa.String(length=36), nullable=False),
            sa.Column(
                "plan_id",
                sa.String(length=36),
                sa.ForeignKey("ai_action_plan.plan_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(length=50), nullable=False),
            sa.Column("target_device_id", sa.String(length=50), nullable=True),
            sa.Column("params", sa.JSON(), nullable=True),
            sa.Column("preconditions", sa.JSON(), nullable=True),
            sa.Column("postconditions", sa.JSON(), nullable=True),
            sa.Column("rollback_params", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("command_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("step_id", name="uq_ai_action_step_step_id"),
        )
        _create_index("ai_action_step", "idx_ai_action_step_plan_id", ["plan_id"])
        _create_index(
            "ai_action_step", "idx_ai_action_step_target_device", ["target_device_id"]
        )
        _create_index("ai_action_step", "idx_ai_action_step_status", ["status"])

    if not _has_table("ai_approval"):
        op.create_table(
            "ai_approval",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("approval_id", sa.String(length=36), nullable=False),
            sa.Column(
                "plan_id",
                sa.String(length=36),
                sa.ForeignKey("ai_action_plan.plan_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("actor", sa.String(length=255), nullable=False),
            sa.Column("decision", sa.String(length=20), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("decided_at", sa.DateTime(), nullable=False),
            sa.Column("device_scope", sa.JSON(), nullable=True),
            sa.UniqueConstraint("approval_id", name="uq_ai_approval_approval_id"),
        )
        _create_index("ai_approval", "idx_ai_approval_plan_id", ["plan_id"])

    if not _has_table("ai_outcome"):
        op.create_table(
            "ai_outcome",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("outcome_id", sa.String(length=36), nullable=False),
            sa.Column(
                "plan_id",
                sa.String(length=36),
                sa.ForeignKey("ai_action_plan.plan_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("verified", sa.Boolean(), nullable=False),
            sa.Column("metrics_before", sa.JSON(), nullable=True),
            sa.Column("metrics_after", sa.JSON(), nullable=True),
            sa.Column("rolled_back", sa.Boolean(), nullable=False),
            sa.Column("rollback_success", sa.Boolean(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("recorded_at", sa.DateTime(), nullable=False),
            sa.Column("provenance", sa.String(length=20), nullable=True),
            sa.UniqueConstraint("outcome_id", name="uq_ai_outcome_outcome_id"),
            sa.UniqueConstraint("plan_id", name="uq_ai_outcome_plan_id"),
        )


def downgrade() -> None:
    """Drop the AI action-delegation tables (children first)."""
    for table in ("ai_outcome", "ai_approval", "ai_action_step", "ai_action_plan"):
        if _has_table(table):
            op.drop_table(table)
