"""add batch support to stock adjustments

Revision ID: 1a4a4f3b1f20
Revises: fb40d0b95eb6
Create Date: 2026-04-07 15:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a4a4f3b1f20'
down_revision: Union[str, None] = 'fb40d0b95eb6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('stock_adjustments', sa.Column('batch_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_stock_adjustments_batch_id_product_batches',
        'stock_adjustments',
        'product_batches',
        ['batch_id'],
        ['id'],
    )
    op.execute("ALTER TYPE adjustmenttype ADD VALUE IF NOT EXISTS 'EXPIRED'")


def downgrade() -> None:
    op.drop_constraint(
        'fk_stock_adjustments_batch_id_product_batches',
        'stock_adjustments',
        type_='foreignkey',
    )
    op.drop_column('stock_adjustments', 'batch_id')
