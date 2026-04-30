"""
Cloud reporting projection models built from ingested sync events.
"""
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
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


class CloudProductSnapshot(Base):
    """Current cloud product state projected from branch sync events."""

    __tablename__ = "cloud_product_snapshots"
    __table_args__ = (
        UniqueConstraint("organization_id", "branch_id", "local_product_id", name="uq_cloud_product_snapshot_scope_product"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    local_product_id = Column(Integer, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    sku = Column(String(50), nullable=False, index=True)
    total_stock = Column(Integer, nullable=False, default=0)
    low_stock_threshold = Column(Integer, nullable=False, default=10)
    reorder_level = Column(Integer, nullable=True)
    cost_price = Column(Numeric(12, 2), nullable=True)
    selling_price = Column(Numeric(12, 2), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    last_source_event_id = Column(Integer, ForeignKey("ingested_sync_events.id"), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CloudBatchSnapshot(Base):
    """Current cloud batch state projected from branch sync events."""

    __tablename__ = "cloud_batch_snapshots"
    __table_args__ = (
        UniqueConstraint("organization_id", "branch_id", "local_batch_id", name="uq_cloud_batch_snapshot_scope_batch"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    local_batch_id = Column(Integer, nullable=False, index=True)
    local_product_id = Column(Integer, nullable=False, index=True)
    batch_number = Column(String(100), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=0)
    expiry_date = Column(Date, nullable=False, index=True)
    cost_price = Column(Numeric(12, 2), nullable=True)
    is_quarantined = Column(Boolean, nullable=False, default=False, index=True)
    last_source_event_id = Column(Integer, ForeignKey("ingested_sync_events.id"), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CloudReconciliationAcknowledgement(Base):
    """Manager workflow state for generated cloud reconciliation issues."""

    __tablename__ = "cloud_reconciliation_acknowledgements"
    __table_args__ = (
        UniqueConstraint("organization_id", "issue_key", name="uq_cloud_reconciliation_ack_org_issue"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)
    issue_key = Column(String(64), nullable=False, index=True)
    issue_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="acknowledged", index=True)
    notes = Column(Text, nullable=True)
    acknowledged_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True, index=True)
    resolved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True, index=True)
    resolution_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
