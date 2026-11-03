"""Add retry metadata to ai_action_step (Phase C, Item 13).

Adds retry_count, max_retries, next_retry_at, last_error columns
for per-step retry policy with backoff.

Revision ID: 20261103_add_retry_to_action_step
Revises: 20261103_add_idempotency_to_device_command
Create Date: 2026-11-03
"""

from alembic import op
import sqlalchemy as sa


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


revision = "20261103_add_retry_to_action_step"
down_revision = "20261103_add_idempotency_to_device_command"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add retry metadata to ai_action_step."""
    if not _has_column("ai_action_step", "retry_count"):
        op.add_column(
            "ai_action_step",
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        )
    if not _has_column("ai_action_step", "max_retries"):
        op.add_column(
            "ai_action_step",
            sa.Column("max_retries", sa.Integer(), nullable=False, server_default="0"),
        )
    if not _has_column("ai_action_step", "next_retry_at"):
        op.add_column(
            "ai_action_step",
            sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        )
    if not _has_column("ai_action_step", "last_error"):
        op.add_column(
            "ai_action_step",
            sa.Column("last_error", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    """Remove retry metadata from ai_action_step."""
    for col in ("retry_count", "max_retries", "next_retry_at", "last_error"):
        if _has_column("ai_action_step", col):
            op.drop_column("ai_action_step", col)
