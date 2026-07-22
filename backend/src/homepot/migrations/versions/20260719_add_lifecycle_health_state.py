"""Add lifecycle_state and health_state columns to devices table.

Revision ID: 20260719_add_lifecycle_health
Revises: 20260331_add_dna_heartbeat
Create Date: 2026-07-19
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260719_add_lifecycle_health"
down_revision = "20260331_add_dna_heartbeat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add lifecycle_state and health_state to devices with data backfill."""
    op.add_column(
        "devices",
        sa.Column("lifecycle_state", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "devices",
        sa.Column("health_state", sa.String(length=20), nullable=True),
    )

    op.execute("""
        UPDATE devices
        SET lifecycle_state = CASE
            WHEN status = 'unpaired' OR is_active = false THEN 'unpaired'
            WHEN status IN ('online', 'offline', 'maintenance', 'error') THEN 'active'
            WHEN status = 'unknown' AND is_active = true THEN 'pending'
            ELSE 'pending'
        END
        """)

    op.execute("UPDATE devices SET health_state = 'unknown' WHERE health_state IS NULL")

    op.alter_column("devices", "lifecycle_state", nullable=False)


def downgrade() -> None:
    """Rollback lifecycle_state and health_state columns."""
    op.drop_column("devices", "health_state")
    op.drop_column("devices", "lifecycle_state")
