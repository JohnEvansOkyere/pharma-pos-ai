"""
Pydantic schemas for Product and ProductBatch models.
"""
from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, Field, ConfigDict
from app.models.product import DosageForm, PrescriptionStatus


# Product Batch Schemas
class ProductBatchBase(BaseModel):
    """Base product batch schema."""
    batch_number: str = Field(..., max_length=100)
    quantity: int = Field(..., gt=0)
    manufacture_date: Optional[date] = None
    expiry_date: date
    cost_price: float = Field(..., gt=0)
    location: Optional[str] = Field(None, max_length=100)
    is_quarantined: bool = False
    quarantine_reason: Optional[str] = None


class ProductBatchCreate(ProductBatchBase):
    """Schema for creating a product batch."""
    product_id: int


class ProductBatchUpdate(BaseModel):
    """Schema for updating a product batch."""
    batch_number: Optional[str] = Field(None, max_length=100)
    quantity: Optional[int] = Field(None, gt=0)
    manufacture_date: Optional[date] = None
    expiry_date: Optional[date] = None
    cost_price: Optional[float] = Field(None, gt=0)
    location: Optional[str] = Field(None, max_length=100)
    is_quarantined: Optional[bool] = None
    quarantine_reason: Optional[str] = None


class ProductBatch(ProductBatchBase):
    """Schema for product batch response."""
    id: int
    product_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Product Schemas
class ProductBase(BaseModel):
    """Base product schema."""
    name: str = Field(..., max_length=200)
    generic_name: Optional[str] = Field(None, max_length=200)
    sku: str = Field(..., max_length=50)
    barcode: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None

    # Pharmaceutical-specific fields
    dosage_form: DosageForm = DosageForm.TABLET
    strength: Optional[str] = Field(None, max_length=50)
    prescription_status: PrescriptionStatus = PrescriptionStatus.OTC
    active_ingredient: Optional[str] = Field(None, max_length=200)
    manufacturer: Optional[str] = Field(None, max_length=200)

    # Drug information
    usage_instructions: Optional[str] = None
    side_effects: Optional[str] = None
    contraindications: Optional[str] = None
    storage_conditions: Optional[str] = Field(None, max_length=200)

    # Regulatory
    drug_license_number: Optional[str] = Field(None, max_length=100)
    is_narcotic: bool = False
    requires_id: bool = False

    # Pricing (GH₵)
    cost_price: float = Field(..., gt=0)
    selling_price: float = Field(..., gt=0)
    wholesale_price: Optional[float] = Field(None, gt=0)
    mrp: Optional[float] = Field(None, gt=0)

    # Inventory
    low_stock_threshold: int = Field(10, ge=0)
    reorder_level: int = Field(20, ge=0)
    reorder_quantity: int = Field(100, ge=0)

    category_id: int
    supplier_id: Optional[int] = None
    is_active: bool = True


class ProductCreate(ProductBase):
    """Schema for creating a product."""
    pass


class ProductUpdate(BaseModel):
    """Schema for updating a product."""
    name: Optional[str] = Field(None, max_length=200)
    generic_name: Optional[str] = Field(None, max_length=200)
    sku: Optional[str] = Field(None, max_length=50)
    barcode: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None

    # Pharmaceutical-specific fields
    dosage_form: Optional[DosageForm] = None
    strength: Optional[str] = Field(None, max_length=50)
    prescription_status: Optional[PrescriptionStatus] = None
    active_ingredient: Optional[str] = Field(None, max_length=200)
    manufacturer: Optional[str] = Field(None, max_length=200)

    # Drug information
    usage_instructions: Optional[str] = None
    side_effects: Optional[str] = None
    contraindications: Optional[str] = None
    storage_conditions: Optional[str] = Field(None, max_length=200)

    # Regulatory
    drug_license_number: Optional[str] = Field(None, max_length=100)
    is_narcotic: Optional[bool] = None
    requires_id: Optional[bool] = None

    # Pricing (GH₵)
    cost_price: Optional[float] = Field(None, gt=0)
    selling_price: Optional[float] = Field(None, gt=0)
    wholesale_price: Optional[float] = Field(None, gt=0)
    mrp: Optional[float] = Field(None, gt=0)

    # Inventory
    low_stock_threshold: Optional[int] = Field(None, ge=0)
    reorder_level: Optional[int] = Field(None, ge=0)
    reorder_quantity: Optional[int] = Field(None, ge=0)

    category_id: Optional[int] = None
    supplier_id: Optional[int] = None
    is_active: Optional[bool] = None


class Product(ProductBase):
    """Schema for product response."""
    id: int
    total_stock: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ProductWithBatches(Product):
    """Schema for product with batches."""
    batches: List[ProductBatch] = []

    model_config = ConfigDict(from_attributes=True)


class ProductSearch(BaseModel):
    """Schema for product search results."""
    id: int
    name: str
    generic_name: Optional[str]
    sku: str
    barcode: Optional[str]
    dosage_form: DosageForm
    strength: Optional[str]
    selling_price: float
    cost_price: float
    total_stock: int
    low_stock_threshold: int
    manufacturer: Optional[str]
    category_name: Optional[str] = None
    nearest_expiry: Optional[date] = None  # Earliest expiry date from batches

    model_config = ConfigDict(from_attributes=True)
