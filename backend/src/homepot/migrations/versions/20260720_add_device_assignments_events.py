"""Add DeviceAssignment and DeviceLifecycleEvent models.

Revision ID: 20260720_add_device_assignments_events
Revises: 20260719_add_device_credentials
Create Date: 2026-07-20
"""

from alembic import op
import sqlalchemy as sa

revision = "20260720_add_device_assignments_events"
down_revision = "20260719_add_device_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create device_assignments and device_lifecycle_events tables."""
    op.create_table(
        "device_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.String(36), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("assignment_reason", sa.String(100), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unassigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
        ),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["sites.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_device_assignments_assignment_id"),
        "device_assignments",
        ["assignment_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_device_assignments_device_id"),
        "device_assignments",
        ["device_id"],
        unique=False,
    )

    op.create_table(
        "device_lifecycle_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("epoch_id", sa.Integer(), nullable=True),
        sa.Column("from_state", sa.String(20), nullable=True),
        sa.Column("to_state", sa.String(20), nullable=True),
        sa.Column("triggered_by_user_id", sa.Integer(), nullable=True),
        sa.Column("triggered_by_device_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(100), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
        ),
        sa.ForeignKeyConstraint(
            ["epoch_id"],
            ["lifecycle_epochs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["triggered_by_user_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["triggered_by_device_id"],
            ["devices.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_device_lifecycle_events_device_id"),
        "device_lifecycle_events",
        ["device_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_device_lifecycle_events_epoch_id"),
        "device_lifecycle_events",
        ["epoch_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_device_lifecycle_events_event_id"),
        "device_lifecycle_events",
        ["event_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_device_lifecycle_events_idempotency_key"),
        "device_lifecycle_events",
        ["idempotency_key"],
        unique=False,
    )


def downgrade() -> None:
    """Drop device_assignments and device_lifecycle_events tables."""
    op.drop_index(
        op.f("ix_device_lifecycle_events_idempotency_key"),
        table_name="device_lifecycle_events",
    )
    op.drop_index(
        op.f("ix_device_lifecycle_events_event_id"),
        table_name="device_lifecycle_events",
    )
    op.drop_index(
        op.f("ix_device_lifecycle_events_epoch_id"),
        table_name="device_lifecycle_events",
    )
    op.drop_index(
        op.f("ix_device_lifecycle_events_device_id"),
        table_name="device_lifecycle_events",
    )
    op.drop_table("device_lifecycle_events")

    op.drop_index(
        op.f("ix_device_assignments_device_id"),
        table_name="device_assignments",
    )
    op.drop_index(
        op.f("ix_device_assignments_assignment_id"),
        table_name="device_assignments",
    )
    op.drop_table("device_assignments")
