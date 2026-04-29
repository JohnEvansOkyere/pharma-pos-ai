"""
Stock take models for controlled physical inventory counts.
"""
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class StockTakeStatus(str, Enum):
    """Lifecycle status for a physical count session."""

    DRAFT = "draft"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class StockTake(Base):
    """Physical stock count session."""

    __tablename__ = "stock_takes"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)
    source_device_id = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)
    reference = Column(String(50), unique=True, nullable=False, index=True)
    status = Column(SQLEnum(StockTakeStatus), default=StockTakeStatus.DRAFT, nullable=False, index=True)
    reason = Column(Text, nullable=False)
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    completed_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    items = relationship("StockTakeItem", back_populates="stock_take", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[created_by])
    completer = relationship("User", foreign_keys=[completed_by])

    def __repr__(self):
        return f"<StockTake(id={self.id}, reference='{self.reference}', status='{self.status}')>"


class StockTakeItem(Base):
    """Batch-level physical count line."""

    __tablename__ = "stock_take_items"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)
    stock_take_id = Column(Integer, ForeignKey("stock_takes.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("product_batches.id"), nullable=False, index=True)
    expected_quantity = Column(Integer, nullable=False)
    counted_quantity = Column(Integer, nullable=False)
    variance_quantity = Column(Integer, nullable=False)
    reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    stock_take = relationship("StockTake", back_populates="items")
    product = relationship("Product")
    batch = relationship("ProductBatch")

    def __repr__(self):
        return (
            f"<StockTakeItem(id={self.id}, stock_take_id={self.stock_take_id}, "
            f"batch_id={self.batch_id}, variance={self.variance_quantity})>"
        )
