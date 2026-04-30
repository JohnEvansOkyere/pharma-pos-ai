"""add audit log hash chain

Revision ID: a9b8c7d6e5f4
Revises: h8c9d0e1f2a3
Create Date: 2026-04-30 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a9b8c7d6e5f4"
down_revision: Union[str, None] = "h8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("activity_logs", sa.Column("hash_version", sa.Integer(), nullable=True))
    op.add_column("activity_logs", sa.Column("previous_hash", sa.String(length=64), nullable=True))
    op.add_column("activity_logs", sa.Column("current_hash", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_activity_logs_previous_hash"), "activity_logs", ["previous_hash"], unique=False)
    op.create_index(op.f("ix_activity_logs_current_hash"), "activity_logs", ["current_hash"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_activity_logs_current_hash"), table_name="activity_logs")
    op.drop_index(op.f("ix_activity_logs_previous_hash"), table_name="activity_logs")
    op.drop_column("activity_logs", "current_hash")
    op.drop_column("activity_logs", "previous_hash")
    op.drop_column("activity_logs", "hash_version")
