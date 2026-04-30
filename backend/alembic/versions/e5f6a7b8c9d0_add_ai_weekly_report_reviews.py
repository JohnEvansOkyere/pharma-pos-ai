"""add ai weekly report reviews

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-30 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_weekly_manager_reports", sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True))
    op.add_column("ai_weekly_manager_reports", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ai_weekly_manager_reports", sa.Column("review_notes", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_ai_weekly_reports_reviewed_by_user_id_users",
        "ai_weekly_manager_reports",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_ai_weekly_manager_reports_reviewed_by_user_id"),
        "ai_weekly_manager_reports",
        ["reviewed_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_weekly_manager_reports_reviewed_at"),
        "ai_weekly_manager_reports",
        ["reviewed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_weekly_manager_reports_reviewed_at"), table_name="ai_weekly_manager_reports")
    op.drop_index(op.f("ix_ai_weekly_manager_reports_reviewed_by_user_id"), table_name="ai_weekly_manager_reports")
    op.drop_constraint(
        "fk_ai_weekly_reports_reviewed_by_user_id_users",
        "ai_weekly_manager_reports",
        type_="foreignkey",
    )
    op.drop_column("ai_weekly_manager_reports", "review_notes")
    op.drop_column("ai_weekly_manager_reports", "reviewed_at")
    op.drop_column("ai_weekly_manager_reports", "reviewed_by_user_id")
