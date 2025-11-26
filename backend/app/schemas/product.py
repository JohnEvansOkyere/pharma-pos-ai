"""
Pydantic schemas for Product and ProductBatch models.
"""
from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, Field, ConfigDict


# Product Batch Schemas
class ProductBatchBase(BaseModel):
    """Base product batch schema."""
    batch_number: str = Field(..., max_length=100)
    quantity: int = Field(..., gt=0)
    manufacture_date: Optional[date] = None
    expiry_date: date
    cost_price: float = Field(..., gt=0)


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
    cost_price: float = Field(..., gt=0)
    selling_price: float = Field(..., gt=0)
    mrp: Optional[float] = Field(None, gt=0)
    low_stock_threshold: int = Field(10, ge=0)
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
    cost_price: Optional[float] = Field(None, gt=0)
    selling_price: Optional[float] = Field(None, gt=0)
    mrp: Optional[float] = Field(None, gt=0)
    low_stock_threshold: Optional[int] = Field(None, ge=0)
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
    sku: str
    barcode: Optional[str]
    selling_price: float
    total_stock: int

    model_config = ConfigDict(from_attributes=True)
