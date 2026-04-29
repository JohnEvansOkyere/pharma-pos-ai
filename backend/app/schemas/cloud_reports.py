"""
Schemas for cloud reporting endpoints.
"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class CloudSalesSummary(BaseModel):
    organization_id: int
    branch_id: Optional[int] = None
    sales_count: int
    total_revenue: float
    total_items: int


class CloudBranchSalesSummary(BaseModel):
    branch_id: int
    sales_count: int
    total_revenue: float
    total_items: int


class CloudInventoryMovementSummary(BaseModel):
    organization_id: int
    branch_id: Optional[int] = None
    movement_count: int
    total_positive_quantity: int
    total_negative_quantity: int
    net_quantity_delta: int


class CloudSyncHealth(BaseModel):
    organization_id: int
    branch_id: Optional[int] = None
    ingested_event_count: int
    projected_event_count: int
    projection_failed_count: int
    duplicate_delivery_count: int
    last_received_at: Optional[datetime] = None
    last_projected_at: Optional[datetime] = None


class CloudStockRiskSummary(BaseModel):
    organization_id: int
    branch_id: Optional[int] = None
    low_stock_count: int
    out_of_stock_count: int
    near_expiry_batch_count: int
    expired_batch_count: int
    total_quantity_on_hand: int
    value_at_risk: float
    expiry_warning_days: int


class CloudLowStockItem(BaseModel):
    branch_id: int
    product_id: int
    product_name: str
    sku: str
    total_stock: int
    low_stock_threshold: int
    reorder_level: Optional[int] = None
    units_needed: int
    status: str


class CloudExpiryRiskItem(BaseModel):
    branch_id: int
    product_id: int
    product_name: str
    sku: str
    batch_id: int
    batch_number: str
    quantity: int
    expiry_date: date
    days_until_expiry: int
    value_at_risk: float
    status: str
