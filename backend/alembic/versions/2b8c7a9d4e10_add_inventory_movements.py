"""add inventory movements

Revision ID: 2b8c7a9d4e10
Revises: 9f0d7e6a2c11
Create Date: 2026-04-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2b8c7a9d4e10"
down_revision: Union[str, None] = "9f0d7e6a2c11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MOVEMENT_TYPE_VALUES = (
    "STOCK_RECEIVED",
    "INITIAL_BATCH_STOCK",
    "SALE_DISPENSED",
    "SALE_REVERSED",
    "STOCK_ADJUSTMENT_POSITIVE",
    "STOCK_ADJUSTMENT_NEGATIVE",
    "STOCK_CORRECTION",
    "EXPIRY_WRITE_OFF",
    "DAMAGE_WRITE_OFF",
    "RETURNED_TO_STOCK",
)


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    movement_type_enum = sa.Enum(*MOVEMENT_TYPE_VALUES, name="inventorymovementtype")
    if dialect_name == "postgresql":
        movement_type_enum.create(bind, checkfirst=True)
        movement_type_column = movement_type_enum
    else:
        movement_type_column = sa.String(length=40)

    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=True),
        sa.Column("movement_type", movement_type_column, nullable=False),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column("stock_after", sa.Integer(), nullable=True),
        sa.Column("source_document_type", sa.String(length=50), nullable=False),
        sa.Column("source_document_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["product_batches.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inventory_movements_id"), "inventory_movements", ["id"], unique=False)
    op.create_index(op.f("ix_inventory_movements_product_id"), "inventory_movements", ["product_id"], unique=False)
    op.create_index(op.f("ix_inventory_movements_batch_id"), "inventory_movements", ["batch_id"], unique=False)
    op.create_index(op.f("ix_inventory_movements_movement_type"), "inventory_movements", ["movement_type"], unique=False)
    op.create_index(
        op.f("ix_inventory_movements_source_document_type"),
        "inventory_movements",
        ["source_document_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_inventory_movements_source_document_id"),
        "inventory_movements",
        ["source_document_id"],
        unique=False,
    )
    op.create_index(op.f("ix_inventory_movements_created_by"), "inventory_movements", ["created_by"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    op.drop_index(op.f("ix_inventory_movements_created_by"), table_name="inventory_movements")
    op.drop_index(op.f("ix_inventory_movements_source_document_id"), table_name="inventory_movements")
    op.drop_index(op.f("ix_inventory_movements_source_document_type"), table_name="inventory_movements")
    op.drop_index(op.f("ix_inventory_movements_movement_type"), table_name="inventory_movements")
    op.drop_index(op.f("ix_inventory_movements_batch_id"), table_name="inventory_movements")
    op.drop_index(op.f("ix_inventory_movements_product_id"), table_name="inventory_movements")
    op.drop_index(op.f("ix_inventory_movements_id"), table_name="inventory_movements")
    op.drop_table("inventory_movements")

    if dialect_name == "postgresql":
        movement_type_enum = sa.Enum(*MOVEMENT_TYPE_VALUES, name="inventorymovementtype")
        movement_type_enum.drop(bind, checkfirst=True)
