"""Add idempotency_key to device_commands (Phase C, Item 12).

Prevents duplicate command execution on retry by deduplicating on
(device_id, idempotency_key).

Revision ID: 20261103_add_idempotency_to_device_command
Revises: 20261103_add_step_dependencies_to_action_step
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


def _has_index(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return index_name in {i["name"] for i in inspector.get_indexes(table)}


revision = "20261103_add_idempotency_to_device_command"
down_revision = "20261103_add_step_dependencies_to_action_step"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not _has_column("device_commands", "idempotency_key"):
        op.add_column(
            "device_commands",
            sa.Column("idempotency_key", sa.String(length=36), nullable=True),
        )
    if not _has_index("device_commands", "idx_device_command_idempotency"):
        op.create_index(
            "idx_device_command_idempotency",
            "device_commands",
            ["device_id", "idempotency_key"],
            unique=False,
        )


def downgrade() -> None:
    if _has_index("device_commands", "idx_device_command_idempotency"):
        op.drop_index("idx_device_command_idempotency", table_name="device_commands")
    if _has_column("device_commands", "idempotency_key"):
        op.drop_column("device_commands", "idempotency_key")
