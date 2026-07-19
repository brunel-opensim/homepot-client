"""Add LifecycleEpoch model and lifecycle_epoch_id to Device.

Revision ID: 20260719_add_lifecycle_epochs
Revises: 20260719_add_enrolment_intents
Create Date: 2026-07-19
"""

from alembic import op
import sqlalchemy as sa

revision = "20260719_add_lifecycle_epochs"
down_revision = "20260719_add_enrolment_intents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the lifecycle_epochs table and add lifecycle_epoch_id to devices."""
    op.create_table(
        "lifecycle_epochs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "epoch_id", sa.String(length=36), unique=True, index=True, nullable=False
        ),
        sa.Column(
            "device_id",
            sa.Integer(),
            sa.ForeignKey("devices.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column(
            "tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claim_token_hash", sa.String(length=255), nullable=True),
        sa.Column("enrolment_method", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "devices",
        sa.Column(
            "lifecycle_epoch_id",
            sa.Integer(),
            sa.ForeignKey("lifecycle_epochs.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Drop the lifecycle_epochs table and lifecycle_epoch_id from devices."""
    op.drop_column("devices", "lifecycle_epoch_id")
    op.drop_table("lifecycle_epochs")
