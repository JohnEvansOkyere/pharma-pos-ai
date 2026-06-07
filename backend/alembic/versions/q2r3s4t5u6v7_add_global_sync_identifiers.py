"""add global sync identifiers

Revision ID: q2r3s4t5u6v7
Revises: p1q2r3s4t5u6
Create Date: 2026-06-07
"""
from typing import Sequence, Union
from uuid import UUID, uuid5

from alembic import op
import sqlalchemy as sa


revision: str = "q2r3s4t5u6v7"
down_revision: Union[str, None] = "p1q2r3s4t5u6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GLOBAL_ID_NAMESPACE = UUID("66cc8c97-b21e-4a6a-b5c8-09fa3a52ca45")


def _organization_uid(organization_id: int) -> str:
    return str(uuid5(GLOBAL_ID_NAMESPACE, f"organization:{organization_id}"))


def _branch_uid(organization_id: int, branch_id: int) -> str:
    return str(
        uuid5(
            GLOBAL_ID_NAMESPACE,
            f"organization:{organization_id}:branch:{branch_id}",
        )
    )


def _deployment_uid(device_uid: str) -> str:
    return str(uuid5(GLOBAL_ID_NAMESPACE, f"device:{device_uid}:deployment"))


def _aggregate_uid(
    deployment_uid: str,
    aggregate_type: str,
    aggregate_id: int | None,
) -> str | None:
    if aggregate_id is None:
        return None
    return str(uuid5(UUID(deployment_uid), f"{aggregate_type}:{aggregate_id}"))


def _backfill_postgresql(bind) -> None:
    """Backfill UUID identity in set-based PostgreSQL statements."""
    bind.execute(sa.text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
    bind.execute(
        sa.text(
            """
            UPDATE organizations
            SET organization_uid = uuid_generate_v5(
                CAST(:namespace AS uuid),
                concat('organization', chr(58), id::text)
            )::text
            """
        ),
        {"namespace": str(GLOBAL_ID_NAMESPACE)},
    )
    bind.execute(
        sa.text(
            """
            UPDATE branches
            SET branch_uid = uuid_generate_v5(
                CAST(:namespace AS uuid),
                concat(
                    'organization',
                    chr(58),
                    organization_id::text,
                    chr(58),
                    'branch',
                    chr(58),
                    id::text
                )
            )::text
            """
        ),
        {"namespace": str(GLOBAL_ID_NAMESPACE)},
    )
    bind.execute(
        sa.text(
            """
            UPDATE devices
            SET deployment_uid = uuid_generate_v5(
                CAST(:namespace AS uuid),
                concat(
                    'device',
                    chr(58),
                    device_uid,
                    chr(58),
                    'deployment'
                )
            )::text
            """
        ),
        {"namespace": str(GLOBAL_ID_NAMESPACE)},
    )
    bind.execute(
        sa.text(
            """
            UPDATE ingested_sync_events AS event
            SET deployment_uid = device.deployment_uid,
                aggregate_uid = CASE
                    WHEN event.aggregate_id IS NULL THEN NULL
                    ELSE uuid_generate_v5(
                        CAST(device.deployment_uid AS uuid),
                        concat(
                            event.aggregate_type,
                            chr(58),
                            event.aggregate_id::text
                        )
                    )::text
                END
            FROM devices AS device
            WHERE device.id = event.source_device_id
            """
        )
    )


def _backfill_compatibility_dialect(bind) -> None:
    """Retain deterministic compatibility for non-PostgreSQL migration tests."""
    for row in bind.execute(sa.text("SELECT id FROM organizations")).mappings():
        bind.execute(
            sa.text(
                "UPDATE organizations SET organization_uid = :uid WHERE id = :id"
            ),
            {"uid": _organization_uid(row["id"]), "id": row["id"]},
        )

    for row in bind.execute(
        sa.text("SELECT id, organization_id FROM branches")
    ).mappings():
        bind.execute(
            sa.text("UPDATE branches SET branch_uid = :uid WHERE id = :id"),
            {
                "uid": _branch_uid(row["organization_id"], row["id"]),
                "id": row["id"],
            },
        )

    for row in bind.execute(
        sa.text("SELECT id, device_uid FROM devices")
    ).mappings():
        bind.execute(
            sa.text("UPDATE devices SET deployment_uid = :uid WHERE id = :id"),
            {"uid": _deployment_uid(row["device_uid"]), "id": row["id"]},
        )

    ingested_rows = bind.execute(
        sa.text(
            """
            SELECT event.id, event.aggregate_type, event.aggregate_id,
                   device.deployment_uid
            FROM ingested_sync_events AS event
            JOIN devices AS device ON device.id = event.source_device_id
            """
        )
    ).mappings()
    for row in ingested_rows:
        bind.execute(
            sa.text(
                """
                UPDATE ingested_sync_events
                SET deployment_uid = :deployment_uid,
                    aggregate_uid = :aggregate_uid
                WHERE id = :id
                """
            ),
            {
                "deployment_uid": row["deployment_uid"],
                "aggregate_uid": _aggregate_uid(
                    row["deployment_uid"],
                    row["aggregate_type"],
                    row["aggregate_id"],
                ),
                "id": row["id"],
            },
        )


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("organization_uid", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "branches",
        sa.Column("branch_uid", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "devices",
        sa.Column("deployment_uid", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "ingested_sync_events",
        sa.Column("deployment_uid", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "ingested_sync_events",
        sa.Column("aggregate_uid", sa.String(length=36), nullable=True),
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        _backfill_postgresql(bind)
    else:
        _backfill_compatibility_dialect(bind)

    op.alter_column("organizations", "organization_uid", nullable=False)
    op.alter_column("branches", "branch_uid", nullable=False)
    op.alter_column("devices", "deployment_uid", nullable=False)
    op.alter_column("ingested_sync_events", "deployment_uid", nullable=False)

    op.create_index(
        "ix_organizations_organization_uid",
        "organizations",
        ["organization_uid"],
        unique=True,
    )
    op.create_index(
        "ix_branches_branch_uid",
        "branches",
        ["branch_uid"],
        unique=True,
    )
    op.create_index(
        "ix_devices_deployment_uid",
        "devices",
        ["deployment_uid"],
        unique=False,
    )
    op.create_index(
        "ix_ingested_sync_events_deployment_uid",
        "ingested_sync_events",
        ["deployment_uid"],
        unique=False,
    )
    op.create_index(
        "ix_ingested_sync_events_aggregate_uid",
        "ingested_sync_events",
        ["aggregate_uid"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ingested_sync_events_aggregate_uid",
        table_name="ingested_sync_events",
    )
    op.drop_index(
        "ix_ingested_sync_events_deployment_uid",
        table_name="ingested_sync_events",
    )
    op.drop_index("ix_devices_deployment_uid", table_name="devices")
    op.drop_index("ix_branches_branch_uid", table_name="branches")
    op.drop_index("ix_organizations_organization_uid", table_name="organizations")
    op.drop_column("ingested_sync_events", "aggregate_uid")
    op.drop_column("ingested_sync_events", "deployment_uid")
    op.drop_column("devices", "deployment_uid")
    op.drop_column("branches", "branch_uid")
    op.drop_column("organizations", "organization_uid")
