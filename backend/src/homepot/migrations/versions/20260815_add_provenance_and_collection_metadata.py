"""Add provenance and collection metadata to analytics tables.

Revision ID: 20260815_add_provenance_and_collection_metadata
Revises: 20260807_add_push_token_channel
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260815_add_provenance_and_collection_metadata"
down_revision = "20260807_add_push_token_channel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Snapshot evidence provenance onto telemetry and event rows.

    The provenance column is nullable so existing rows are not silently
    assigned a guessed classification; only rows written after this
    migration carry a provenance value.
    """
    op.add_column(
        "device_metrics",
        sa.Column("provenance", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "device_metrics",
        sa.Column("collection_interval_seconds", sa.Integer(), nullable=True),
    )
    op.add_column(
        "device_state_history",
        sa.Column("provenance", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "job_outcomes",
        sa.Column("provenance", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "error_logs",
        sa.Column("provenance", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    """Rollback the provenance and collection metadata columns."""
    op.drop_column("error_logs", "provenance")
    op.drop_column("job_outcomes", "provenance")
    op.drop_column("device_state_history", "provenance")
    op.drop_column("device_metrics", "collection_interval_seconds")
    op.drop_column("device_metrics", "provenance")
