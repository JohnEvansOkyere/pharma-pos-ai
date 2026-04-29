"""
Pydantic schemas for inventory movement ledger records.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.inventory_movement import InventoryMovementType


class InventoryMovement(BaseModel):
    """Inventory movement response schema."""

    id: int
    product_id: int
    batch_id: Optional[int] = None
    movement_type: InventoryMovementType
    quantity_delta: int
    stock_after: Optional[int] = None
    source_document_type: str
    source_document_id: Optional[int] = None
    reason: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
