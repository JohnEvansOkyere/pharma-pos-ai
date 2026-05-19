"""Add occurred_at to cloud fact tables for business-time reporting

Revision ID: j0e1f2a3b4c5
Revises: 650dc9d5a2f1
Create Date: 2026-05-19 01:30:00.000000+00:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "j0e1f2a3b4c5"
down_revision = "650dc9d5a2f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cloud_sale_facts",
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_cloud_sale_facts_occurred_at"), "cloud_sale_facts", ["occurred_at"])
    op.add_column(
        "cloud_inventory_movement_facts",
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_cloud_inventory_movement_facts_occurred_at"),
        "cloud_inventory_movement_facts",
        ["occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_cloud_inventory_movement_facts_occurred_at"),
        table_name="cloud_inventory_movement_facts",
    )
    op.drop_column("cloud_inventory_movement_facts", "occurred_at")
    op.drop_index(op.f("ix_cloud_sale_facts_occurred_at"), table_name="cloud_sale_facts")
    op.drop_column("cloud_sale_facts", "occurred_at")
