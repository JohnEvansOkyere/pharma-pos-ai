"""
Pydantic schemas for Sale and SaleItem models.
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


# Sale Item Schemas
class SaleItemBase(BaseModel):
    """Base sale item schema."""
    product_id: int
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., gt=0)
    discount_amount: float = Field(0.0, ge=0)


class SaleItemCreate(SaleItemBase):
    """Schema for creating a sale item."""
    pass


class SaleItem(SaleItemBase):
    """Schema for sale item response."""
    id: int
    sale_id: int
    total_price: float

    model_config = ConfigDict(from_attributes=True)


class SaleItemWithProduct(SaleItem):
    """Schema for sale item with product details."""
    product_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# Sale Schemas
class SaleBase(BaseModel):
    """Base sale schema."""
    payment_method: str = "cash"
    customer_name: Optional[str] = Field(None, max_length=100)
    customer_phone: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = None


class SaleCreate(SaleBase):
    """Schema for creating a sale."""
    items: List[SaleItemCreate] = Field(..., min_length=1)
    discount_amount: float = Field(0.0, ge=0)
    tax_amount: float = Field(0.0, ge=0)
    amount_paid: float = Field(..., gt=0)


class Sale(SaleBase):
    """Schema for sale response."""
    id: int
    invoice_number: str
    subtotal: float
    discount_amount: float
    tax_amount: float
    total_amount: float
    amount_paid: float
    change_amount: float
    user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SaleWithItems(Sale):
    """Schema for sale with items."""
    items: List[SaleItem] = []

    model_config = ConfigDict(from_attributes=True)


class SaleSummary(BaseModel):
    """Schema for daily sales summary."""
    total_sales: int
    total_revenue: float
    total_profit: float
    total_items_sold: int
