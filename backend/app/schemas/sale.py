"""
Pydantic schemas for Sale and SaleItem models.
"""
from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, Field, ConfigDict
from app.models.sale import PaymentMethod, SalePricingMode, SaleReversalType, SaleStatus


# Sale Item Schemas
class SaleItemBase(BaseModel):
    """Base sale item schema."""
    product_id: int
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., gt=0)
    discount_amount: float = Field(0.0, ge=0)

    # Optional product snapshot fields
    product_name: Optional[str] = None
    dosage_form: Optional[str] = None
    strength: Optional[str] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None


class SaleItemCreate(SaleItemBase):
    """Schema for creating a sale item."""
    pass


class SaleItem(SaleItemBase):
    """Schema for sale item response."""
    id: int
    sale_id: int
    total_price: float
    tax_amount: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class SaleItemWithProduct(SaleItem):
    """Schema for sale item with product details (includes all snapshot fields from base)."""

    model_config = ConfigDict(from_attributes=True)


# Sale Schemas
class SaleBase(BaseModel):
    """Base sale schema."""
    payment_method: PaymentMethod = PaymentMethod.CASH
    status: SaleStatus = SaleStatus.COMPLETED
    pricing_mode: SalePricingMode = SalePricingMode.RETAIL

    # Customer information
    customer_name: Optional[str] = Field(None, max_length=100)
    customer_phone: Optional[str] = Field(None, max_length=20)
    customer_id_number: Optional[str] = Field(None, max_length=50)
    customer_address: Optional[str] = None

    # Mobile Money specific
    momo_reference: Optional[str] = Field(None, max_length=100)
    momo_number: Optional[str] = Field(None, max_length=20)

    # Prescription tracking
    prescription_number: Optional[str] = Field(None, max_length=100)
    doctor_name: Optional[str] = Field(None, max_length=100)
    has_prescription: bool = False

    # Insurance (for future enhancement)
    insurance_company: Optional[str] = Field(None, max_length=100)
    insurance_claim_number: Optional[str] = Field(None, max_length=100)
    insurance_coverage: float = 0.0

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
    discount_percentage: float = 0.0
    tax_amount: float
    tax_rate: float = 0.0
    total_amount: float
    amount_paid: float
    change_amount: float
    is_printed: bool = False
    print_count: int = 0
    user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SaleWithItems(Sale):
    """Schema for sale with items."""
    items: List[SaleItemWithProduct] = []

    model_config = ConfigDict(from_attributes=True)


class SaleReversal(BaseModel):
    """Sale reversal/refund response schema."""
    id: int
    sale_id: int
    reversal_type: SaleReversalType
    reason: str
    total_amount: float
    restored_quantity: int
    performed_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SaleSummary(BaseModel):
    """Schema for daily sales summary."""
    total_sales: int
    total_revenue: float
    total_profit: float
    total_items_sold: int


class SaleActionRequest(BaseModel):
    """Manager-controlled sale reversal request."""
    reason: str = Field(..., min_length=3, max_length=300)


class EndOfDayCloseout(BaseModel):
    """Operational closeout summary for a business day."""
    business_date: date
    completed_sales_count: int
    refunded_sales_count: int
    cancelled_sales_count: int
    completed_revenue: float
    refunded_revenue: float
    cancelled_revenue: float
    cash_revenue: float
    momo_revenue: float
    card_revenue: float
    bank_transfer_revenue: float
    credit_revenue: float
