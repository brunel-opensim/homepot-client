"""Add provenance column to alerts and anomaly_scans tables.

Revision ID: 20261128_add_provenance_to_alerts_anomaly_scans
Revises: 20261128_add_provenance_to_device_commands
Create Date: 2026-11-28
"""

from alembic import op
import sqlalchemy as sa

revision = "20261128_add_provenance_to_alerts_anomaly_scans"
down_revision = "20261128_add_provenance_to_device_commands"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add provenance columns to alerts and anomaly_scans."""
    op.add_column(
        "alerts",
        sa.Column("provenance", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "anomaly_scans",
        sa.Column("provenance", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    """Rollback the provenance columns."""
    op.drop_column("anomaly_scans", "provenance")
    op.drop_column("alerts", "provenance")
