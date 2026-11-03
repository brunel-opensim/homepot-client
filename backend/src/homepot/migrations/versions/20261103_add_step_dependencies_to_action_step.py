"""Add dependency edges and per-step tracking to ai_action_step (Phase A).

Adds:
- depends_on_step_id: self-referential FK for sequential step execution
- result, error: per-step result/error tracking
- started_at, completed_at: per-step timestamps for checkpointing
- approval_required: per-step approval gate flag
- idempotency_key: prevents duplicate dispatch on retry

All columns are nullable (or have defaults) so existing rows remain valid.

Revision ID: 20261103_add_step_dependencies_to_action_step
Revises: 20261102_add_investigation_links_to_action_plan
Create Date: 2026-11-03
"""

from alembic import op
import sqlalchemy as sa

revision = "20261103_add_step_dependencies_to_action_step"
down_revision = "20261102_add_investigation_links_to_action_plan"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def _has_index(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return index_name in {i["name"] for i in inspector.get_indexes(table)}


def upgrade() -> None:
    """Add dependency and tracking columns to ai_action_step."""
    columns = [
        ("depends_on_step_id", sa.String(length=36), True),
        ("result", sa.JSON(), True),
        ("error", sa.Text(), True),
        ("started_at", sa.DateTime(), True),
        ("completed_at", sa.DateTime(), True),
        ("approval_required", sa.Boolean(), False),
        ("idempotency_key", sa.String(length=36), True),
    ]
    for col_name, col_type, nullable in columns:
        if not _has_column("ai_action_step", col_name):
            kwargs = {"nullable": nullable}
            if col_name == "approval_required":
                kwargs["server_default"] = sa.text("false")
            op.add_column(
                "ai_action_step",
                sa.Column(col_name, col_type, **kwargs),
            )

    # Self-referential FK for depends_on_step_id
    inspector = sa.inspect(op.get_bind())
    if "ai_action_step" in inspector.get_table_names():
        fks = {fk.get("name") for fk in inspector.get_foreign_keys("ai_action_step")}
        if "fk_ai_action_step_depends_on" not in fks:
            op.create_foreign_key(
                "fk_ai_action_step_depends_on",
                "ai_action_step",
                "ai_action_step",
                ["depends_on_step_id"],
                ["step_id"],
                ondelete="SET NULL",
            )

    # Indexes
    if "ai_action_step" in inspector.get_table_names():
        existing = {i["name"] for i in inspector.get_indexes("ai_action_step")}
        for idx, col in (
            ("idx_ai_action_step_depends_on", "depends_on_step_id"),
            ("idx_ai_action_step_idempotency", "idempotency_key"),
        ):
            if idx not in existing:
                op.create_index(idx, "ai_action_step", [col])


def downgrade() -> None:
    """Remove dependency and tracking columns from ai_action_step."""
    # Drop FK first
    inspector = sa.inspect(op.get_bind())
    if "ai_action_step" in inspector.get_table_names():
        fks = {fk.get("name") for fk in inspector.get_foreign_keys("ai_action_step")}
        if "fk_ai_action_step_depends_on" in fks:
            op.drop_constraint(
                "fk_ai_action_step_depends_on", "ai_action_step", type_="foreignkey"
            )

    for col in (
        "depends_on_step_id",
        "result",
        "error",
        "started_at",
        "completed_at",
        "approval_required",
        "idempotency_key",
    ):
        if _has_column("ai_action_step", col):
            op.drop_column("ai_action_step", col)
