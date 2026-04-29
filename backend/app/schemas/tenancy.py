"""
Pydantic schemas for tenant, branch, and device records.
"""
from datetime import datetime
from typing import Optional

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
