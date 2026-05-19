"""add cloud device heartbeat snapshots

Revision ID: l2a3b4c5d6e7
Revises: k1f2a3b4c5d6
Create Date: 2026-05-19 03:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "l2a3b4c5d6e7"
down_revision = "k1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE synceventtype ADD VALUE IF NOT EXISTS 'SYSTEM_HEARTBEAT'")

    op.create_table(
        "cloud_device_heartbeat_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("source_device_id", sa.Integer(), nullable=False),
        sa.Column("device_uid", sa.String(length=100), nullable=False),
        sa.Column("readiness_status", sa.String(length=20), nullable=False),
        sa.Column("app_version", sa.String(length=50), nullable=True),
        sa.Column("environment", sa.String(length=50), nullable=True),
        sa.Column("database_connected", sa.Boolean(), nullable=False),
        sa.Column("scheduler_enabled", sa.Boolean(), nullable=False),
        sa.Column("scheduler_running", sa.Boolean(), nullable=False),
        sa.Column("scheduler_job_count", sa.Integer(), nullable=False),
        sa.Column("cloud_sync_enabled", sa.Boolean(), nullable=False),
        sa.Column("cloud_sync_configured", sa.Boolean(), nullable=False),
        sa.Column("sync_pending_count", sa.Integer(), nullable=False),
        sa.Column("sync_failed_count", sa.Integer(), nullable=False),
        sa.Column("oldest_unsent_event_age_minutes", sa.Integer(), nullable=True),
        sa.Column("latest_backup_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_backup_age_hours", sa.Integer(), nullable=True),
        sa.Column("backup_is_recent", sa.Boolean(), nullable=False),
        sa.Column("restore_recovery_ready", sa.Boolean(), nullable=False),
        sa.Column("last_restore_drill_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("free_disk_bytes", sa.BigInteger(), nullable=True),
        sa.Column("total_disk_bytes", sa.BigInteger(), nullable=True),
        sa.Column("uptime_seconds", sa.Integer(), nullable=True),
        sa.Column("server_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_source_event_id", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["last_source_event_id"], ["ingested_sync_events.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["source_device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_device_id", name="uq_cloud_device_heartbeat_source_device"),
    )
    op.create_index("ix_cloud_device_heartbeat_snapshots_id", "cloud_device_heartbeat_snapshots", ["id"])
    op.create_index("ix_cloud_device_heartbeat_snapshots_organization_id", "cloud_device_heartbeat_snapshots", ["organization_id"])
    op.create_index("ix_cloud_device_heartbeat_snapshots_branch_id", "cloud_device_heartbeat_snapshots", ["branch_id"])
    op.create_index("ix_cloud_device_heartbeat_snapshots_source_device_id", "cloud_device_heartbeat_snapshots", ["source_device_id"])
    op.create_index("ix_cloud_device_heartbeat_snapshots_device_uid", "cloud_device_heartbeat_snapshots", ["device_uid"])
    op.create_index("ix_cloud_device_heartbeat_snapshots_readiness_status", "cloud_device_heartbeat_snapshots", ["readiness_status"])
    op.create_index("ix_cloud_device_heartbeat_snapshots_server_time", "cloud_device_heartbeat_snapshots", ["server_time"])
    op.create_index("ix_cloud_device_heartbeat_snapshots_last_source_event_id", "cloud_device_heartbeat_snapshots", ["last_source_event_id"])


def downgrade():
    op.drop_table("cloud_device_heartbeat_snapshots")
