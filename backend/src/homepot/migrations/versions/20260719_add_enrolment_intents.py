"""Add EnrolmentIntent model for durable enrolment-intent records.

Revision ID: 20260719_add_enrolment_intents
Revises: 20260719_add_tenant_membership
Create Date: 2026-07-19
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260719_add_enrolment_intents"
down_revision = "20260719_add_tenant_membership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "enrolment_intents",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("intent_id", sa.String(length=36), unique=True, index=True, nullable=False),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column(
            "enrolment_method", sa.String(length=50), nullable=False
        ),
        sa.Column(
            "expected_device_identity", sa.String(length=100), nullable=True
        ),
        sa.Column("claim_token_hash", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "creator_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "idempotency_key",
            sa.String(length=100),
            unique=True,
            index=True,
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("enrolment_intents")
