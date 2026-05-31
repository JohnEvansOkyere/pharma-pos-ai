"""
Pydantic schemas for the Customer retention module.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class CustomerCreate(BaseModel):
    full_name: str
    phone: str
    email: Optional[str] = None
    date_of_birth: Optional[str] = None    # YYYY-MM-DD
    gender: Optional[str] = None
    address: Optional[str] = None
    town: Optional[str] = None
    region: Optional[str] = None
    known_allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    notes: Optional[str] = None
    sms_consent: Optional[str] = "pending"
    whatsapp_consent: Optional[str] = "pending"
    preferred_channel: Optional[str] = "sms"

    @field_validator("phone")
    @classmethod
    def phone_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Phone number is required")
        return v

    @field_validator("full_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Full name is required")
        return v


class CustomerUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    town: Optional[str] = None
    region: Optional[str] = None
    known_allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    notes: Optional[str] = None
    sms_consent: Optional[str] = None
    whatsapp_consent: Optional[str] = None
    preferred_channel: Optional[str] = None
    is_active: Optional[bool] = None


class CustomerConsentUpdate(BaseModel):
    """Lightweight endpoint just for updating consent — used from POS."""
    sms_consent: Optional[str] = None
    whatsapp_consent: Optional[str] = None
    preferred_channel: Optional[str] = None


class Customer(BaseModel):
    id: int
    organization_id: int
    branch_id: Optional[int] = None
    full_name: str
    phone: str
    email: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    town: Optional[str] = None
    region: Optional[str] = None
    known_allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    notes: Optional[str] = None
    sms_consent: str
    whatsapp_consent: str
    consent_recorded_at: Optional[datetime] = None
    preferred_channel: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    total_purchases: Optional[int] = None   # enriched at query time

    model_config = {"from_attributes": True}


class CustomerSearchResult(BaseModel):
    """Lightweight result for POS search-as-you-type."""
    id: int
    full_name: str
    phone: str
    email: Optional[str] = None
    sms_consent: str
    whatsapp_consent: str
    preferred_channel: str

    model_config = {"from_attributes": True}


class FollowUpSchema(BaseModel):
    id: int
    customer_id: int
    sale_id: int
    scheduled_at: datetime
    channel: str
    status: str
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    attempts: int
    last_error: Optional[str] = None
    message_text: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
