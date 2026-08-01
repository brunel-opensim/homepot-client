"""Add sites.bootstrap_key_hash and devices.device_permissions/capabilities.

Revision ID: 20260801_add_site_device_columns
Revises: 20260726_add_is_simulated
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "20260801_add_site_device_columns"
down_revision = "20260726_add_is_simulated"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    """Return True if *column* already exists on *table*.

    The app creates the schema with ``Base.metadata.create_all`` at startup
    and this migration targets existing deployments that predate the
    columns, so guard against pre-existing columns (e.g. created by
    create_all on a fresh DB or by manual ALTER).
    """
    inspector = inspect(op.get_bind())
    return any(col["name"] == column for col in inspector.get_columns(table))


def upgrade() -> None:
    """Add the missing site/device columns introduced across PRs 220-221."""
    if not _column_exists("sites", "bootstrap_key_hash"):
        op.add_column(
            "sites",
            sa.Column("bootstrap_key_hash", sa.String(length=255), nullable=True),
        )
    if not _column_exists("devices", "device_permissions"):
        op.add_column(
            "devices",
            sa.Column("device_permissions", sa.JSON(), nullable=True),
        )
    if not _column_exists("devices", "capabilities"):
        op.add_column(
            "devices",
            sa.Column("capabilities", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    """Rollback the site/device columns."""
    if _column_exists("devices", "capabilities"):
        op.drop_column("devices", "capabilities")
    if _column_exists("devices", "device_permissions"):
        op.drop_column("devices", "device_permissions")
    if _column_exists("sites", "bootstrap_key_hash"):
        op.drop_column("sites", "bootstrap_key_hash")
