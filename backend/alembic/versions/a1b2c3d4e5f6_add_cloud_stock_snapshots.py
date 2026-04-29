"""add cloud stock snapshots

Revision ID: a1b2c3d4e5f6
Revises: 9d0e1f2a3b44
Create Date: 2026-04-29 08:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9d0e1f2a3b44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cloud_product_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("local_product_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("sku", sa.String(length=50), nullable=False),
        sa.Column("total_stock", sa.Integer(), nullable=False),
        sa.Column("low_stock_threshold", sa.Integer(), nullable=False),
        sa.Column("reorder_level", sa.Integer(), nullable=True),
        sa.Column("cost_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("selling_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_source_event_id", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["last_source_event_id"], ["ingested_sync_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "branch_id", "local_product_id", name="uq_cloud_product_snapshot_scope_product"),
    )
    op.create_index(op.f("ix_cloud_product_snapshots_id"), "cloud_product_snapshots", ["id"], unique=False)
    op.create_index(op.f("ix_cloud_product_snapshots_organization_id"), "cloud_product_snapshots", ["organization_id"], unique=False)
    op.create_index(op.f("ix_cloud_product_snapshots_branch_id"), "cloud_product_snapshots", ["branch_id"], unique=False)
    op.create_index(op.f("ix_cloud_product_snapshots_local_product_id"), "cloud_product_snapshots", ["local_product_id"], unique=False)
    op.create_index(op.f("ix_cloud_product_snapshots_sku"), "cloud_product_snapshots", ["sku"], unique=False)
    op.create_index(op.f("ix_cloud_product_snapshots_is_active"), "cloud_product_snapshots", ["is_active"], unique=False)
    op.create_index(op.f("ix_cloud_product_snapshots_last_source_event_id"), "cloud_product_snapshots", ["last_source_event_id"], unique=False)

    op.create_table(
        "cloud_batch_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("local_batch_id", sa.Integer(), nullable=False),
        sa.Column("local_product_id", sa.Integer(), nullable=False),
        sa.Column("batch_number", sa.String(length=100), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("cost_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("is_quarantined", sa.Boolean(), nullable=False),
        sa.Column("last_source_event_id", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["last_source_event_id"], ["ingested_sync_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "branch_id", "local_batch_id", name="uq_cloud_batch_snapshot_scope_batch"),
    )
    op.create_index(op.f("ix_cloud_batch_snapshots_id"), "cloud_batch_snapshots", ["id"], unique=False)
    op.create_index(op.f("ix_cloud_batch_snapshots_organization_id"), "cloud_batch_snapshots", ["organization_id"], unique=False)
    op.create_index(op.f("ix_cloud_batch_snapshots_branch_id"), "cloud_batch_snapshots", ["branch_id"], unique=False)
    op.create_index(op.f("ix_cloud_batch_snapshots_local_batch_id"), "cloud_batch_snapshots", ["local_batch_id"], unique=False)
    op.create_index(op.f("ix_cloud_batch_snapshots_local_product_id"), "cloud_batch_snapshots", ["local_product_id"], unique=False)
    op.create_index(op.f("ix_cloud_batch_snapshots_batch_number"), "cloud_batch_snapshots", ["batch_number"], unique=False)
    op.create_index(op.f("ix_cloud_batch_snapshots_expiry_date"), "cloud_batch_snapshots", ["expiry_date"], unique=False)
    op.create_index(op.f("ix_cloud_batch_snapshots_is_quarantined"), "cloud_batch_snapshots", ["is_quarantined"], unique=False)
    op.create_index(op.f("ix_cloud_batch_snapshots_last_source_event_id"), "cloud_batch_snapshots", ["last_source_event_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_cloud_batch_snapshots_last_source_event_id"), table_name="cloud_batch_snapshots")
    op.drop_index(op.f("ix_cloud_batch_snapshots_is_quarantined"), table_name="cloud_batch_snapshots")
    op.drop_index(op.f("ix_cloud_batch_snapshots_expiry_date"), table_name="cloud_batch_snapshots")
    op.drop_index(op.f("ix_cloud_batch_snapshots_batch_number"), table_name="cloud_batch_snapshots")
    op.drop_index(op.f("ix_cloud_batch_snapshots_local_product_id"), table_name="cloud_batch_snapshots")
    op.drop_index(op.f("ix_cloud_batch_snapshots_local_batch_id"), table_name="cloud_batch_snapshots")
    op.drop_index(op.f("ix_cloud_batch_snapshots_branch_id"), table_name="cloud_batch_snapshots")
    op.drop_index(op.f("ix_cloud_batch_snapshots_organization_id"), table_name="cloud_batch_snapshots")
    op.drop_index(op.f("ix_cloud_batch_snapshots_id"), table_name="cloud_batch_snapshots")
    op.drop_table("cloud_batch_snapshots")

    op.drop_index(op.f("ix_cloud_product_snapshots_last_source_event_id"), table_name="cloud_product_snapshots")
    op.drop_index(op.f("ix_cloud_product_snapshots_is_active"), table_name="cloud_product_snapshots")
    op.drop_index(op.f("ix_cloud_product_snapshots_sku"), table_name="cloud_product_snapshots")
    op.drop_index(op.f("ix_cloud_product_snapshots_local_product_id"), table_name="cloud_product_snapshots")
    op.drop_index(op.f("ix_cloud_product_snapshots_branch_id"), table_name="cloud_product_snapshots")
    op.drop_index(op.f("ix_cloud_product_snapshots_organization_id"), table_name="cloud_product_snapshots")
    op.drop_index(op.f("ix_cloud_product_snapshots_id"), table_name="cloud_product_snapshots")
    op.drop_table("cloud_product_snapshots")
