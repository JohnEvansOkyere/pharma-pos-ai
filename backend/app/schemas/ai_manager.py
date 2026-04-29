"""
Schemas for the read-only AI manager assistant.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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
    generated_at: datetime
    created_at: datetime
