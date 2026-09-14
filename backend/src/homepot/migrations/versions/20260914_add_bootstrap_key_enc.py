"""Add sites.bootstrap_key_enc for retrievable (encrypted) bootstrap keys.

Revision ID: 20260914_add_bootstrap_key_enc
Revises: 20260817_add_site_lifecycle_state
Create Date: 2026-09-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "20260914_add_bootstrap_key_enc"
down_revision = "20260817_add_site_lifecycle_state"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    """Return True if *column* already exists on *table*.

    The app creates the schema with ``Base.metadata.create_all`` at startup
    and this migration targets existing deployments that predate the column,
    so guard against pre-existing columns (e.g. created by create_all on a
    fresh DB or by manual ALTER).
    """
    inspector = inspect(op.get_bind())
    return any(col["name"] == column for col in inspector.get_columns(table))


def upgrade() -> None:
    """Store the Fernet-encrypted plaintext bootstrap key for re-display."""
    if not _column_exists("sites", "bootstrap_key_enc"):
        op.add_column(
            "sites",
            sa.Column("bootstrap_key_enc", sa.String(length=1024), nullable=True),
        )


def downgrade() -> None:
    """Drop the encrypted-key column."""
    if _column_exists("sites", "bootstrap_key_enc"):
        op.drop_column("sites", "bootstrap_key_enc")
