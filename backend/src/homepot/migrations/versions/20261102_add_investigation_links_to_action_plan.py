"""Add investigation links to ai_action_plan.

Links AI action plans to the originating investigation session/run/message
(Stage 5 of the investigation workflow). All columns are nullable so existing
plans remain valid.

Revision ID: 20261102_add_investigation_links_to_action_plan
Revises: 20261101_add_investigation_tables
Create Date: 2026-11-02
"""

from alembic import op
import sqlalchemy as sa

revision = "20261102_add_investigation_links_to_action_plan"
down_revision = "20261101_add_investigation_tables"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    for col in ("investigation_session_id", "investigation_run_id", "investigation_message_id"):
        if not _has_column("ai_action_plan", col):
            op.add_column("ai_action_plan", sa.Column(col, sa.String(length=36), nullable=True))
    # Indexes
    inspector = sa.inspect(op.get_bind())
    if "ai_action_plan" in inspector.get_table_names():
        existing = {i["name"] for i in inspector.get_indexes("ai_action_plan")}
        for idx, col in (
            ("idx_ai_action_plan_session", "investigation_session_id"),
            ("idx_ai_action_plan_run", "investigation_run_id"),
        ):
            if idx not in existing:
                op.create_index(idx, "ai_action_plan", [col])


def downgrade() -> None:
    for col in ("investigation_session_id", "investigation_run_id", "investigation_message_id"):
        if _has_column("ai_action_plan", col):
            op.drop_column("ai_action_plan", col)