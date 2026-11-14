"""Add monitor_dismissed_until column to devices.

Supports the operator "Remove from Dashboard" override: when an operator
removes an auto-monitored device, this timestamp records a cooldown so the
anomaly scan does not immediately re-pin it. Manually adding a device clears
it.

Revision ID: 20261114_add_monitor_dismiss
Revises: 20261114_add_anomaly_scan
Create Date: 2026-11-14
"""

from alembic import op
import sqlalchemy as sa


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


revision = "20261114_add_monitor_dismiss"
down_revision = "20261114_add_anomaly_scan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the monitor_dismissed_until column to devices."""
    if not _has_column("devices", "monitor_dismissed_until"):
        op.add_column(
            "devices",
            sa.Column(
                "monitor_dismissed_until", sa.DateTime(timezone=True), nullable=True
            ),
        )


def downgrade() -> None:
    """Drop the monitor_dismissed_until column from devices."""
    if _has_column("devices", "monitor_dismissed_until"):
        op.drop_column("devices", "monitor_dismissed_until")
