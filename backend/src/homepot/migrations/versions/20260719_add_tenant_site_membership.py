"""Add Tenant, TenantMembership, SiteMembership models and tenant_id columns.

Revision ID: 20260719_add_tenant_membership
Revises: 20260719_add_lifecycle_health
Create Date: 2026-07-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "20260719_add_tenant_membership"
down_revision = "20260719_add_lifecycle_health"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create tenant and membership tables, add tenant_id to users/sites, seed default tenant."""
    # Create tenants table
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "slug", sa.String(length=50), unique=True, index=True, nullable=False
        ),
        sa.Column("settings", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    # Create tenant_memberships table
    op.create_table(
        "tenant_memberships",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False
        ),
        sa.Column("role", sa.String(length=50), default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    # Create site_memberships table
    op.create_table(
        "site_memberships",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("role", sa.String(length=50), default="viewer"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    # Add tenant_id to users
    op.add_column(
        "users",
        sa.Column(
            "tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True
        ),
    )

    # Add tenant_id to sites
    op.add_column(
        "sites",
        sa.Column(
            "tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True
        ),
    )

    # Create a default tenant and migrate existing users/sites into it.
    # Generate a connection-aware slug from the default tenant name.
    op.execute(
        text(
            "INSERT INTO tenants (name, slug, is_active, created_at, updated_at) "
            "VALUES ('Default Tenant', 'default', true, now(), now())"
        )
    )

    # Get the id of the default tenant we just inserted.
    conn = op.get_bind()
    result = conn.execute(text("SELECT id FROM tenants WHERE slug = 'default'"))
    default_tenant_id = result.scalar()

    if default_tenant_id:
        conn = op.get_bind()
        conn.execute(
            text("UPDATE users SET tenant_id = :tid WHERE tenant_id IS NULL"),
            {"tid": default_tenant_id},
        )
        conn.execute(
            text("UPDATE sites SET tenant_id = :tid WHERE tenant_id IS NULL"),
            {"tid": default_tenant_id},
        )


def downgrade() -> None:
    """Rollback tenant and membership tables and columns."""
    op.drop_column("sites", "tenant_id")
    op.drop_column("users", "tenant_id")
    op.drop_table("site_memberships")
    op.drop_table("tenant_memberships")
    op.drop_table("tenants")
