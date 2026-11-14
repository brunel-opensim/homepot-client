"""Add anomaly_scans table for multi-level anomaly detection.

Stores one row per device per scheduled scan so persistence (repeated breaches
over a window) and de-escalation (consecutive clean scans) can be computed. The
Dashboard reads the latest row per device instead of recomputing on each poll.

Revision ID: 20261114_add_anomaly_scan
Revises: 20261106_add_archived_at_to_action_plan
Create Date: 2026-11-14
"""

from alembic import op
import sqlalchemy as sa


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table in inspector.get_table_names()


revision = "20261114_add_anomaly_scan"
down_revision = "20261106_add_archived_at_to_action_plan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the anomaly_scans table."""
    if _has_table("anomaly_scans"):
        return
    op.create_table(
        "anomaly_scans",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False, index=True),
        sa.Column("device_id", sa.String(50), nullable=False, index=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("reasons", sa.JSON(), nullable=True),
    )
    op.create_index(
        "idx_anomaly_scan_device_timestamp",
        "anomaly_scans",
        ["device_id", "timestamp"],
    )


def downgrade() -> None:
    """Drop the anomaly_scans table."""
    if not _has_table("anomaly_scans"):
        return
    op.drop_index("idx_anomaly_scan_device_timestamp", table_name="anomaly_scans")
    op.drop_table("anomaly_scans")
