"""convert money columns to numeric

Revision ID: 54f6c3e7c2d1
Revises: 1a4a4f3b1f20
Create Date: 2026-04-09 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "54f6c3e7c2d1"
down_revision: Union[str, None] = "1a4a4f3b1f20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MONEY_TYPE = sa.Numeric(12, 2)
FLOAT_TYPE = sa.Float()


def upgrade() -> None:
    with op.batch_alter_table("products") as batch_op:
        batch_op.alter_column("cost_price", existing_type=FLOAT_TYPE, type_=MONEY_TYPE, existing_nullable=False)
        batch_op.alter_column("selling_price", existing_type=FLOAT_TYPE, type_=MONEY_TYPE, existing_nullable=False)
        batch_op.alter_column("wholesale_price", existing_type=FLOAT_TYPE, type_=MONEY_TYPE, existing_nullable=True)
        batch_op.alter_column("mrp", existing_type=FLOAT_TYPE, type_=MONEY_TYPE, existing_nullable=True)

    with op.batch_alter_table("product_batches") as batch_op:
        batch_op.alter_column("cost_price", existing_type=FLOAT_TYPE, type_=MONEY_TYPE, existing_nullable=False)

    with op.batch_alter_table("sales") as batch_op:
        batch_op.alter_column("subtotal", existing_type=FLOAT_TYPE, type_=MONEY_TYPE, existing_nullable=False)
        batch_op.alter_column("discount_amount", existing_type=FLOAT_TYPE, type_=MONEY_TYPE, existing_nullable=False)
        batch_op.alter_column("tax_amount", existing_type=FLOAT_TYPE, type_=MONEY_TYPE, existing_nullable=False)
        batch_op.alter_column("total_amount", existing_type=FLOAT_TYPE, type_=MONEY_TYPE, existing_nullable=False)
        batch_op.alter_column("amount_paid", existing_type=FLOAT_TYPE, type_=MONEY_TYPE, existing_nullable=False)
        batch_op.alter_column("change_amount", existing_type=FLOAT_TYPE, type_=MONEY_TYPE, existing_nullable=False)
        batch_op.alter_column("insurance_coverage", existing_type=FLOAT_TYPE, type_=MONEY_TYPE, existing_nullable=True)

    with op.batch_alter_table("sale_items") as batch_op:
        batch_op.alter_column("unit_price", existing_type=FLOAT_TYPE, type_=MONEY_TYPE, existing_nullable=False)
        batch_op.alter_column("discount_amount", existing_type=FLOAT_TYPE, type_=MONEY_TYPE, existing_nullable=False)
        batch_op.alter_column("total_price", existing_type=FLOAT_TYPE, type_=MONEY_TYPE, existing_nullable=False)
        batch_op.alter_column("tax_amount", existing_type=FLOAT_TYPE, type_=MONEY_TYPE, existing_nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("sale_items") as batch_op:
        batch_op.alter_column("unit_price", existing_type=MONEY_TYPE, type_=FLOAT_TYPE, existing_nullable=False)
        batch_op.alter_column("discount_amount", existing_type=MONEY_TYPE, type_=FLOAT_TYPE, existing_nullable=False)
        batch_op.alter_column("total_price", existing_type=MONEY_TYPE, type_=FLOAT_TYPE, existing_nullable=False)
        batch_op.alter_column("tax_amount", existing_type=MONEY_TYPE, type_=FLOAT_TYPE, existing_nullable=True)

    with op.batch_alter_table("sales") as batch_op:
        batch_op.alter_column("subtotal", existing_type=MONEY_TYPE, type_=FLOAT_TYPE, existing_nullable=False)
        batch_op.alter_column("discount_amount", existing_type=MONEY_TYPE, type_=FLOAT_TYPE, existing_nullable=False)
        batch_op.alter_column("tax_amount", existing_type=MONEY_TYPE, type_=FLOAT_TYPE, existing_nullable=False)
        batch_op.alter_column("total_amount", existing_type=MONEY_TYPE, type_=FLOAT_TYPE, existing_nullable=False)
        batch_op.alter_column("amount_paid", existing_type=MONEY_TYPE, type_=FLOAT_TYPE, existing_nullable=False)
        batch_op.alter_column("change_amount", existing_type=MONEY_TYPE, type_=FLOAT_TYPE, existing_nullable=False)
        batch_op.alter_column("insurance_coverage", existing_type=MONEY_TYPE, type_=FLOAT_TYPE, existing_nullable=True)

    with op.batch_alter_table("product_batches") as batch_op:
        batch_op.alter_column("cost_price", existing_type=MONEY_TYPE, type_=FLOAT_TYPE, existing_nullable=False)

    with op.batch_alter_table("products") as batch_op:
        batch_op.alter_column("cost_price", existing_type=MONEY_TYPE, type_=FLOAT_TYPE, existing_nullable=False)
        batch_op.alter_column("selling_price", existing_type=MONEY_TYPE, type_=FLOAT_TYPE, existing_nullable=False)
        batch_op.alter_column("wholesale_price", existing_type=MONEY_TYPE, type_=FLOAT_TYPE, existing_nullable=True)
        batch_op.alter_column("mrp", existing_type=MONEY_TYPE, type_=FLOAT_TYPE, existing_nullable=True)
