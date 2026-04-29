"""
Sync ingestion API endpoints.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.db.base import get_db
from app.models.sync_ingestion import IngestedSyncEvent
from app.models.tenancy import Device, DeviceStatus
from app.schemas.cloud_projection import CloudProjectionRunResult, CloudProjectionStatus
from app.schemas.sync_ingestion import SyncIngestionRequest, SyncIngestionResponse
from app.services.cloud_projection_service import CloudProjectionService
from app.models.user import User

router = APIRouter(prefix="/sync", tags=["Sync"])


def _get_active_device(db: Session, payload: SyncIngestionRequest) -> Device:
    device = db.query(Device).filter(Device.device_uid == payload.device_uid).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device is not registered",
        )
    if device.status != DeviceStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device is not active",
        )
    if device.organization_id != payload.organization_id or device.branch_id != payload.branch_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device does not belong to the submitted organization and branch",
        )
    return device


@router.post("/ingest", response_model=SyncIngestionResponse, status_code=status.HTTP_202_ACCEPTED)
def ingest_sync_event(
    payload: SyncIngestionRequest,
    db: Session = Depends(get_db),
):
    """
    Accept one local outbox event from a registered branch device.

    This endpoint is intentionally idempotent:
    - same event ID and same payload hash returns the existing record
    - same event ID with different payload hash is rejected
    - same device sequence with a different event is rejected
    """
    try:
        device = _get_active_device(db, payload)

        existing_by_event_id = db.query(IngestedSyncEvent).filter(
            IngestedSyncEvent.event_id == payload.event_id
        ).first()
        if existing_by_event_id:
            if existing_by_event_id.payload_hash != payload.payload_hash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Event ID already exists with a different payload hash",
                )
            existing_by_event_id.duplicate_count += 1
            existing_by_event_id.last_duplicate_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing_by_event_id)
            return SyncIngestionResponse(
                accepted=True,
                duplicate=True,
                event_id=existing_by_event_id.event_id,
                ingested_event_id=existing_by_event_id.id,
                local_sequence_number=existing_by_event_id.local_sequence_number,
                received_at=existing_by_event_id.received_at,
            )

        existing_by_sequence = db.query(IngestedSyncEvent).filter(
            IngestedSyncEvent.source_device_id == device.id,
            IngestedSyncEvent.local_sequence_number == payload.local_sequence_number,
        ).first()
        if existing_by_sequence:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Device local sequence number already exists with a different event ID",
            )

        ingested = IngestedSyncEvent(
            event_id=payload.event_id,
            organization_id=payload.organization_id,
            branch_id=payload.branch_id,
            source_device_id=device.id,
            local_sequence_number=payload.local_sequence_number,
            event_type=payload.event_type,
            aggregate_type=payload.aggregate_type,
            aggregate_id=payload.aggregate_id,
            schema_version=payload.schema_version,
            payload=payload.payload,
            payload_hash=payload.payload_hash,
            duplicate_count=0,
        )
        db.add(ingested)
        db.commit()
        db.refresh(ingested)
        return SyncIngestionResponse(
            accepted=True,
            duplicate=False,
            event_id=ingested.event_id,
            ingested_event_id=ingested.id,
            local_sequence_number=ingested.local_sequence_number,
            received_at=ingested.received_at,
        )
    except Exception:
        db.rollback()
        raise


@router.get("/projection-status", response_model=CloudProjectionStatus)
def get_projection_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    status_payload = CloudProjectionService.status(db)
    return CloudProjectionStatus(
        **{
            **status_payload,
            "last_projected_at": status_payload["last_projected_at"].isoformat()
            if status_payload["last_projected_at"]
            else None,
        }
    )


@router.post("/project", response_model=CloudProjectionRunResult)
def project_ingested_events(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return CloudProjectionRunResult(**CloudProjectionService.project_pending(db, limit=limit))
