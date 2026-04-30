"""add ai external provider settings

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-04-30 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_external_provider_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("external_ai_enabled", sa.Boolean(), nullable=False),
        sa.Column("allowed_providers", sa.JSON(), nullable=False),
        sa.Column("preferred_provider", sa.String(length=50), nullable=True),
        sa.Column("preferred_model", sa.String(length=100), nullable=True),
        sa.Column("consent_text", sa.Text(), nullable=True),
        sa.Column("consented_by_user_id", sa.Integer(), nullable=True),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["consented_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_external_provider_settings_id"), "ai_external_provider_settings", ["id"], unique=False)
    op.create_index(
        op.f("ix_ai_external_provider_settings_organization_id"),
        "ai_external_provider_settings",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_external_provider_settings_external_ai_enabled"),
        "ai_external_provider_settings",
        ["external_ai_enabled"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_external_provider_settings_consented_by_user_id"),
        "ai_external_provider_settings",
        ["consented_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_external_provider_settings_consented_at"),
        "ai_external_provider_settings",
        ["consented_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_external_provider_settings_updated_by_user_id"),
        "ai_external_provider_settings",
        ["updated_by_user_id"],
        unique=False,
    )
    op.create_index(
        "uq_ai_external_provider_settings_org",
        "ai_external_provider_settings",
        ["organization_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_ai_external_provider_settings_org", table_name="ai_external_provider_settings")
    op.drop_index(op.f("ix_ai_external_provider_settings_updated_by_user_id"), table_name="ai_external_provider_settings")
    op.drop_index(op.f("ix_ai_external_provider_settings_consented_at"), table_name="ai_external_provider_settings")
    op.drop_index(op.f("ix_ai_external_provider_settings_consented_by_user_id"), table_name="ai_external_provider_settings")
    op.drop_index(op.f("ix_ai_external_provider_settings_external_ai_enabled"), table_name="ai_external_provider_settings")
    op.drop_index(op.f("ix_ai_external_provider_settings_organization_id"), table_name="ai_external_provider_settings")
    op.drop_index(op.f("ix_ai_external_provider_settings_id"), table_name="ai_external_provider_settings")
    op.drop_table("ai_external_provider_settings")
