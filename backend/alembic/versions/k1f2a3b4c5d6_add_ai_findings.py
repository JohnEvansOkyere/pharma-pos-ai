"""add ai_findings

Revision ID: k1f2a3b4c5d6
Revises: j0e1f2a3b4c5
Create Date: 2026-05-19 03:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "k1f2a3b4c5d6"
down_revision = "j0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_findings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("affected_count", sa.Integer(), nullable=False),
        sa.Column("action_hint", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(length=120), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("data_trust_status", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "fingerprint", name="uq_ai_findings_org_fingerprint"),
    )
    op.create_index("ix_ai_findings_id", "ai_findings", ["id"])
    op.create_index("ix_ai_findings_organization_id", "ai_findings", ["organization_id"])
    op.create_index("ix_ai_findings_branch_id", "ai_findings", ["branch_id"])
    op.create_index("ix_ai_findings_type", "ai_findings", ["type"])
    op.create_index("ix_ai_findings_severity", "ai_findings", ["severity"])
    op.create_index("ix_ai_findings_fingerprint", "ai_findings", ["fingerprint"])
    op.create_index("ix_ai_findings_status", "ai_findings", ["status"])
    op.create_index("ix_ai_findings_due_date", "ai_findings", ["due_date"])
    op.create_index("ix_ai_findings_snoozed_until", "ai_findings", ["snoozed_until"])
    op.create_index("ix_ai_findings_resolved_at", "ai_findings", ["resolved_at"])
    op.create_index("ix_ai_findings_last_seen_at", "ai_findings", ["last_seen_at"])
    op.create_index("ix_ai_findings_resolved_by_user_id", "ai_findings", ["resolved_by_user_id"])


def downgrade():
    op.drop_table("ai_findings")
