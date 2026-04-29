"""
Local sync outbox models for hybrid cloud readiness.
"""
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class SyncEventStatus(str, Enum):
    """Delivery state for a local sync event."""

    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"


class SyncEventType(str, Enum):
    """Canonical local business event types for cloud sync."""

    SALE_CREATED = "sale_created"
    SALE_REVERSED = "sale_reversed"
    STOCK_RECEIVED = "stock_received"
    STOCK_ADJUSTED = "stock_adjusted"
    STOCK_TAKE_CREATED = "stock_take_created"
    STOCK_TAKE_COMPLETED = "stock_take_completed"
    PRODUCT_CREATED = "product_created"
    PRODUCT_UPDATED = "product_updated"
    PRODUCT_DEACTIVATED = "product_deactivated"
    PRODUCT_BATCH_CREATED = "product_batch_created"
    PRODUCT_BATCH_UPDATED = "product_batch_updated"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    CATEGORY_CREATED = "category_created"
    CATEGORY_UPDATED = "category_updated"
    CATEGORY_DELETED = "category_deleted"
    SUPPLIER_CREATED = "supplier_created"
    SUPPLIER_UPDATED = "supplier_updated"
    SUPPLIER_DELETED = "supplier_deleted"


class SyncEventCounter(Base):
    """Single-row counters used to allocate durable local sequence numbers."""

    __tablename__ = "sync_event_counters"

    name = Column(String(50), primary_key=True)
    next_value = Column(Integer, nullable=False)


class SyncEvent(Base):
    """Append-only local outbox event."""

    __tablename__ = "sync_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(36), unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)
    source_device_id = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)
    local_sequence_number = Column(Integer, unique=True, nullable=False, index=True)
    event_type = Column(SQLEnum(SyncEventType), nullable=False, index=True)
    aggregate_type = Column(String(50), nullable=False, index=True)
    aggregate_id = Column(Integer, nullable=True, index=True)
    schema_version = Column(Integer, nullable=False, default=1)
    payload = Column(JSON, nullable=False)
    payload_hash = Column(String(64), nullable=False)
    status = Column(SQLEnum(SyncEventStatus), default=SyncEventStatus.PENDING, nullable=False, index=True)
    retry_count = Column(Integer, default=0, nullable=False)
    last_error = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sent_at = Column(DateTime(timezone=True))
    acknowledged_at = Column(DateTime(timezone=True))

    def __repr__(self):
        return (
            f"<SyncEvent(id={self.id}, event_id='{self.event_id}', "
            f"type='{self.event_type}', seq={self.local_sequence_number})>"
        )
