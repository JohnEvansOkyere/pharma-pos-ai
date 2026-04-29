"""add ai weekly manager reports

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-29 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_weekly_manager_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("generated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("performance_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("performance_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action_period_start", sa.Date(), nullable=False),
        sa.Column("action_period_end", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("executive_summary", sa.Text(), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("tool_results", sa.JSON(), nullable=False),
        sa.Column("safety_notes", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["generated_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_weekly_manager_reports_id"), "ai_weekly_manager_reports", ["id"], unique=False)
    op.create_index(
        op.f("ix_ai_weekly_manager_reports_organization_id"),
        "ai_weekly_manager_reports",
        ["organization_id"],
        unique=False,
    )
    op.create_index(op.f("ix_ai_weekly_manager_reports_branch_id"), "ai_weekly_manager_reports", ["branch_id"], unique=False)
    op.create_index(
        op.f("ix_ai_weekly_manager_reports_generated_by_user_id"),
        "ai_weekly_manager_reports",
        ["generated_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_weekly_manager_reports_performance_period_start"),
        "ai_weekly_manager_reports",
        ["performance_period_start"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_weekly_manager_reports_performance_period_end"),
        "ai_weekly_manager_reports",
        ["performance_period_end"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_weekly_manager_reports_action_period_start"),
        "ai_weekly_manager_reports",
        ["action_period_start"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_weekly_manager_reports_action_period_end"),
        "ai_weekly_manager_reports",
        ["action_period_end"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_weekly_manager_reports_generated_at"),
        "ai_weekly_manager_reports",
        ["generated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_weekly_manager_reports_generated_at"), table_name="ai_weekly_manager_reports")
    op.drop_index(op.f("ix_ai_weekly_manager_reports_action_period_end"), table_name="ai_weekly_manager_reports")
    op.drop_index(op.f("ix_ai_weekly_manager_reports_action_period_start"), table_name="ai_weekly_manager_reports")
    op.drop_index(op.f("ix_ai_weekly_manager_reports_performance_period_end"), table_name="ai_weekly_manager_reports")
    op.drop_index(op.f("ix_ai_weekly_manager_reports_performance_period_start"), table_name="ai_weekly_manager_reports")
    op.drop_index(op.f("ix_ai_weekly_manager_reports_generated_by_user_id"), table_name="ai_weekly_manager_reports")
    op.drop_index(op.f("ix_ai_weekly_manager_reports_branch_id"), table_name="ai_weekly_manager_reports")
    op.drop_index(op.f("ix_ai_weekly_manager_reports_organization_id"), table_name="ai_weekly_manager_reports")
    op.drop_index(op.f("ix_ai_weekly_manager_reports_id"), table_name="ai_weekly_manager_reports")
    op.drop_table("ai_weekly_manager_reports")
