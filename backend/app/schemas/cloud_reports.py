"""
Schemas for cloud reporting endpoints.
"""
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


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


class CloudReconciliationIssue(BaseModel):
    issue_key: str
    severity: str
    issue_type: str
    branch_id: Optional[int] = None
    product_id: Optional[int] = None
    batch_id: Optional[int] = None
    product_name: Optional[str] = None
    batch_number: Optional[str] = None
    expected_quantity: Optional[int] = None
    actual_quantity: Optional[int] = None
    delta: Optional[int] = None
    message: str
    acknowledgement_status: Optional[str] = None
    acknowledgement_notes: Optional[str] = None
    acknowledged_by_user_id: Optional[int] = None
    acknowledged_at: Optional[datetime] = None
    resolved_by_user_id: Optional[int] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None


class CloudReconciliationSummary(BaseModel):
    organization_id: int
    branch_id: Optional[int] = None
    product_snapshot_count: int
    batch_snapshot_count: int
    movement_fact_count: int
    projection_failed_count: int
    issue_count: int
    critical_issue_count: int
    high_issue_count: int
    medium_issue_count: int
    acknowledged_issue_count: int = 0
    resolved_issue_count: int = 0
    issues: List[CloudReconciliationIssue]


class CloudReconciliationIssueActionRequest(BaseModel):
    organization_id: int
    branch_id: Optional[int] = None
    issue_key: str
    notes: Optional[str] = None


class CloudReconciliationRepairRequest(BaseModel):
    organization_id: int
    branch_id: Optional[int] = None
    issue_key: Optional[str] = None
    repair_type: str
    notes: Optional[str] = None
    limit: int = 100


class CloudReconciliationRepairResponse(BaseModel):
    organization_id: int
    branch_id: Optional[int] = None
    repair_type: str
    issue_key: Optional[str] = None
    attempted: int
    repaired: int
    failed: int
    skipped: int
    message: str
    details: List[dict] = Field(default_factory=list)


class CloudReconciliationAcknowledgementResponse(BaseModel):
    id: int
    organization_id: int
    branch_id: Optional[int] = None
    issue_key: str
    issue_type: str
    severity: str
    status: str
    notes: Optional[str] = None
    acknowledged_by_user_id: Optional[int] = None
    acknowledged_at: Optional[datetime] = None
    resolved_by_user_id: Optional[int] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
