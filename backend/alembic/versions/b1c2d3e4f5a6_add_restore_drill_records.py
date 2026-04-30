"""add restore drill records

Revision ID: b1c2d3e4f5a6
Revises: a9b8c7d6e5f4
Create Date: 2026-04-30 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a9b8c7d6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "restore_drills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("backup_path", sa.Text(), nullable=False),
        sa.Column("backup_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("backup_size_bytes", sa.Integer(), nullable=True),
        sa.Column("restore_target", sa.String(length=300), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("verification_summary", sa.JSON(), nullable=False),
        sa.Column("tested_by_user_id", sa.Integer(), nullable=False),
        sa.Column("tested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tested_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_restore_drills_id"), "restore_drills", ["id"], unique=False)
    op.create_index(op.f("ix_restore_drills_status"), "restore_drills", ["status"], unique=False)
    op.create_index(op.f("ix_restore_drills_tested_by_user_id"), "restore_drills", ["tested_by_user_id"], unique=False)
    op.create_index(op.f("ix_restore_drills_tested_at"), "restore_drills", ["tested_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_restore_drills_tested_at"), table_name="restore_drills")
    op.drop_index(op.f("ix_restore_drills_tested_by_user_id"), table_name="restore_drills")
    op.drop_index(op.f("ix_restore_drills_status"), table_name="restore_drills")
    op.drop_index(op.f("ix_restore_drills_id"), table_name="restore_drills")
    op.drop_table("restore_drills")
