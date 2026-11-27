"""Add provenance column to device_commands for immutable evidence classification.

Revision ID: 20261128_add_provenance_to_device_commands
Revises: 20261114_add_monitor_dismiss
Create Date: 2026-11-28
"""

from alembic import op
import sqlalchemy as sa

revision = "20261128_add_provenance_to_device_commands"
down_revision = "20261114_add_monitor_dismiss"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add provenance column to device_commands."""
    op.add_column(
        "device_commands",
        sa.Column("provenance", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    """Rollback the provenance column."""
    op.drop_column("device_commands", "provenance")
