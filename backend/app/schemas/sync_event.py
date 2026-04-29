"""
Pydantic schemas for sync outbox events.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from app.models.sync_event import SyncEventStatus, SyncEventType


class SyncEvent(BaseModel):
    """Sync event response schema."""

    id: int
    event_id: str
    organization_id: Optional[int] = None
    branch_id: Optional[int] = None
    source_device_id: Optional[int] = None
    local_sequence_number: int
    event_type: SyncEventType
    aggregate_type: str
    aggregate_id: Optional[int] = None
    schema_version: int
    payload: dict[str, Any]
    payload_hash: str
    status: SyncEventStatus
    retry_count: int
    last_error: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
