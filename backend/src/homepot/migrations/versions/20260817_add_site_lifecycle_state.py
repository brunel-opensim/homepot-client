"""Add lifecycle_state column to sites table.

Revision ID: 20260817_add_site_lifecycle_state
Revises: 20260816_add_command_and_config_outcome_tracking
Create Date: 2026-08-17
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260817_add_site_lifecycle_state"
down_revision = "20260816_add_command_and_config_outcome_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add lifecycle_state to sites with data backfill."""
    op.add_column(
        "sites",
        sa.Column("lifecycle_state", sa.String(length=20), nullable=True),
    )

    op.execute(
        """
        UPDATE sites
        SET lifecycle_state = CASE
            WHEN is_active = false THEN 'archived'
            ELSE 'active'
        END
        """
    )

    op.alter_column("sites", "lifecycle_state", nullable=False)


def downgrade() -> None:
    """Rollback the sites lifecycle_state column."""
    op.drop_column("sites", "lifecycle_state")
