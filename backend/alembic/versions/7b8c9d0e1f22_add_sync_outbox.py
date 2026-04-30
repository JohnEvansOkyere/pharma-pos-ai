"""add sync outbox

Revision ID: 7b8c9d0e1f22
Revises: 6a7b8c9d0e11
Create Date: 2026-04-29 00:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "7b8c9d0e1f22"
down_revision: Union[str, None] = "6a7b8c9d0e11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SYNC_EVENT_STATUS_VALUES = ("PENDING", "SENDING", "SENT", "FAILED")
SYNC_EVENT_TYPE_VALUES = (
    "SALE_CREATED",
    "SALE_REVERSED",
    "STOCK_RECEIVED",
    "STOCK_ADJUSTED",
    "STOCK_TAKE_CREATED",
    "STOCK_TAKE_COMPLETED",
    "PRODUCT_CREATED",
    "PRODUCT_UPDATED",
    "PRODUCT_DEACTIVATED",
    "PRODUCT_BATCH_CREATED",
    "PRODUCT_BATCH_UPDATED",
    "USER_CREATED",
    "USER_UPDATED",
    "USER_DELETED",
    "CATEGORY_CREATED",
    "CATEGORY_UPDATED",
    "CATEGORY_DELETED",
    "SUPPLIER_CREATED",
    "SUPPLIER_UPDATED",
    "SUPPLIER_DELETED",
)


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    status_enum = sa.Enum(*SYNC_EVENT_STATUS_VALUES, name="synceventstatus")
    event_type_enum = sa.Enum(*SYNC_EVENT_TYPE_VALUES, name="synceventtype")
    if dialect_name == "postgresql":
        status_enum.create(bind, checkfirst=True)
        event_type_enum.create(bind, checkfirst=True)
        status_column = postgresql.ENUM(
            *SYNC_EVENT_STATUS_VALUES,
            name="synceventstatus",
            create_type=False,
        )
        event_type_column = postgresql.ENUM(
            *SYNC_EVENT_TYPE_VALUES,
            name="synceventtype",
            create_type=False,
        )
    else:
        status_column = sa.String(length=20)
        event_type_column = sa.String(length=50)

    op.create_table(
        "sync_event_counters",
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("next_value", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )

    op.create_table(
        "sync_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("source_device_id", sa.Integer(), nullable=True),
        sa.Column("local_sequence_number", sa.Integer(), nullable=False),
        sa.Column("event_type", event_type_column, nullable=False),
        sa.Column("aggregate_type", sa.String(length=50), nullable=False),
        sa.Column("aggregate_id", sa.Integer(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("status", status_column, nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["source_device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sync_events_id"), "sync_events", ["id"], unique=False)
    op.create_index(op.f("ix_sync_events_event_id"), "sync_events", ["event_id"], unique=True)
    op.create_index(op.f("ix_sync_events_organization_id"), "sync_events", ["organization_id"], unique=False)
    op.create_index(op.f("ix_sync_events_branch_id"), "sync_events", ["branch_id"], unique=False)
    op.create_index(op.f("ix_sync_events_source_device_id"), "sync_events", ["source_device_id"], unique=False)
    op.create_index(op.f("ix_sync_events_local_sequence_number"), "sync_events", ["local_sequence_number"], unique=True)
    op.create_index(op.f("ix_sync_events_event_type"), "sync_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_sync_events_aggregate_type"), "sync_events", ["aggregate_type"], unique=False)
    op.create_index(op.f("ix_sync_events_aggregate_id"), "sync_events", ["aggregate_id"], unique=False)
    op.create_index(op.f("ix_sync_events_status"), "sync_events", ["status"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    op.drop_index(op.f("ix_sync_events_status"), table_name="sync_events")
    op.drop_index(op.f("ix_sync_events_aggregate_id"), table_name="sync_events")
    op.drop_index(op.f("ix_sync_events_aggregate_type"), table_name="sync_events")
    op.drop_index(op.f("ix_sync_events_event_type"), table_name="sync_events")
    op.drop_index(op.f("ix_sync_events_local_sequence_number"), table_name="sync_events")
    op.drop_index(op.f("ix_sync_events_source_device_id"), table_name="sync_events")
    op.drop_index(op.f("ix_sync_events_branch_id"), table_name="sync_events")
    op.drop_index(op.f("ix_sync_events_organization_id"), table_name="sync_events")
    op.drop_index(op.f("ix_sync_events_event_id"), table_name="sync_events")
    op.drop_index(op.f("ix_sync_events_id"), table_name="sync_events")
    op.drop_table("sync_events")
    op.drop_table("sync_event_counters")

    if dialect_name == "postgresql":
        event_type_enum = sa.Enum(*SYNC_EVENT_TYPE_VALUES, name="synceventtype")
        status_enum = sa.Enum(*SYNC_EVENT_STATUS_VALUES, name="synceventstatus")
        event_type_enum.drop(bind, checkfirst=True)
        status_enum.drop(bind, checkfirst=True)
