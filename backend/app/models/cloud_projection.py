"""
Cloud reporting projection models built from ingested sync events.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base import Base


class CloudSaleFact(Base):
    """Cloud reporting fact for completed branch sales."""

    __tablename__ = "cloud_sale_facts"

    id = Column(Integer, primary_key=True, index=True)
    source_event_id = Column(Integer, ForeignKey("ingested_sync_events.id"), nullable=False, unique=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    source_device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    local_sale_id = Column(Integer, nullable=False, index=True)
    invoice_number = Column(String(50), nullable=False, index=True)
    total_amount = Column(Numeric(12, 2), nullable=False)
    payment_method = Column(String(50))
    item_count = Column(Integer, nullable=False, default=0)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CloudInventoryMovementFact(Base):
    """Cloud reporting fact for stock-impacting branch events."""

    __tablename__ = "cloud_inventory_movement_facts"
    __table_args__ = (
        UniqueConstraint("source_event_id", "line_number", name="uq_cloud_inventory_movement_event_line"),
    )

    id = Column(Integer, primary_key=True, index=True)
    source_event_id = Column(Integer, ForeignKey("ingested_sync_events.id"), nullable=False, index=True)
    line_number = Column(Integer, nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    source_device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    local_product_id = Column(Integer, nullable=True, index=True)
    local_batch_id = Column(Integer, nullable=True, index=True)
    quantity_delta = Column(Integer, nullable=False)
    stock_after = Column(Integer, nullable=True)
    reason = Column(String(300))
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
