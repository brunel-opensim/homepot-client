"""Add archived_at column to ai_action_plan (retention policy).

Adds a soft-archive timestamp so terminal plans older than the configured
retention window can be hidden from the default list/summary while remaining
available for reliability metrics and audit.

Revision ID: 20261106_add_archived_at_to_action_plan
Revises: 20261103_add_retry_to_action_step
Create Date: 2026-11-06
"""

from alembic import op
import sqlalchemy as sa


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


revision = "20261106_add_archived_at_to_action_plan"
down_revision = "20261103_add_retry_to_action_step"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add archived_at column to ai_action_plan."""
    if not _has_column("ai_action_plan", "archived_at"):
        op.add_column(
            "ai_action_plan",
            sa.Column("archived_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "idx_ai_action_plan_archived_at",
            "ai_action_plan",
            ["archived_at"],
        )


def downgrade() -> None:
    """Remove archived_at column from ai_action_plan."""
    if _has_column("ai_action_plan", "archived_at"):
        op.drop_index("idx_ai_action_plan_archived_at", table_name="ai_action_plan")
        op.drop_column("ai_action_plan", "archived_at")
