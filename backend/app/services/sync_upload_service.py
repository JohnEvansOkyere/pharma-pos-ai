"""
Local sync upload worker helpers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.sync_event import SyncEvent, SyncEventStatus
from app.models.tenancy import Device


class SyncUploadService:
    """Upload pending local outbox events to the configured cloud ingestion API."""

    @staticmethod
    def _resolve_event_identity(db: Session, event: SyncEvent) -> tuple[Optional[int], Optional[int], Optional[str]]:
        organization_id = event.organization_id or settings.CLOUD_SYNC_ORGANIZATION_ID
        branch_id = event.branch_id or settings.CLOUD_SYNC_BRANCH_ID
        device_uid = settings.CLOUD_SYNC_DEVICE_UID

        if event.source_device_id:
            device = db.query(Device).filter(Device.id == event.source_device_id).first()
            if device:
                organization_id = organization_id or device.organization_id
                branch_id = branch_id or device.branch_id
                device_uid = device_uid or device.device_uid

        return organization_id, branch_id, device_uid

    @staticmethod
    def _build_upload_payload(db: Session, event: SyncEvent) -> dict[str, Any]:
        organization_id, branch_id, device_uid = SyncUploadService._resolve_event_identity(db, event)
        if not organization_id or not branch_id or not device_uid:
            raise ValueError("Sync event is missing organization, branch, or device identity")

        return {
            "event_id": event.event_id,
            "organization_id": organization_id,
            "branch_id": branch_id,
            "device_uid": device_uid,
            "local_sequence_number": event.local_sequence_number,
            "event_type": event.event_type.value,
            "aggregate_type": event.aggregate_type,
            "aggregate_id": event.aggregate_id,
            "schema_version": event.schema_version,
            "payload": event.payload,
            "payload_hash": event.payload_hash,
        }

    @staticmethod
    def _headers() -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if settings.CLOUD_SYNC_API_TOKEN:
            headers["Authorization"] = f"Bearer {settings.CLOUD_SYNC_API_TOKEN}"
        return headers

    @staticmethod
    def sync_status(db: Session) -> dict[str, Any]:
        pending_count = db.query(SyncEvent).filter(SyncEvent.status == SyncEventStatus.PENDING).count()
        failed_count = db.query(SyncEvent).filter(SyncEvent.status == SyncEventStatus.FAILED).count()
        sent_count = db.query(SyncEvent).filter(SyncEvent.status == SyncEventStatus.SENT).count()
        last_sent = (
            db.query(SyncEvent)
            .filter(SyncEvent.status == SyncEventStatus.SENT)
            .order_by(SyncEvent.sent_at.desc())
            .first()
        )
        return {
            "enabled": settings.CLOUD_SYNC_ENABLED,
            "configured": bool(settings.CLOUD_SYNC_INGEST_URL),
            "pending_count": pending_count,
            "failed_count": failed_count,
            "sent_count": sent_count,
            "last_sent_at": last_sent.sent_at if last_sent else None,
        }

    @staticmethod
    def upload_pending(db: Session, *, limit: Optional[int] = None) -> dict[str, Any]:
        """Upload pending/failed events. Caller owns the database session."""
        if not settings.CLOUD_SYNC_ENABLED:
            return {"attempted": 0, "sent": 0, "failed": 0, "skipped": 0, "message": "Cloud sync disabled"}
        if not settings.CLOUD_SYNC_INGEST_URL:
            return {"attempted": 0, "sent": 0, "failed": 0, "skipped": 0, "message": "Cloud sync URL not configured"}

        batch_limit = limit or settings.CLOUD_SYNC_BATCH_SIZE
        events = (
            db.query(SyncEvent)
            .filter(
                SyncEvent.status.in_([SyncEventStatus.PENDING, SyncEventStatus.FAILED]),
                SyncEvent.retry_count < settings.CLOUD_SYNC_MAX_RETRIES,
            )
            .order_by(SyncEvent.local_sequence_number.asc())
            .limit(batch_limit)
            .all()
        )

        attempted = 0
        sent = 0
        failed = 0
        skipped = 0
        now = datetime.now(timezone.utc)

        with httpx.Client(timeout=settings.CLOUD_SYNC_TIMEOUT_SECONDS) as client:
            for event in events:
                try:
                    payload = SyncUploadService._build_upload_payload(db, event)
                except ValueError as exc:
                    event.status = SyncEventStatus.FAILED
                    event.retry_count += 1
                    event.last_error = str(exc)
                    failed += 1
                    db.commit()
                    continue

                attempted += 1
                event.status = SyncEventStatus.SENDING
                db.commit()

                try:
                    response = client.post(
                        settings.CLOUD_SYNC_INGEST_URL,
                        json=payload,
                        headers=SyncUploadService._headers(),
                    )
                    if response.status_code in {200, 201, 202}:
                        event.status = SyncEventStatus.SENT
                        event.sent_at = now
                        event.acknowledged_at = datetime.now(timezone.utc)
                        event.last_error = None
                        sent += 1
                    elif response.status_code == 409:
                        event.status = SyncEventStatus.FAILED
                        event.retry_count += 1
                        event.last_error = f"Conflict from cloud ingestion: {response.text[:500]}"
                        failed += 1
                    else:
                        event.status = SyncEventStatus.FAILED
                        event.retry_count += 1
                        event.last_error = f"HTTP {response.status_code}: {response.text[:500]}"
                        failed += 1
                except httpx.HTTPError as exc:
                    event.status = SyncEventStatus.FAILED
                    event.retry_count += 1
                    event.last_error = str(exc)
                    failed += 1

                db.commit()

        return {"attempted": attempted, "sent": sent, "failed": failed, "skipped": skipped, "message": "Sync run complete"}
