"""add sale reversals

Revision ID: 3c9d8b1f5a22
Revises: 2b8c7a9d4e10
Create Date: 2026-04-29 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3c9d8b1f5a22"
down_revision: Union[str, None] = "2b8c7a9d4e10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


REVERSAL_TYPE_VALUES = ("VOID", "REFUND")


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    reversal_type_enum = sa.Enum(*REVERSAL_TYPE_VALUES, name="salereversaltype")
    if dialect_name == "postgresql":
        reversal_type_enum.create(bind, checkfirst=True)
        reversal_type_column = reversal_type_enum
    else:
        reversal_type_column = sa.String(length=20)

    op.create_table(
        "sale_reversals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sale_id", sa.Integer(), nullable=False),
        sa.Column("reversal_type", reversal_type_column, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("restored_quantity", sa.Integer(), nullable=False),
        sa.Column("performed_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["performed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sale_reversals_id"), "sale_reversals", ["id"], unique=False)
    op.create_index(op.f("ix_sale_reversals_sale_id"), "sale_reversals", ["sale_id"], unique=False)
    op.create_index(op.f("ix_sale_reversals_reversal_type"), "sale_reversals", ["reversal_type"], unique=False)
    op.create_index(op.f("ix_sale_reversals_performed_by"), "sale_reversals", ["performed_by"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    op.drop_index(op.f("ix_sale_reversals_performed_by"), table_name="sale_reversals")
    op.drop_index(op.f("ix_sale_reversals_reversal_type"), table_name="sale_reversals")
    op.drop_index(op.f("ix_sale_reversals_sale_id"), table_name="sale_reversals")
    op.drop_index(op.f("ix_sale_reversals_id"), table_name="sale_reversals")
    op.drop_table("sale_reversals")

    if dialect_name == "postgresql":
        reversal_type_enum = sa.Enum(*REVERSAL_TYPE_VALUES, name="salereversaltype")
        reversal_type_enum.drop(bind, checkfirst=True)
