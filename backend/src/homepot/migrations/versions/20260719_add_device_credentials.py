"""Add DeviceCredential model for tracked API-key versions.

Revision ID: 20260719_add_device_credentials
Revises: 20260719_add_lifecycle_epochs
Create Date: 2026-07-19
"""

from alembic import op
import sqlalchemy as sa

revision = "20260719_add_device_credentials"
down_revision = "20260719_add_lifecycle_epochs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the device_credentials table."""
    op.create_table(
        "device_credentials",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "credential_id",
            sa.String(length=36),
            unique=True,
            index=True,
            nullable=False,
        ),
        sa.Column(
            "device_id",
            sa.Integer(),
            sa.ForeignKey("devices.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("key_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
    )


def downgrade() -> None:
    """Drop the device_credentials table."""
    op.drop_table("device_credentials")
