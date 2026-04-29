"""add sync ingestion

Revision ID: 8c9d0e1f2a33
Revises: 7b8c9d0e1f22
Create Date: 2026-04-29 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8c9d0e1f2a33"
down_revision: Union[str, None] = "7b8c9d0e1f22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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

    if dialect_name == "postgresql":
        event_type_column = sa.Enum(*SYNC_EVENT_TYPE_VALUES, name="synceventtype", create_type=False)
    else:
        event_type_column = sa.String(length=50)

    op.create_table(
        "ingested_sync_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("source_device_id", sa.Integer(), nullable=False),
        sa.Column("local_sequence_number", sa.Integer(), nullable=False),
        sa.Column("event_type", event_type_column, nullable=False),
        sa.Column("aggregate_type", sa.String(length=50), nullable=False),
        sa.Column("aggregate_id", sa.Integer(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("last_duplicate_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingest_error", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["source_device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_device_id", "local_sequence_number", name="uq_ingested_sync_events_device_sequence"),
    )
    op.create_index(op.f("ix_ingested_sync_events_id"), "ingested_sync_events", ["id"], unique=False)
    op.create_index(op.f("ix_ingested_sync_events_event_id"), "ingested_sync_events", ["event_id"], unique=True)
    op.create_index(op.f("ix_ingested_sync_events_organization_id"), "ingested_sync_events", ["organization_id"], unique=False)
    op.create_index(op.f("ix_ingested_sync_events_branch_id"), "ingested_sync_events", ["branch_id"], unique=False)
    op.create_index(op.f("ix_ingested_sync_events_source_device_id"), "ingested_sync_events", ["source_device_id"], unique=False)
    op.create_index(op.f("ix_ingested_sync_events_local_sequence_number"), "ingested_sync_events", ["local_sequence_number"], unique=False)
    op.create_index(op.f("ix_ingested_sync_events_event_type"), "ingested_sync_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_ingested_sync_events_aggregate_type"), "ingested_sync_events", ["aggregate_type"], unique=False)
    op.create_index(op.f("ix_ingested_sync_events_aggregate_id"), "ingested_sync_events", ["aggregate_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ingested_sync_events_aggregate_id"), table_name="ingested_sync_events")
    op.drop_index(op.f("ix_ingested_sync_events_aggregate_type"), table_name="ingested_sync_events")
    op.drop_index(op.f("ix_ingested_sync_events_event_type"), table_name="ingested_sync_events")
    op.drop_index(op.f("ix_ingested_sync_events_local_sequence_number"), table_name="ingested_sync_events")
    op.drop_index(op.f("ix_ingested_sync_events_source_device_id"), table_name="ingested_sync_events")
    op.drop_index(op.f("ix_ingested_sync_events_branch_id"), table_name="ingested_sync_events")
    op.drop_index(op.f("ix_ingested_sync_events_organization_id"), table_name="ingested_sync_events")
    op.drop_index(op.f("ix_ingested_sync_events_event_id"), table_name="ingested_sync_events")
    op.drop_index(op.f("ix_ingested_sync_events_id"), table_name="ingested_sync_events")
    op.drop_table("ingested_sync_events")
