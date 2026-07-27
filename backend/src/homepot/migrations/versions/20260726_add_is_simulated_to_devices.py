"""Add is_simulated column to devices table.

Revision ID: 20260726_add_is_simulated
Revises: 20260720_add_device_assignments_events
Create Date: 2026-07-26
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260726_add_is_simulated"
down_revision = "20260720_add_device_assignments_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add is_simulated column to devices table."""
    op.add_column(
        "devices",
        sa.Column("is_simulated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    """Rollback is_simulated column."""
    op.drop_column("devices", "is_simulated")
