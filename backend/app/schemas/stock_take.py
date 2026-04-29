"""
Pydantic schemas for stock take workflows.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.stock_take import StockTakeStatus


class StockTakeItemCreate(BaseModel):
    """Batch-level counted quantity for a stock take."""

    product_id: int
    batch_id: int
    counted_quantity: int = Field(..., ge=0)
    reason: Optional[str] = Field(None, max_length=300)


class StockTakeCreate(BaseModel):
    """Create a stock take draft from physical count lines."""

    reason: str = Field(..., min_length=3, max_length=300)
    notes: Optional[str] = None
    items: List[StockTakeItemCreate] = Field(..., min_length=1)


class StockTakeComplete(BaseModel):
    """Manager approval payload for completing a stock take."""

    notes: Optional[str] = Field(None, max_length=500)


class StockTakeItem(BaseModel):
    """Stock take item response."""

    id: int
    stock_take_id: int
    product_id: int
    batch_id: int
    expected_quantity: int
    counted_quantity: int
    variance_quantity: int
    reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StockTake(BaseModel):
    """Stock take response."""

    id: int
    reference: str
    status: StockTakeStatus
    reason: str
    notes: Optional[str] = None
    created_by: int
    completed_by: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    items: List[StockTakeItem] = []

    model_config = ConfigDict(from_attributes=True)
