"""Add retry metadata to ai_action_step (Phase C, Item 13).

Adds retry_count, max_retries, next_retry_at, last_error columns
for per-step retry policy with backoff.

Revision ID: 20261103_add_retry_to_action_step
Revises: 20261103_add_idempotency_to_device_command
Create Date: 2026-11-03
"""

from typing import Any

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
    columns = [
        ("retry_count", sa.Integer(), False),
        ("max_retries", sa.Integer(), False),
        ("next_retry_at", sa.DateTime(), True),
        ("last_error", sa.Text(), True),
    ]
    for col_name, col_type, nullable in columns:
        if not _has_column("ai_action_step", col_name):
            kwargs: dict[str, Any] = {"nullable": nullable}
            if not nullable:
                if col_name == "retry_count":
                    kwargs["server_default"] = "0"
                elif col_name == "max_retries":
                    kwargs["server_default"] = "0"
            op.add_column(
                "ai_action_step",
                sa.Column(col_name, col_type, **kwargs),
            )


def downgrade() -> None:
    for col in ("retry_count", "max_retries", "next_retry_at", "last_error"):
        if _has_column("ai_action_step", col):
            op.drop_column("ai_action_step", col)
