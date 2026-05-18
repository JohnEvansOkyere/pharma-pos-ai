"""merge_token_hash_and_restore_drill_branches

Revision ID: 650dc9d5a2f1
Revises: b1c2d3e4f5a6, i9d0e1f2a3b4
Create Date: 2026-05-18 21:19:48.867481

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '650dc9d5a2f1'
down_revision: Union[str, None] = ('b1c2d3e4f5a6', 'i9d0e1f2a3b4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
