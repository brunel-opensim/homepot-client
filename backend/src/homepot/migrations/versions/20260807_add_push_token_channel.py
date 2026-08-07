"""Add push_token and push_channel columns to devices table.

Revision ID: 20260807_add_push_token_channel
Revises: 20260801_add_site_device_columns
Create Date: 2026-08-07
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260807_add_push_token_channel"
down_revision = "20260801_add_site_device_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add push transport registration columns to the devices table."""
    op.add_column(
        "devices",
        sa.Column("push_token", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "devices",
        sa.Column("push_channel", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    """Rollback push transport registration columns."""
    op.drop_column("devices", "push_channel")
    op.drop_column("devices", "push_token")
