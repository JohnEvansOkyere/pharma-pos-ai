"""add ai report delivery settings and idempotency

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-29 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_weekly_manager_reports",
        sa.Column("report_scope_key", sa.String(length=50), server_default="organization", nullable=False),
    )
    op.execute(
        "UPDATE ai_weekly_manager_reports "
        "SET report_scope_key = CASE "
        "WHEN branch_id IS NULL THEN 'organization' "
        "ELSE 'branch:' || branch_id "
        "END"
    )
    op.create_index(
        op.f("ix_ai_weekly_manager_reports_report_scope_key"),
        "ai_weekly_manager_reports",
        ["report_scope_key"],
        unique=False,
    )
    op.create_index(
        "uq_ai_weekly_reports_scope_action_period",
        "ai_weekly_manager_reports",
        ["organization_id", "report_scope_key", "action_period_start", "action_period_end"],
        unique=True,
    )

    op.create_table(
        "ai_weekly_report_delivery_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("report_scope_key", sa.String(length=50), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), nullable=False),
        sa.Column("email_recipients", sa.JSON(), nullable=False),
        sa.Column("telegram_enabled", sa.Boolean(), nullable=False),
        sa.Column("telegram_chat_ids", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_weekly_report_delivery_settings_id"), "ai_weekly_report_delivery_settings", ["id"], unique=False)
    op.create_index(
        op.f("ix_ai_weekly_report_delivery_settings_organization_id"),
        "ai_weekly_report_delivery_settings",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_weekly_report_delivery_settings_branch_id"),
        "ai_weekly_report_delivery_settings",
        ["branch_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_weekly_report_delivery_settings_report_scope_key"),
        "ai_weekly_report_delivery_settings",
        ["report_scope_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_weekly_report_delivery_settings_is_active"),
        "ai_weekly_report_delivery_settings",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_weekly_report_delivery_settings_created_by_user_id"),
        "ai_weekly_report_delivery_settings",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_weekly_report_delivery_settings_updated_by_user_id"),
        "ai_weekly_report_delivery_settings",
        ["updated_by_user_id"],
        unique=False,
    )
    op.create_index(
        "uq_ai_weekly_delivery_settings_scope",
        "ai_weekly_report_delivery_settings",
        ["organization_id", "report_scope_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_ai_weekly_delivery_settings_scope", table_name="ai_weekly_report_delivery_settings")
    op.drop_index(op.f("ix_ai_weekly_report_delivery_settings_updated_by_user_id"), table_name="ai_weekly_report_delivery_settings")
    op.drop_index(op.f("ix_ai_weekly_report_delivery_settings_created_by_user_id"), table_name="ai_weekly_report_delivery_settings")
    op.drop_index(op.f("ix_ai_weekly_report_delivery_settings_is_active"), table_name="ai_weekly_report_delivery_settings")
    op.drop_index(op.f("ix_ai_weekly_report_delivery_settings_report_scope_key"), table_name="ai_weekly_report_delivery_settings")
    op.drop_index(op.f("ix_ai_weekly_report_delivery_settings_branch_id"), table_name="ai_weekly_report_delivery_settings")
    op.drop_index(op.f("ix_ai_weekly_report_delivery_settings_organization_id"), table_name="ai_weekly_report_delivery_settings")
    op.drop_index(op.f("ix_ai_weekly_report_delivery_settings_id"), table_name="ai_weekly_report_delivery_settings")
    op.drop_table("ai_weekly_report_delivery_settings")
    op.drop_index("uq_ai_weekly_reports_scope_action_period", table_name="ai_weekly_manager_reports")
    op.drop_index(op.f("ix_ai_weekly_manager_reports_report_scope_key"), table_name="ai_weekly_manager_reports")
    op.drop_column("ai_weekly_manager_reports", "report_scope_key")
