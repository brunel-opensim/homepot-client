"""Add the investigation session tables.

Introduces durable storage for backend-owned AI investigations (see
``docs/ai-ui-design.md`` and Stage 2 of the investigation workflow):

* ``investigation_sessions`` - one row per investigation, owned by a user and
  scoped to a site/device.
* ``investigation_messages`` - the ordered messages of a session (user +
  assistant), including trust/routing/sources evidence.
* ``investigation_runs`` - one row per submitted message tracking the
  lifecycle of answering it (pending/running/completed/cancelled/failed).

Creation is guarded because the application also builds its schema with
``Base.metadata.create_all`` at startup, which may have created these tables
already on a fresh database.

Revision ID: 20261101_add_investigation_tables
Revises: 20261028_add_agent_health
Create Date: 2026-11-01
"""

from alembic import op
import sqlalchemy as sa

revision = "20261101_add_investigation_tables"
down_revision = "20261028_add_agent_health"
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    return table in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has_table("investigation_sessions"):
        op.create_table(
            "investigation_sessions",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("session_id", sa.String(length=36), nullable=False, unique=True, index=True),
            sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=True, index=True),
            sa.Column("device_id", sa.String(length=50), nullable=True, index=True),
            sa.Column("title", sa.String(length=200), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        )

    if not _has_table("investigation_messages"):
        op.create_table(
            "investigation_messages",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("message_id", sa.String(length=36), nullable=False, unique=True, index=True),
            sa.Column("session_id", sa.Integer(), sa.ForeignKey("investigation_sessions.id"), nullable=False, index=True),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False, index=True),
            sa.Column("trust", sa.JSON(), nullable=True),
            sa.Column("routing", sa.JSON(), nullable=True),
            sa.Column("sources", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _has_table("investigation_runs"):
        op.create_table(
            "investigation_runs",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("run_id", sa.String(length=36), nullable=False, unique=True, index=True),
            sa.Column("session_id", sa.Integer(), sa.ForeignKey("investigation_sessions.id"), nullable=False, index=True),
            sa.Column("message_id", sa.Integer(), sa.ForeignKey("investigation_messages.id"), nullable=True, index=True),
            sa.Column("status", sa.String(length=20), nullable=False, index=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    for t in ("investigation_runs", "investigation_messages", "investigation_sessions"):
        if _has_table(t):
            op.drop_table(t)