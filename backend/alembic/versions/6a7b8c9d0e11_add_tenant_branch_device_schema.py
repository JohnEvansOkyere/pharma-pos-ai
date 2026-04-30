"""add tenant branch device schema

Revision ID: 6a7b8c9d0e11
Revises: 5e2f7c9a1b44
Create Date: 2026-04-29 00:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "6a7b8c9d0e11"
down_revision: Union[str, None] = "5e2f7c9a1b44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEVICE_STATUS_VALUES = ("ACTIVE", "DISABLED", "RETIRED")


TABLE_TENANT_COLUMNS = {
    "users": ("organization_id", "branch_id"),
    "products": ("organization_id", "branch_id"),
    "product_batches": ("organization_id", "branch_id"),
    "sales": ("organization_id", "branch_id", "source_device_id"),
    "sale_items": ("organization_id", "branch_id"),
    "sale_reversals": ("organization_id", "branch_id"),
    "stock_adjustments": ("organization_id", "branch_id", "source_device_id"),
    "activity_logs": ("organization_id", "branch_id", "source_device_id"),
    "inventory_movements": ("organization_id", "branch_id", "source_device_id"),
    "stock_takes": ("organization_id", "branch_id", "source_device_id"),
    "stock_take_items": ("organization_id", "branch_id"),
}


def _add_nullable_fk(table_name: str, column_name: str, target_table: str) -> None:
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.add_column(sa.Column(column_name, sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            f"fk_{table_name}_{column_name}_{target_table}",
            target_table,
            [column_name],
            ["id"],
        )
        batch_op.create_index(f"ix_{table_name}_{column_name}", [column_name])


def _drop_nullable_fk(table_name: str, column_name: str, target_table: str) -> None:
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.drop_index(f"ix_{table_name}_{column_name}")
        batch_op.drop_constraint(f"fk_{table_name}_{column_name}_{target_table}", type_="foreignkey")
        batch_op.drop_column(column_name)


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    device_status_enum = sa.Enum(*DEVICE_STATUS_VALUES, name="devicestatus")
    if dialect_name == "postgresql":
        device_status_enum.create(bind, checkfirst=True)
        device_status_column = postgresql.ENUM(
            *DEVICE_STATUS_VALUES,
            name="devicestatus",
            create_type=False,
        )
    else:
        device_status_column = sa.String(length=20)

    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("legal_name", sa.String(length=200), nullable=True),
        sa.Column("contact_phone", sa.String(length=20), nullable=True),
        sa.Column("contact_email", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_organizations_id"), "organizations", ["id"], unique=False)
    op.create_index(op.f("ix_organizations_name"), "organizations", ["name"], unique=False)

    op.create_table(
        "branches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_branches_org_code"),
    )
    op.create_index(op.f("ix_branches_id"), "branches", ["id"], unique=False)
    op.create_index(op.f("ix_branches_organization_id"), "branches", ["organization_id"], unique=False)
    op.create_index(op.f("ix_branches_name"), "branches", ["name"], unique=False)
    op.create_index(op.f("ix_branches_code"), "branches", ["code"], unique=False)

    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("device_uid", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", device_status_column, nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_devices_id"), "devices", ["id"], unique=False)
    op.create_index(op.f("ix_devices_organization_id"), "devices", ["organization_id"], unique=False)
    op.create_index(op.f("ix_devices_branch_id"), "devices", ["branch_id"], unique=False)
    op.create_index(op.f("ix_devices_device_uid"), "devices", ["device_uid"], unique=True)
    op.create_index(op.f("ix_devices_status"), "devices", ["status"], unique=False)

    for table_name, columns in TABLE_TENANT_COLUMNS.items():
        for column_name in columns:
            if column_name == "organization_id":
                _add_nullable_fk(table_name, column_name, "organizations")
            elif column_name == "branch_id":
                _add_nullable_fk(table_name, column_name, "branches")
            elif column_name == "source_device_id":
                _add_nullable_fk(table_name, column_name, "devices")


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    for table_name, columns in reversed(TABLE_TENANT_COLUMNS.items()):
        for column_name in reversed(columns):
            if column_name == "organization_id":
                _drop_nullable_fk(table_name, column_name, "organizations")
            elif column_name == "branch_id":
                _drop_nullable_fk(table_name, column_name, "branches")
            elif column_name == "source_device_id":
                _drop_nullable_fk(table_name, column_name, "devices")

    op.drop_index(op.f("ix_devices_status"), table_name="devices")
    op.drop_index(op.f("ix_devices_device_uid"), table_name="devices")
    op.drop_index(op.f("ix_devices_branch_id"), table_name="devices")
    op.drop_index(op.f("ix_devices_organization_id"), table_name="devices")
    op.drop_index(op.f("ix_devices_id"), table_name="devices")
    op.drop_table("devices")

    op.drop_index(op.f("ix_branches_code"), table_name="branches")
    op.drop_index(op.f("ix_branches_name"), table_name="branches")
    op.drop_index(op.f("ix_branches_organization_id"), table_name="branches")
    op.drop_index(op.f("ix_branches_id"), table_name="branches")
    op.drop_table("branches")

    op.drop_index(op.f("ix_organizations_name"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_id"), table_name="organizations")
    op.drop_table("organizations")

    if dialect_name == "postgresql":
        device_status_enum = sa.Enum(*DEVICE_STATUS_VALUES, name="devicestatus")
        device_status_enum.drop(bind, checkfirst=True)
