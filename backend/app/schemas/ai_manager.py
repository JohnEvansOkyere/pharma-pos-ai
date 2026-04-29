"""
Schemas for the read-only AI manager assistant.
"""
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
    refused: bool = False
