"""add cloud projection tables

Revision ID: 9d0e1f2a3b44
Revises: 8c9d0e1f2a33
Create Date: 2026-04-29 01:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9d0e1f2a3b44"
down_revision: Union[str, None] = "8c9d0e1f2a33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("ingested_sync_events") as batch_op:
        batch_op.add_column(sa.Column("projected_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("projection_error", sa.Text(), nullable=True))

    op.create_table(
        "cloud_sale_facts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_event_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("source_device_id", sa.Integer(), nullable=False),
        sa.Column("local_sale_id", sa.Integer(), nullable=False),
        sa.Column("invoice_number", sa.String(length=50), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_method", sa.String(length=50), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["source_device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["source_event_id"], ["ingested_sync_events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cloud_sale_facts_id"), "cloud_sale_facts", ["id"], unique=False)
    op.create_index(op.f("ix_cloud_sale_facts_source_event_id"), "cloud_sale_facts", ["source_event_id"], unique=True)
    op.create_index(op.f("ix_cloud_sale_facts_organization_id"), "cloud_sale_facts", ["organization_id"], unique=False)
    op.create_index(op.f("ix_cloud_sale_facts_branch_id"), "cloud_sale_facts", ["branch_id"], unique=False)
    op.create_index(op.f("ix_cloud_sale_facts_source_device_id"), "cloud_sale_facts", ["source_device_id"], unique=False)
    op.create_index(op.f("ix_cloud_sale_facts_local_sale_id"), "cloud_sale_facts", ["local_sale_id"], unique=False)
    op.create_index(op.f("ix_cloud_sale_facts_invoice_number"), "cloud_sale_facts", ["invoice_number"], unique=False)

    op.create_table(
        "cloud_inventory_movement_facts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_event_id", sa.Integer(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("source_device_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("local_product_id", sa.Integer(), nullable=True),
        sa.Column("local_batch_id", sa.Integer(), nullable=True),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column("stock_after", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=300), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["source_device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["source_event_id"], ["ingested_sync_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_event_id", "line_number", name="uq_cloud_inventory_movement_event_line"),
    )
    op.create_index(op.f("ix_cloud_inventory_movement_facts_id"), "cloud_inventory_movement_facts", ["id"], unique=False)
    op.create_index(op.f("ix_cloud_inventory_movement_facts_source_event_id"), "cloud_inventory_movement_facts", ["source_event_id"], unique=False)
    op.create_index(op.f("ix_cloud_inventory_movement_facts_organization_id"), "cloud_inventory_movement_facts", ["organization_id"], unique=False)
    op.create_index(op.f("ix_cloud_inventory_movement_facts_branch_id"), "cloud_inventory_movement_facts", ["branch_id"], unique=False)
    op.create_index(op.f("ix_cloud_inventory_movement_facts_source_device_id"), "cloud_inventory_movement_facts", ["source_device_id"], unique=False)
    op.create_index(op.f("ix_cloud_inventory_movement_facts_event_type"), "cloud_inventory_movement_facts", ["event_type"], unique=False)
    op.create_index(op.f("ix_cloud_inventory_movement_facts_local_product_id"), "cloud_inventory_movement_facts", ["local_product_id"], unique=False)
    op.create_index(op.f("ix_cloud_inventory_movement_facts_local_batch_id"), "cloud_inventory_movement_facts", ["local_batch_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_cloud_inventory_movement_facts_local_batch_id"), table_name="cloud_inventory_movement_facts")
    op.drop_index(op.f("ix_cloud_inventory_movement_facts_local_product_id"), table_name="cloud_inventory_movement_facts")
    op.drop_index(op.f("ix_cloud_inventory_movement_facts_event_type"), table_name="cloud_inventory_movement_facts")
    op.drop_index(op.f("ix_cloud_inventory_movement_facts_source_device_id"), table_name="cloud_inventory_movement_facts")
    op.drop_index(op.f("ix_cloud_inventory_movement_facts_branch_id"), table_name="cloud_inventory_movement_facts")
    op.drop_index(op.f("ix_cloud_inventory_movement_facts_organization_id"), table_name="cloud_inventory_movement_facts")
    op.drop_index(op.f("ix_cloud_inventory_movement_facts_source_event_id"), table_name="cloud_inventory_movement_facts")
    op.drop_index(op.f("ix_cloud_inventory_movement_facts_id"), table_name="cloud_inventory_movement_facts")
    op.drop_table("cloud_inventory_movement_facts")

    op.drop_index(op.f("ix_cloud_sale_facts_invoice_number"), table_name="cloud_sale_facts")
    op.drop_index(op.f("ix_cloud_sale_facts_local_sale_id"), table_name="cloud_sale_facts")
    op.drop_index(op.f("ix_cloud_sale_facts_source_device_id"), table_name="cloud_sale_facts")
    op.drop_index(op.f("ix_cloud_sale_facts_branch_id"), table_name="cloud_sale_facts")
    op.drop_index(op.f("ix_cloud_sale_facts_organization_id"), table_name="cloud_sale_facts")
    op.drop_index(op.f("ix_cloud_sale_facts_source_event_id"), table_name="cloud_sale_facts")
    op.drop_index(op.f("ix_cloud_sale_facts_id"), table_name="cloud_sale_facts")
    op.drop_table("cloud_sale_facts")

    with op.batch_alter_table("ingested_sync_events") as batch_op:
        batch_op.drop_column("projection_error")
        batch_op.drop_column("projected_at")
