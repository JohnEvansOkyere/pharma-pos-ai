"""add ai weekly report deliveries

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-29 12:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_weekly_report_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("recipient", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("provider_response", sa.JSON(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["ai_weekly_manager_reports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_weekly_report_deliveries_id"), "ai_weekly_report_deliveries", ["id"], unique=False)
    op.create_index(op.f("ix_ai_weekly_report_deliveries_report_id"), "ai_weekly_report_deliveries", ["report_id"], unique=False)
    op.create_index(
        op.f("ix_ai_weekly_report_deliveries_organization_id"),
        "ai_weekly_report_deliveries",
        ["organization_id"],
        unique=False,
    )
    op.create_index(op.f("ix_ai_weekly_report_deliveries_branch_id"), "ai_weekly_report_deliveries", ["branch_id"], unique=False)
    op.create_index(op.f("ix_ai_weekly_report_deliveries_channel"), "ai_weekly_report_deliveries", ["channel"], unique=False)
    op.create_index(op.f("ix_ai_weekly_report_deliveries_recipient"), "ai_weekly_report_deliveries", ["recipient"], unique=False)
    op.create_index(op.f("ix_ai_weekly_report_deliveries_status"), "ai_weekly_report_deliveries", ["status"], unique=False)
    op.create_index(op.f("ix_ai_weekly_report_deliveries_sent_at"), "ai_weekly_report_deliveries", ["sent_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_weekly_report_deliveries_sent_at"), table_name="ai_weekly_report_deliveries")
    op.drop_index(op.f("ix_ai_weekly_report_deliveries_status"), table_name="ai_weekly_report_deliveries")
    op.drop_index(op.f("ix_ai_weekly_report_deliveries_recipient"), table_name="ai_weekly_report_deliveries")
    op.drop_index(op.f("ix_ai_weekly_report_deliveries_channel"), table_name="ai_weekly_report_deliveries")
    op.drop_index(op.f("ix_ai_weekly_report_deliveries_branch_id"), table_name="ai_weekly_report_deliveries")
    op.drop_index(op.f("ix_ai_weekly_report_deliveries_organization_id"), table_name="ai_weekly_report_deliveries")
    op.drop_index(op.f("ix_ai_weekly_report_deliveries_report_id"), table_name="ai_weekly_report_deliveries")
    op.drop_index(op.f("ix_ai_weekly_report_deliveries_id"), table_name="ai_weekly_report_deliveries")
    op.drop_table("ai_weekly_report_deliveries")
