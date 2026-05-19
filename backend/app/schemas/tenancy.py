"""
Pydantic schemas for tenant, branch, and device records.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.tenancy import DeviceStatus


class OrganizationBase(BaseModel):
    """Shared organization fields."""

    name: str = Field(..., min_length=1, max_length=200)
    legal_name: Optional[str] = Field(None, max_length=200)
    contact_phone: Optional[str] = Field(None, max_length=20)
    contact_email: Optional[EmailStr] = None
    is_active: bool = True


class Organization(OrganizationBase):
    """Organization response schema."""

    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BranchBase(BaseModel):
    """Shared branch fields."""

    organization_id: int
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    is_active: bool = True


class Branch(BranchBase):
    """Branch response schema."""

    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DeviceBase(BaseModel):
    """Shared device fields."""

    organization_id: int
    branch_id: int
    device_uid: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    status: DeviceStatus = DeviceStatus.ACTIVE


class Device(DeviceBase):
    """Device response schema."""

    id: int
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── Admin API schemas (vendor-facing, cloud only) ─────────────────────────────

class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    legal_name: Optional[str] = Field(None, max_length=200)
    contact_phone: Optional[str] = Field(None, max_length=20)
    contact_email: Optional[EmailStr] = None


class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    legal_name: Optional[str] = Field(None, max_length=200)
    contact_phone: Optional[str] = Field(None, max_length=20)
    contact_email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class OrganizationDetail(BaseModel):
    id: int
    name: str
    legal_name: Optional[str]
    contact_phone: Optional[str]
    contact_email: Optional[str]
    is_active: bool
    created_at: datetime
    branch_count: int = 0
    device_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class BranchCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None


class BranchUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    is_active: Optional[bool] = None


class BranchDetail(BaseModel):
    id: int
    organization_id: int
    name: str
    code: str
    phone: Optional[str]
    address: Optional[str]
    is_active: bool
    created_at: datetime
    device_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class DeviceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class DeviceStatusUpdate(BaseModel):
    status: DeviceStatus


class DeviceDetail(BaseModel):
    id: int
    organization_id: int
    branch_id: int
    device_uid: str
    name: str
    status: DeviceStatus
    last_seen_at: Optional[datetime]
    created_at: datetime
    organization_name: Optional[str] = None
    branch_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DeviceProvisionResponse(BaseModel):
    """Returned once on device creation. raw_token is never stored server-side."""
    id: int
    organization_id: int
    branch_id: int
    device_uid: str
    name: str
    status: DeviceStatus
    created_at: datetime
    raw_token: str
    env_block: str

    model_config = ConfigDict(from_attributes=True)


# ── Admin command center schemas ──────────────────────────────────────────────

class CommandCenterTotals(BaseModel):
    total_pharmacies: int = 0
    active_pharmacies: int = 0
    total_branches: int = 0
    active_branches: int = 0
    total_devices: int = 0
    active_devices: int = 0
    disabled_devices: int = 0
    retired_devices: int = 0
    synced_last_24h: int = 0
    stale_devices: int = 0
    never_synced_devices: int = 0
    branches_without_devices: int = 0
    branches_without_healthy_device: int = 0
    heartbeat_ready_devices: int = 0
    heartbeat_warning_devices: int = 0
    heartbeat_critical_devices: int = 0
    heartbeat_stale_devices: int = 0
    heartbeat_missing_devices: int = 0


class CommandCenterDataTrust(BaseModel):
    status: str
    last_event_received_at: Optional[datetime] = None
    last_projected_at: Optional[datetime] = None
    projection_lag_minutes: Optional[int] = None
    ingested_event_count: int = 0
    projected_event_count: int = 0
    unprojected_event_count: int = 0
    projection_failed_count: int = 0
    duplicate_delivery_count: int = 0


class CommandCenterMoneyPulse(BaseModel):
    today_revenue: float = 0
    yesterday_revenue: float = 0
    trailing_7d_revenue: float = 0
    today_sales_count: int = 0
    yesterday_sales_count: int = 0
    trailing_7d_sales_count: int = 0


class CommandCenterStockRisk(BaseModel):
    out_of_stock_products: int = 0
    low_stock_products: int = 0
    expired_batches: int = 0
    near_expiry_batches: int = 0
    quantity_on_hand: int = 0
    value_at_risk: float = 0
    expiry_warning_days: int = 90


class CommandCenterAttentionItem(BaseModel):
    severity: str
    kind: str
    title: str
    detail: str
    organization_id: Optional[int] = None
    organization_name: Optional[str] = None
    branch_id: Optional[int] = None
    branch_name: Optional[str] = None
    device_id: Optional[int] = None
    device_name: Optional[str] = None
    last_seen_at: Optional[datetime] = None


class CommandCenterOrganizationSummary(BaseModel):
    organization_id: int
    organization_name: str
    branch_count: int = 0
    device_count: int = 0
    active_device_count: int = 0
    stale_device_count: int = 0
    never_synced_device_count: int = 0
    last_seen_at: Optional[datetime] = None
    today_revenue: float = 0
    trailing_7d_revenue: float = 0
    projection_failed_count: int = 0
    sync_status: str = "unknown"
    readiness_status: str = "unknown"
    last_heartbeat_at: Optional[datetime] = None
    heartbeat_critical_count: int = 0
    heartbeat_warning_count: int = 0
    heartbeat_stale_count: int = 0
    heartbeat_missing_count: int = 0


class AdminCommandCenterResponse(BaseModel):
    generated_at: datetime
    totals: CommandCenterTotals
    data_trust: CommandCenterDataTrust
    last_heartbeat_at: Optional[datetime] = None
    money: CommandCenterMoneyPulse
    stock_risk: CommandCenterStockRisk
    attention: List[CommandCenterAttentionItem] = []
    organizations: List[CommandCenterOrganizationSummary] = []
