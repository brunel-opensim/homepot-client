"""Add issued_by to the device_commands table.

Records who queued each command. The command queue is the natural home for
the actor, and it is what lets the dashboard answer "who last touched this
device?" when two technicians work the same device. The audit log already
captures the actor for queued commands, but it is a separate table and is
not exposed on the command history endpoint.

Revision ID: 20260929_add_command_issued_by
Revises: 20260914_add_bootstrap_key_enc
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260929_add_command_issued_by"
down_revision = "20260914_add_bootstrap_key_enc"
branch_labels = None
depends_on = None

TABLE = "device_commands"
COLUMN = "issued_by"


def _column_exists(table: str, column: str) -> bool:
    """Return whether column is already present on table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    """Add the issuing user to queued commands, idempotently."""
    if _column_exists(TABLE, COLUMN):
        return
    op.add_column(TABLE, sa.Column(COLUMN, sa.String(length=255), nullable=True))
    op.create_index(op.f("ix_device_commands_issued_by"), TABLE, [COLUMN])


def downgrade() -> None:
    """Remove the issuing user column."""
    op.drop_index(op.f("ix_device_commands_issued_by"), table_name=TABLE)
    op.drop_column(TABLE, COLUMN)
