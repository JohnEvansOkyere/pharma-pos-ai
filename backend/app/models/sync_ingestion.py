"""
Cloud-side sync ingestion records.
"""
from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base import Base
from app.models.sync_event import SyncEventType


class IngestedSyncEvent(Base):
    """Idempotent record of a branch event accepted by the cloud API."""

    __tablename__ = "ingested_sync_events"
    __table_args__ = (
        UniqueConstraint(
            "source_device_id",
            "local_sequence_number",
            name="uq_ingested_sync_events_device_sequence",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(36), unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    source_device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    local_sequence_number = Column(Integer, nullable=False, index=True)
    event_type = Column(SQLEnum(SyncEventType), nullable=False, index=True)
    aggregate_type = Column(String(50), nullable=False, index=True)
    aggregate_id = Column(Integer, nullable=True, index=True)
    schema_version = Column(Integer, nullable=False)
    payload = Column(JSON, nullable=False)
    payload_hash = Column(String(64), nullable=False)
    duplicate_count = Column(Integer, default=0, nullable=False)
    last_duplicate_at = Column(DateTime(timezone=True))
    ingest_error = Column(Text)
    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<IngestedSyncEvent(id={self.id}, event_id='{self.event_id}')>"
