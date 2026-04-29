"""
Project ingested sync events into cloud reporting read models.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.cloud_projection import CloudInventoryMovementFact, CloudSaleFact
from app.models.sync_event import SyncEventType
from app.models.sync_ingestion import IngestedSyncEvent


class CloudProjectionService:
    """Build reporting facts from accepted branch sync events."""

    STOCK_EVENT_TYPES = {
        SyncEventType.STOCK_RECEIVED,
        SyncEventType.STOCK_ADJUSTED,
        SyncEventType.STOCK_TAKE_COMPLETED,
        SyncEventType.SALE_REVERSED,
    }

    @staticmethod
    def status(db: Session) -> dict[str, Any]:
        unprojected_count = db.query(IngestedSyncEvent).filter(
            IngestedSyncEvent.projected_at.is_(None),
            IngestedSyncEvent.projection_error.is_(None),
        ).count()
        projected_count = db.query(IngestedSyncEvent).filter(IngestedSyncEvent.projected_at.is_not(None)).count()
        failed_count = db.query(IngestedSyncEvent).filter(IngestedSyncEvent.projection_error.is_not(None)).count()
        last_projected_at = db.query(func.max(IngestedSyncEvent.projected_at)).scalar()
        return {
            "unprojected_count": unprojected_count,
            "projected_count": projected_count,
            "failed_count": failed_count,
            "last_projected_at": last_projected_at,
        }

    @staticmethod
    def project_pending(db: Session, *, limit: int = 100) -> dict[str, Any]:
        events = (
            db.query(IngestedSyncEvent)
            .filter(
                IngestedSyncEvent.projected_at.is_(None),
                IngestedSyncEvent.projection_error.is_(None),
            )
            .order_by(IngestedSyncEvent.received_at.asc(), IngestedSyncEvent.id.asc())
            .limit(limit)
            .all()
        )

        attempted = 0
        projected = 0
        failed = 0
        skipped = 0

        for event in events:
            attempted += 1
            try:
                was_projected = CloudProjectionService.project_event(db, event)
                if was_projected:
                    projected += 1
                else:
                    skipped += 1
                event.projected_at = datetime.now(timezone.utc)
                event.projection_error = None
                db.commit()
            except Exception as exc:
                db.rollback()
                event = db.query(IngestedSyncEvent).filter(IngestedSyncEvent.id == event.id).one()
                event.projection_error = str(exc)
                failed += 1
                db.commit()

        return {
            "attempted": attempted,
            "projected": projected,
            "failed": failed,
            "skipped": skipped,
            "message": "Projection run complete",
        }

    @staticmethod
    def project_event(db: Session, event: IngestedSyncEvent) -> bool:
        if event.projected_at is not None:
            return False
        if event.event_type == SyncEventType.SALE_CREATED:
            return CloudProjectionService._project_sale_created(db, event)
        if event.event_type in CloudProjectionService.STOCK_EVENT_TYPES:
            return CloudProjectionService._project_inventory_event(db, event)
        return False

    @staticmethod
    def _project_sale_created(db: Session, event: IngestedSyncEvent) -> bool:
        existing = db.query(CloudSaleFact).filter(CloudSaleFact.source_event_id == event.id).first()
        if existing:
            return False

        payload = event.payload
        total_amount = Decimal(str(payload.get("total_amount", "0.00")))
        items = payload.get("items") or []
        fact = CloudSaleFact(
            source_event_id=event.id,
            organization_id=event.organization_id,
            branch_id=event.branch_id,
            source_device_id=event.source_device_id,
            local_sale_id=int(payload.get("sale_id") or event.aggregate_id or 0),
            invoice_number=payload.get("invoice_number") or f"event-{event.event_id}",
            total_amount=total_amount,
            payment_method=payload.get("payment_method"),
            item_count=len(items),
            payload=payload,
        )
        db.add(fact)
        return True

    @staticmethod
    def _movement_lines(event: IngestedSyncEvent) -> list[dict[str, Any]]:
        payload = event.payload

        if event.event_type == SyncEventType.STOCK_RECEIVED:
            return [
                {
                    "product_id": payload.get("product_id"),
                    "batch_id": payload.get("batch_id"),
                    "quantity_delta": payload.get("quantity", 0),
                    "stock_after": payload.get("new_stock"),
                    "reason": "Stock received",
                    "payload": payload,
                }
            ]

        if event.event_type == SyncEventType.STOCK_ADJUSTED:
            movements = payload.get("movements") or []
            return [
                {
                    "product_id": payload.get("product_id"),
                    "batch_id": movement.get("batch_id"),
                    "quantity_delta": movement.get("quantity_delta", 0),
                    "stock_after": payload.get("stock_after"),
                    "reason": payload.get("reason"),
                    "payload": movement,
                }
                for movement in movements
            ]

        if event.event_type == SyncEventType.STOCK_TAKE_COMPLETED:
            return [
                {
                    "product_id": None,
                    "batch_id": None,
                    "quantity_delta": payload.get("total_variance", 0),
                    "stock_after": None,
                    "reason": f"Stock take {payload.get('reference')}",
                    "payload": payload,
                }
            ]

        if event.event_type == SyncEventType.SALE_REVERSED:
            return [
                {
                    "product_id": None,
                    "batch_id": None,
                    "quantity_delta": payload.get("restored_quantity", 0),
                    "stock_after": None,
                    "reason": payload.get("reason"),
                    "payload": payload,
                }
            ]

        return []

    @staticmethod
    def _project_inventory_event(db: Session, event: IngestedSyncEvent) -> bool:
        existing = db.query(CloudInventoryMovementFact).filter(
            CloudInventoryMovementFact.source_event_id == event.id
        ).first()
        if existing:
            return False

        lines = CloudProjectionService._movement_lines(event)
        for index, line in enumerate(lines, start=1):
            db.add(
                CloudInventoryMovementFact(
                    source_event_id=event.id,
                    line_number=index,
                    organization_id=event.organization_id,
                    branch_id=event.branch_id,
                    source_device_id=event.source_device_id,
                    event_type=event.event_type.value,
                    local_product_id=line.get("product_id"),
                    local_batch_id=line.get("batch_id"),
                    quantity_delta=int(line.get("quantity_delta") or 0),
                    stock_after=line.get("stock_after"),
                    reason=line.get("reason"),
                    payload=line.get("payload") or event.payload,
                )
            )
        return bool(lines)
