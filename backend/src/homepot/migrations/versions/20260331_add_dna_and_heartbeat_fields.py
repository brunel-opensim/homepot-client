"""Add device DNA and heartbeat fields to devices table.

Revision ID: 20260331_add_dna_heartbeat
Revises:
Create Date: 2026-03-31
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260331_add_dna_heartbeat"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply schema changes for device DNA and heartbeat tracking."""
    op.add_column(
        "devices", sa.Column("os_details", sa.String(length=255), nullable=True)
    )
    op.add_column("devices", sa.Column("local_ip", sa.String(length=45), nullable=True))
    op.add_column("devices", sa.Column("wan_ip", sa.String(length=45), nullable=True))
    op.add_column(
        "devices",
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Rollback schema changes for device DNA and heartbeat tracking."""
    op.drop_column("devices", "last_heartbeat_at")
    op.drop_column("devices", "wan_ip")
    op.drop_column("devices", "local_ip")
    op.drop_column("devices", "os_details")
