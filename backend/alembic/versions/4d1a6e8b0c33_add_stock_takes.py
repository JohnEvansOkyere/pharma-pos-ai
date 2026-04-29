"""add stock takes

Revision ID: 4d1a6e8b0c33
Revises: 3c9d8b1f5a22
Create Date: 2026-04-29 00:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4d1a6e8b0c33"
down_revision: Union[str, None] = "3c9d8b1f5a22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


STOCK_TAKE_STATUS_VALUES = ("DRAFT", "COMPLETED", "CANCELLED")


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    status_enum = sa.Enum(*STOCK_TAKE_STATUS_VALUES, name="stocktakestatus")
    if dialect_name == "postgresql":
        status_enum.create(bind, checkfirst=True)
        status_column = status_enum
    else:
        status_column = sa.String(length=20)

    op.create_table(
        "stock_takes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(length=50), nullable=False),
        sa.Column("status", status_column, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("completed_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["completed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stock_takes_id"), "stock_takes", ["id"], unique=False)
    op.create_index(op.f("ix_stock_takes_reference"), "stock_takes", ["reference"], unique=True)
    op.create_index(op.f("ix_stock_takes_status"), "stock_takes", ["status"], unique=False)
    op.create_index(op.f("ix_stock_takes_created_by"), "stock_takes", ["created_by"], unique=False)
    op.create_index(op.f("ix_stock_takes_completed_by"), "stock_takes", ["completed_by"], unique=False)

    op.create_table(
        "stock_take_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_take_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("expected_quantity", sa.Integer(), nullable=False),
        sa.Column("counted_quantity", sa.Integer(), nullable=False),
        sa.Column("variance_quantity", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["product_batches.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["stock_take_id"], ["stock_takes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stock_take_items_id"), "stock_take_items", ["id"], unique=False)
    op.create_index(op.f("ix_stock_take_items_stock_take_id"), "stock_take_items", ["stock_take_id"], unique=False)
    op.create_index(op.f("ix_stock_take_items_product_id"), "stock_take_items", ["product_id"], unique=False)
    op.create_index(op.f("ix_stock_take_items_batch_id"), "stock_take_items", ["batch_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    op.drop_index(op.f("ix_stock_take_items_batch_id"), table_name="stock_take_items")
    op.drop_index(op.f("ix_stock_take_items_product_id"), table_name="stock_take_items")
    op.drop_index(op.f("ix_stock_take_items_stock_take_id"), table_name="stock_take_items")
    op.drop_index(op.f("ix_stock_take_items_id"), table_name="stock_take_items")
    op.drop_table("stock_take_items")

    op.drop_index(op.f("ix_stock_takes_completed_by"), table_name="stock_takes")
    op.drop_index(op.f("ix_stock_takes_created_by"), table_name="stock_takes")
    op.drop_index(op.f("ix_stock_takes_status"), table_name="stock_takes")
    op.drop_index(op.f("ix_stock_takes_reference"), table_name="stock_takes")
    op.drop_index(op.f("ix_stock_takes_id"), table_name="stock_takes")
    op.drop_table("stock_takes")

    if dialect_name == "postgresql":
        status_enum = sa.Enum(*STOCK_TAKE_STATUS_VALUES, name="stocktakestatus")
        status_enum.drop(bind, checkfirst=True)
