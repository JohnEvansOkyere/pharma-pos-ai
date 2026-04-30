"""
Schemas for the read-only AI manager assistant.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class AIManagerChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    organization_id: int
    branch_id: Optional[int] = None
    period_days: int = Field(30, ge=1, le=365)


class AIManagerDataScope(BaseModel):
    organization_id: int
    branch_id: Optional[int] = None
    period_days: int
    sources: List[str]


class AIManagerChatResponse(BaseModel):
    answer: str
    data_scope: AIManagerDataScope
    tool_results: Dict[str, Any]
    safety_notes: List[str]
    provider: str
    model: Optional[str] = None
    fallback_used: bool = False
    refused: bool = False


class AIWeeklyReportGenerateRequest(BaseModel):
    organization_id: int
    branch_id: Optional[int] = None
    deliver: bool = False


class AIWeeklyReportDeliverRequest(BaseModel):
    channels: Optional[List[str]] = None

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, value):
        if value is None:
            return value
        allowed = {"email", "telegram"}
        normalized = [channel.strip().lower() for channel in value]
        unsupported = [channel for channel in normalized if channel not in allowed]
        if unsupported:
            raise ValueError("channels may only include email and telegram")
        return normalized


class AIWeeklyReportReviewRequest(BaseModel):
    review_notes: Optional[str] = Field(None, max_length=2000)


class AIWeeklyManagerReportResponse(BaseModel):
    id: int
    organization_id: int
    branch_id: Optional[int] = None
    generated_by_user_id: Optional[int] = None
    performance_period_start: datetime
    performance_period_end: datetime
    action_period_start: date
    action_period_end: date
    title: str
    executive_summary: str
    sections: Dict[str, Any]
    tool_results: Dict[str, Any]
    safety_notes: List[str]
    provider: str
    model: Optional[str] = None
    fallback_used: bool = False
    reviewed_by_user_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    generated_at: datetime
    created_at: datetime


class AIWeeklyReportDeliveryResponse(BaseModel):
    id: int
    report_id: int
    organization_id: int
    branch_id: Optional[int] = None
    channel: str
    recipient: str
    status: str
    attempt_count: int
    error_message: Optional[str] = None
    provider_response: Optional[Dict[str, Any]] = None
    sent_at: Optional[datetime] = None
    created_at: datetime


class AIWeeklyReportDeliverySettingUpsert(BaseModel):
    organization_id: int
    branch_id: Optional[int] = None
    email_enabled: bool = False
    email_recipients: List[str] = []
    telegram_enabled: bool = False
    telegram_chat_ids: List[str] = []
    is_active: bool = True


class AIWeeklyReportDeliverySettingResponse(BaseModel):
    id: int
    organization_id: int
    branch_id: Optional[int] = None
    report_scope_key: str
    email_enabled: bool
    email_recipients: List[str]
    telegram_enabled: bool
    telegram_chat_ids: List[str]
    is_active: bool
    created_by_user_id: Optional[int] = None
    updated_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
