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
