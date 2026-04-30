"""add sale pricing mode

Revision ID: 9f0d7e6a2c11
Revises: 54f6c3e7c2d1
Create Date: 2026-04-09 22:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "9f0d7e6a2c11"
down_revision: Union[str, None] = "54f6c3e7c2d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PRICING_MODE_VALUES = ("RETAIL", "WHOLESALE")


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    pricing_mode_enum = sa.Enum(*PRICING_MODE_VALUES, name="salepricingmode")

    if dialect_name == "postgresql":
        pricing_mode_enum.create(bind, checkfirst=True)
        pricing_mode_column = postgresql.ENUM(
            *PRICING_MODE_VALUES,
            name="salepricingmode",
            create_type=False,
        )
        op.add_column(
            "sales",
            sa.Column(
                "pricing_mode",
                pricing_mode_column,
                nullable=False,
                server_default="RETAIL",
            ),
        )
    else:
        with op.batch_alter_table("sales") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "pricing_mode",
                    sa.String(length=20),
                    nullable=False,
                    server_default="RETAIL",
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == "postgresql":
        op.drop_column("sales", "pricing_mode")
        pricing_mode_enum = sa.Enum(*PRICING_MODE_VALUES, name="salepricingmode")
        pricing_mode_enum.drop(bind, checkfirst=True)
    else:
        with op.batch_alter_table("sales") as batch_op:
            batch_op.drop_column("pricing_mode")
