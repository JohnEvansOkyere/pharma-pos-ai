"""
Pydantic schemas for stock adjustments.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.stock_adjustment import AdjustmentType


class StockAdjustmentBase(BaseModel):
    """Base schema for stock adjustments."""
    adjustment_type: AdjustmentType
    quantity: int = Field(..., gt=0)
    reason: str = Field(..., min_length=3)
    batch_id: Optional[int] = None


class StockAdjustmentCreate(StockAdjustmentBase):
    """Schema for creating stock adjustments."""
    product_id: int


class StockAdjustment(StockAdjustmentBase):
    """Schema for stock adjustment response."""
    id: int
    product_id: int
    performed_by: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
