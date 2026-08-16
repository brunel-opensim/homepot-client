"""Track command delivery timestamps and configuration outcome metadata.

Revision ID: 20260816_add_command_and_config_outcome_tracking
Revises: 20260815_add_provenance_and_collection_metadata
Create Date: 2026-08-16
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260816_add_command_and_config_outcome_tracking"
down_revision = "20260815_add_provenance_and_collection_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add command sent_at and configuration outcome/rollback columns.

    ``device_commands.sent_at`` records when the agent acknowledged a queued
    command, so round-trip latency can be computed as the gap between
    ``sent_at`` and ``executed_at``. The new ``configuration_history`` columns
    close the loop on whether a change succeeded, whether it had to be rolled
    back, and how the device performed before/after/at-rollback, together with
    the provenance of the reporting device.
    """
    op.add_column(
        "device_commands",
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "configuration_history",
        sa.Column("rollback_performance", sa.JSON(), nullable=True),
    )
    op.add_column(
        "configuration_history",
        sa.Column("rollback_success", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "configuration_history",
        sa.Column("rolled_back_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "configuration_history",
        sa.Column("provenance", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    """Rollback the command and configuration outcome tracking columns."""
    op.drop_column("configuration_history", "provenance")
    op.drop_column("configuration_history", "rolled_back_at")
    op.drop_column("configuration_history", "rollback_success")
    op.drop_column("configuration_history", "rollback_performance")
    op.drop_column("device_commands", "sent_at")
