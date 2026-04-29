"""
Schemas for cloud reporting endpoints.
"""
from datetime import datetime
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
