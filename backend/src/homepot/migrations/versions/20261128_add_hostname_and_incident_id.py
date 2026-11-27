"""Add hostname column to devices and incident_id column to alerts.

Revision ID: 20261128_add_hostname_and_incident_id
Revises: 20261128_add_provenance_to_alerts_anomaly_scans
Create Date: 2026-11-28
"""

from alembic import op
import sqlalchemy as sa

revision = "20261128_add_hostname_and_incident_id"
down_revision = "20261128_add_provenance_to_alerts_anomaly_scans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add hostname to devices and incident_id to alerts."""
    op.add_column(
        "devices",
        sa.Column("hostname", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("incident_id", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    """Rollback the columns."""
    op.drop_column("alerts", "incident_id")
    op.drop_column("devices", "hostname")
