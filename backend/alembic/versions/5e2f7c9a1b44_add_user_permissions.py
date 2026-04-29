"""add user permissions

Revision ID: 5e2f7c9a1b44
Revises: 4d1a6e8b0c33
Create Date: 2026-04-29 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5e2f7c9a1b44"
down_revision: Union[str, None] = "4d1a6e8b0c33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("permissions", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "permissions")
