"""Add agent health fields (uptime, restart count) to devices table.

Revision ID: 20261028_add_agent_health
Revises: 20261016_add_ai_action_tables
Create Date: 2026-10-28
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20261028_add_agent_health"
down_revision = "20261016_add_ai_action_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add agent_uptime_seconds and agent_restart_count columns."""
    op.add_column(
        "devices",
        sa.Column("agent_uptime_seconds", sa.Integer(), nullable=True),
    )
    op.add_column(
        "devices",
        sa.Column(
            "agent_restart_count", sa.Integer(), nullable=True, server_default="0"
        ),
    )


def downgrade() -> None:
    """Remove agent health columns."""
    op.drop_column("devices", "agent_restart_count")
    op.drop_column("devices", "agent_uptime_seconds")
