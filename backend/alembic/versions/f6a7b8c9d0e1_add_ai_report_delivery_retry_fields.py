"""add ai report delivery retry fields

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-30 01:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_weekly_report_deliveries", sa.Column("retryable", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("ai_weekly_report_deliveries", sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ai_weekly_report_deliveries", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ai_weekly_report_deliveries", sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False))
    op.create_index(op.f("ix_ai_weekly_report_deliveries_retryable"), "ai_weekly_report_deliveries", ["retryable"], unique=False)
    op.create_index(op.f("ix_ai_weekly_report_deliveries_last_attempted_at"), "ai_weekly_report_deliveries", ["last_attempted_at"], unique=False)
    op.create_index(op.f("ix_ai_weekly_report_deliveries_next_retry_at"), "ai_weekly_report_deliveries", ["next_retry_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_weekly_report_deliveries_next_retry_at"), table_name="ai_weekly_report_deliveries")
    op.drop_index(op.f("ix_ai_weekly_report_deliveries_last_attempted_at"), table_name="ai_weekly_report_deliveries")
    op.drop_index(op.f("ix_ai_weekly_report_deliveries_retryable"), table_name="ai_weekly_report_deliveries")
    op.drop_column("ai_weekly_report_deliveries", "max_attempts")
    op.drop_column("ai_weekly_report_deliveries", "next_retry_at")
    op.drop_column("ai_weekly_report_deliveries", "last_attempted_at")
    op.drop_column("ai_weekly_report_deliveries", "retryable")
