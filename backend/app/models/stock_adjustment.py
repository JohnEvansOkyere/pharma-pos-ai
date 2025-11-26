"""
Stock adjustment model for inventory corrections.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum

from app.db.base import Base


class AdjustmentType(str, Enum):
    """Stock adjustment type enumeration."""
    ADDITION = "addition"
    SUBTRACTION = "subtraction"
    CORRECTION = "correction"
    DAMAGE = "damage"
    RETURN = "return"


class StockAdjustment(Base):
    """Stock adjustment for tracking inventory changes outside of sales."""

    __tablename__ = "stock_adjustments"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    adjustment_type = Column(SQLEnum(AdjustmentType), nullable=False)
    quantity = Column(Integer, nullable=False)
    reason = Column(Text)
    performed_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<StockAdjustment(id={self.id}, product_id={self.product_id}, type='{self.adjustment_type}', qty={self.quantity})>"
