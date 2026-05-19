"""Add AI chat sessions and messages tables

Revision ID: m3b4c5d6e7f8
Revises: l2a3b4c5d6e7
Create Date: 2026-05-19 12:00:00.000000+00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "m3b4c5d6e7f8"
down_revision = "l2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_chat_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_chat_sessions_id"), "ai_chat_sessions", ["id"])
    op.create_index(op.f("ix_ai_chat_sessions_organization_id"), "ai_chat_sessions", ["organization_id"])
    op.create_index(op.f("ix_ai_chat_sessions_branch_id"), "ai_chat_sessions", ["branch_id"])
    op.create_index(op.f("ix_ai_chat_sessions_user_id"), "ai_chat_sessions", ["user_id"])
    op.create_index(op.f("ix_ai_chat_sessions_closed_at"), "ai_chat_sessions", ["closed_at"])
    op.create_index(op.f("ix_ai_chat_sessions_created_at"), "ai_chat_sessions", ["created_at"])

    op.create_table(
        "ai_chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["ai_chat_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_chat_messages_id"), "ai_chat_messages", ["id"])
    op.create_index(op.f("ix_ai_chat_messages_session_id"), "ai_chat_messages", ["session_id"])
    op.create_index(op.f("ix_ai_chat_messages_created_at"), "ai_chat_messages", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_chat_messages_created_at"), table_name="ai_chat_messages")
    op.drop_index(op.f("ix_ai_chat_messages_session_id"), table_name="ai_chat_messages")
    op.drop_index(op.f("ix_ai_chat_messages_id"), table_name="ai_chat_messages")
    op.drop_table("ai_chat_messages")
    op.drop_index(op.f("ix_ai_chat_sessions_created_at"), table_name="ai_chat_sessions")
    op.drop_index(op.f("ix_ai_chat_sessions_closed_at"), table_name="ai_chat_sessions")
    op.drop_index(op.f("ix_ai_chat_sessions_user_id"), table_name="ai_chat_sessions")
    op.drop_index(op.f("ix_ai_chat_sessions_branch_id"), table_name="ai_chat_sessions")
    op.drop_index(op.f("ix_ai_chat_sessions_organization_id"), table_name="ai_chat_sessions")
    op.drop_index(op.f("ix_ai_chat_sessions_id"), table_name="ai_chat_sessions")
    op.drop_table("ai_chat_sessions")
