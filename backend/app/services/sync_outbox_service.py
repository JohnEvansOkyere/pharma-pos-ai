"""
Helpers for writing local sync outbox events.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import hashlib
import json
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.sync_event import SyncEvent, SyncEventCounter, SyncEventType


class SyncOutboxService:
    """Write sync events inside the caller's current database transaction."""

    COUNTER_NAME = "sync_events"

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {key: SyncOutboxService._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [SyncOutboxService._json_safe(item) for item in value]
        return value

    @staticmethod
    def _payload_hash(payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _next_sequence(db: Session) -> int:
        counter = (
            db.query(SyncEventCounter)
            .filter(SyncEventCounter.name == SyncOutboxService.COUNTER_NAME)
            .with_for_update()
            .first()
        )
        if counter is None:
            counter = SyncEventCounter(name=SyncOutboxService.COUNTER_NAME, next_value=1)
            db.add(counter)
            db.flush()

        sequence = counter.next_value
        counter.next_value += 1
        return sequence

    @staticmethod
    def record_event(
        db: Session,
        *,
        event_type: SyncEventType,
        aggregate_type: str,
        aggregate_id: Optional[int],
        payload: dict[str, Any],
        organization_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        source_device_id: Optional[int] = None,
        schema_version: int = 1,
    ) -> SyncEvent:
        """Append a pending sync event without committing."""
        safe_payload = SyncOutboxService._json_safe(payload)
        event = SyncEvent(
            event_id=str(uuid4()),
            organization_id=organization_id,
            branch_id=branch_id,
            source_device_id=source_device_id,
            local_sequence_number=SyncOutboxService._next_sequence(db),
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            schema_version=schema_version,
            payload=safe_payload,
            payload_hash=SyncOutboxService._payload_hash(safe_payload),
        )
        db.add(event)
        return event
