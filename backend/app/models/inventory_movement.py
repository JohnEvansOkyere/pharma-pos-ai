"""
Append-only inventory movement ledger.
"""
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class InventoryMovementType(str, Enum):
    """Business reason for an inventory quantity change."""

    STOCK_RECEIVED = "stock_received"
    INITIAL_BATCH_STOCK = "initial_batch_stock"
    SALE_DISPENSED = "sale_dispensed"
    SALE_REVERSED = "sale_reversed"
    STOCK_ADJUSTMENT_POSITIVE = "stock_adjustment_positive"
    STOCK_ADJUSTMENT_NEGATIVE = "stock_adjustment_negative"
    STOCK_CORRECTION = "stock_correction"
    EXPIRY_WRITE_OFF = "expiry_write_off"
    DAMAGE_WRITE_OFF = "damage_write_off"
    RETURNED_TO_STOCK = "returned_to_stock"


class InventoryMovement(Base):
    """Append-only stock movement record for audit, reporting, and future sync."""

    __tablename__ = "inventory_movements"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)
    source_device_id = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("product_batches.id"), nullable=True, index=True)
    movement_type = Column(SQLEnum(InventoryMovementType), nullable=False, index=True)
    quantity_delta = Column(Integer, nullable=False)
    stock_after = Column(Integer, nullable=True)
    source_document_type = Column(String(50), nullable=False, index=True)
    source_document_id = Column(Integer, nullable=True, index=True)
    reason = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    product = relationship("Product")
    batch = relationship("ProductBatch")
    user = relationship("User")

    def __repr__(self):
        return (
            f"<InventoryMovement(id={self.id}, product_id={self.product_id}, "
            f"batch_id={self.batch_id}, delta={self.quantity_delta})>"
        )
