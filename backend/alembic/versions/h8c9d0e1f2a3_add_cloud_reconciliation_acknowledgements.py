"""add cloud reconciliation acknowledgements

Revision ID: h8c9d0e1f2a3
Revises: g7b8c9d0e1f2
Create Date: 2026-04-30 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h8c9d0e1f2a3"
down_revision: Union[str, None] = "g7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cloud_reconciliation_acknowledgements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("issue_key", sa.String(length=64), nullable=False),
        sa.Column("issue_type", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("acknowledged_by_user_id", sa.Integer(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["acknowledged_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "issue_key", name="uq_cloud_reconciliation_ack_org_issue"),
    )
    op.create_index(op.f("ix_cloud_reconciliation_acknowledgements_id"), "cloud_reconciliation_acknowledgements", ["id"], unique=False)
    op.create_index(op.f("ix_cloud_reconciliation_acknowledgements_organization_id"), "cloud_reconciliation_acknowledgements", ["organization_id"], unique=False)
    op.create_index(op.f("ix_cloud_reconciliation_acknowledgements_branch_id"), "cloud_reconciliation_acknowledgements", ["branch_id"], unique=False)
    op.create_index(op.f("ix_cloud_reconciliation_acknowledgements_issue_key"), "cloud_reconciliation_acknowledgements", ["issue_key"], unique=False)
    op.create_index(op.f("ix_cloud_reconciliation_acknowledgements_issue_type"), "cloud_reconciliation_acknowledgements", ["issue_type"], unique=False)
    op.create_index(op.f("ix_cloud_reconciliation_acknowledgements_severity"), "cloud_reconciliation_acknowledgements", ["severity"], unique=False)
    op.create_index(op.f("ix_cloud_reconciliation_acknowledgements_status"), "cloud_reconciliation_acknowledgements", ["status"], unique=False)
    op.create_index(op.f("ix_cloud_reconciliation_acknowledgements_acknowledged_by_user_id"), "cloud_reconciliation_acknowledgements", ["acknowledged_by_user_id"], unique=False)
    op.create_index(op.f("ix_cloud_reconciliation_acknowledgements_acknowledged_at"), "cloud_reconciliation_acknowledgements", ["acknowledged_at"], unique=False)
    op.create_index(op.f("ix_cloud_reconciliation_acknowledgements_resolved_by_user_id"), "cloud_reconciliation_acknowledgements", ["resolved_by_user_id"], unique=False)
    op.create_index(op.f("ix_cloud_reconciliation_acknowledgements_resolved_at"), "cloud_reconciliation_acknowledgements", ["resolved_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_cloud_reconciliation_acknowledgements_resolved_at"), table_name="cloud_reconciliation_acknowledgements")
    op.drop_index(op.f("ix_cloud_reconciliation_acknowledgements_resolved_by_user_id"), table_name="cloud_reconciliation_acknowledgements")
    op.drop_index(op.f("ix_cloud_reconciliation_acknowledgements_acknowledged_at"), table_name="cloud_reconciliation_acknowledgements")
    op.drop_index(op.f("ix_cloud_reconciliation_acknowledgements_acknowledged_by_user_id"), table_name="cloud_reconciliation_acknowledgements")
    op.drop_index(op.f("ix_cloud_reconciliation_acknowledgements_status"), table_name="cloud_reconciliation_acknowledgements")
    op.drop_index(op.f("ix_cloud_reconciliation_acknowledgements_severity"), table_name="cloud_reconciliation_acknowledgements")
    op.drop_index(op.f("ix_cloud_reconciliation_acknowledgements_issue_type"), table_name="cloud_reconciliation_acknowledgements")
    op.drop_index(op.f("ix_cloud_reconciliation_acknowledgements_issue_key"), table_name="cloud_reconciliation_acknowledgements")
    op.drop_index(op.f("ix_cloud_reconciliation_acknowledgements_branch_id"), table_name="cloud_reconciliation_acknowledgements")
    op.drop_index(op.f("ix_cloud_reconciliation_acknowledgements_organization_id"), table_name="cloud_reconciliation_acknowledgements")
    op.drop_index(op.f("ix_cloud_reconciliation_acknowledgements_id"), table_name="cloud_reconciliation_acknowledgements")
    op.drop_table("cloud_reconciliation_acknowledgements")
