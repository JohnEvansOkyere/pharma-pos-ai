"""
Schemas for cloud sync ingestion.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.sync_event import SyncEventType


class SyncIngestionRequest(BaseModel):
    """One local outbox event submitted by a branch device."""

    event_id: str = Field(..., min_length=36, max_length=36)
    organization_id: int
    branch_id: int
    device_uid: str = Field(..., min_length=1, max_length=100)
    local_sequence_number: int = Field(..., ge=1)
    event_type: SyncEventType
    aggregate_type: str = Field(..., min_length=1, max_length=50)
    aggregate_id: Optional[int] = None
    schema_version: int = Field(1, ge=1)
    payload: dict[str, Any]
    payload_hash: str = Field(..., min_length=64, max_length=64)


class SyncIngestionResponse(BaseModel):
    """Result of accepting or deduplicating an uploaded event."""

    accepted: bool
    duplicate: bool
    event_id: str
    ingested_event_id: int
    local_sequence_number: int
    received_at: datetime

    model_config = ConfigDict(from_attributes=True)
