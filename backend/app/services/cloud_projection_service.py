"""
Project ingested sync events into cloud reporting read models.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.cloud_projection import (
    CloudBatchSnapshot,
    CloudInventoryMovementFact,
    CloudProductSnapshot,
    CloudSaleFact,
)
from app.models.sync_event import SyncEventType
from app.models.sync_ingestion import IngestedSyncEvent


class CloudProjectionService:
    """Build reporting facts from accepted branch sync events."""

    STOCK_EVENT_TYPES = {
        SyncEventType.SALE_CREATED,
        SyncEventType.STOCK_RECEIVED,
        SyncEventType.STOCK_ADJUSTED,
        SyncEventType.STOCK_TAKE_COMPLETED,
        SyncEventType.SALE_REVERSED,
    }
    PRODUCT_EVENT_TYPES = {
        SyncEventType.PRODUCT_CREATED,
        SyncEventType.PRODUCT_UPDATED,
        SyncEventType.PRODUCT_DEACTIVATED,
    }
    BATCH_EVENT_TYPES = {
        SyncEventType.PRODUCT_BATCH_CREATED,
        SyncEventType.PRODUCT_BATCH_UPDATED,
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
            sale_projected = CloudProjectionService._project_sale_created(db, event)
            stock_projected = CloudProjectionService._apply_sale_stock_effect(db, event)
            return sale_projected or stock_projected
        if event.event_type in CloudProjectionService.PRODUCT_EVENT_TYPES:
            return CloudProjectionService._project_product_event(db, event)
        if event.event_type in CloudProjectionService.BATCH_EVENT_TYPES:
            return CloudProjectionService._project_batch_event(db, event)
        if event.event_type in CloudProjectionService.STOCK_EVENT_TYPES:
            inventory_projected = CloudProjectionService._project_inventory_event(db, event)
            snapshot_projected = CloudProjectionService._apply_stock_snapshot_effect(db, event)
            return inventory_projected or snapshot_projected
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
            if payload.get("lines"):
                return [
                    {
                        "product_id": line.get("product_id"),
                        "batch_id": line.get("batch_id"),
                        "quantity_delta": line.get("variance_quantity", 0),
                        "stock_after": line.get("stock_after"),
                        "reason": line.get("reason") or f"Stock take {payload.get('reference')}",
                        "payload": line,
                    }
                    for line in payload.get("lines") or []
                ]
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
            if payload.get("items"):
                return [
                    {
                        "product_id": item.get("product_id"),
                        "batch_id": item.get("batch_id"),
                        "quantity_delta": item.get("quantity", 0),
                        "stock_after": item.get("stock_after"),
                        "reason": payload.get("reason"),
                        "payload": item,
                    }
                    for item in payload.get("items") or []
                ]
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

    @staticmethod
    def _project_product_event(db: Session, event: IngestedSyncEvent) -> bool:
        payload = event.payload
        local_product_id = payload.get("product_id") or event.aggregate_id
        if local_product_id is None:
            return False

        snapshot = CloudProjectionService._get_product_snapshot(db, event, int(local_product_id))
        if event.event_type == SyncEventType.PRODUCT_DEACTIVATED:
            snapshot.is_active = False
        else:
            updates = payload.get("updates") or {}
            values = {**payload, **updates}
            snapshot.name = str(values.get("name") or snapshot.name or f"Product {local_product_id}")
            snapshot.sku = str(values.get("sku") or snapshot.sku or f"product-{local_product_id}")
            if "total_stock" in values:
                snapshot.total_stock = int(values.get("total_stock") or 0)
            if "low_stock_threshold" in values:
                snapshot.low_stock_threshold = int(values.get("low_stock_threshold") or 0)
            if "reorder_level" in values:
                snapshot.reorder_level = CloudProjectionService._optional_int(values.get("reorder_level"))
            if "cost_price" in values:
                snapshot.cost_price = CloudProjectionService._optional_decimal(values.get("cost_price"))
            if "selling_price" in values:
                snapshot.selling_price = CloudProjectionService._optional_decimal(values.get("selling_price"))
            if "is_active" in values:
                snapshot.is_active = bool(values.get("is_active"))
        snapshot.last_source_event_id = event.id
        snapshot.payload = payload
        snapshot.updated_at = datetime.now(timezone.utc)
        return True

    @staticmethod
    def _project_batch_event(db: Session, event: IngestedSyncEvent) -> bool:
        payload = event.payload
        local_product_id = payload.get("product_id")
        local_batch_id = payload.get("batch_id") or event.aggregate_id
        if local_product_id is None or local_batch_id is None:
            return False

        updates = payload.get("updates") or {}
        values = {**payload, **updates}
        snapshot = CloudProjectionService._get_batch_snapshot(
            db,
            event,
            local_product_id=int(local_product_id),
            local_batch_id=int(local_batch_id),
        )
        snapshot.batch_number = str(values.get("batch_number") or snapshot.batch_number or f"batch-{local_batch_id}")
        if "quantity" in values:
            snapshot.quantity = int(values.get("quantity") or 0)
        snapshot.expiry_date = CloudProjectionService._parse_date(values.get("expiry_date")) or snapshot.expiry_date
        if "cost_price" in values:
            snapshot.cost_price = CloudProjectionService._optional_decimal(values.get("cost_price"))
        if "is_quarantined" in values:
            snapshot.is_quarantined = bool(values.get("is_quarantined"))
        snapshot.last_source_event_id = event.id
        snapshot.payload = payload
        snapshot.updated_at = datetime.now(timezone.utc)

        product = CloudProjectionService._get_product_snapshot(db, event, int(local_product_id))
        if "stock_after" in values:
            product.total_stock = int(values.get("stock_after") or 0)
        else:
            product.total_stock = CloudProjectionService._product_batch_total(db, event, int(local_product_id))
        product.last_source_event_id = event.id
        product.updated_at = datetime.now(timezone.utc)
        return True

    @staticmethod
    def _apply_stock_snapshot_effect(db: Session, event: IngestedSyncEvent) -> bool:
        payload = event.payload

        if event.event_type == SyncEventType.STOCK_RECEIVED:
            product_id = payload.get("product_id")
            batch_id = payload.get("batch_id")
            if product_id is None or batch_id is None:
                return False
            batch = CloudProjectionService._get_batch_snapshot(db, event, local_product_id=int(product_id), local_batch_id=int(batch_id))
            batch.batch_number = str(payload.get("batch_number") or batch.batch_number or f"batch-{batch_id}")
            batch.quantity = max(0, batch.quantity + int(payload.get("quantity") or 0))
            batch.last_source_event_id = event.id
            batch.payload = payload
            batch.updated_at = datetime.now(timezone.utc)

            product = CloudProjectionService._get_product_snapshot(db, event, int(product_id))
            product.total_stock = int(payload.get("new_stock") if payload.get("new_stock") is not None else product.total_stock + int(payload.get("quantity") or 0))
            product.last_source_event_id = event.id
            product.updated_at = datetime.now(timezone.utc)
            return True

        if event.event_type == SyncEventType.STOCK_ADJUSTED:
            product_id = payload.get("product_id")
            if product_id is None:
                return False
            changed = False
            for movement in payload.get("movements") or []:
                batch_id = movement.get("batch_id")
                if batch_id is None:
                    continue
                batch = CloudProjectionService._get_batch_snapshot(db, event, local_product_id=int(product_id), local_batch_id=int(batch_id))
                batch.quantity = max(0, batch.quantity + int(movement.get("quantity_delta") or 0))
                batch.last_source_event_id = event.id
                batch.payload = {**payload, "movement": movement}
                batch.updated_at = datetime.now(timezone.utc)
                changed = True

            product = CloudProjectionService._get_product_snapshot(db, event, int(product_id))
            if payload.get("stock_after") is not None:
                product.total_stock = int(payload.get("stock_after") or 0)
            elif changed:
                product.total_stock = CloudProjectionService._product_batch_total(db, event, int(product_id))
            product.last_source_event_id = event.id
            product.updated_at = datetime.now(timezone.utc)
            return True

        if event.event_type == SyncEventType.STOCK_TAKE_COMPLETED:
            changed = False
            for line in payload.get("lines") or []:
                product_id = line.get("product_id")
                batch_id = line.get("batch_id")
                if product_id is None or batch_id is None:
                    continue
                batch = CloudProjectionService._get_batch_snapshot(db, event, local_product_id=int(product_id), local_batch_id=int(batch_id))
                batch.batch_number = str(line.get("batch_number") or batch.batch_number or f"batch-{batch_id}")
                batch.quantity = max(0, int(line.get("counted_quantity") or 0))
                batch.last_source_event_id = event.id
                batch.payload = {**payload, "line": line}
                batch.updated_at = datetime.now(timezone.utc)

                product = CloudProjectionService._get_product_snapshot(db, event, int(product_id))
                if line.get("stock_after") is not None:
                    product.total_stock = int(line.get("stock_after") or 0)
                else:
                    product.total_stock = CloudProjectionService._product_batch_total(db, event, int(product_id))
                product.last_source_event_id = event.id
                product.updated_at = datetime.now(timezone.utc)
                changed = True
            return changed

        if event.event_type == SyncEventType.SALE_REVERSED:
            changed = False
            for item in payload.get("items") or []:
                product_id = item.get("product_id")
                quantity = int(item.get("quantity") or 0)
                if product_id is None or quantity <= 0:
                    continue
                product = CloudProjectionService._get_product_snapshot(db, event, int(product_id))
                product.total_stock += quantity
                product.last_source_event_id = event.id
                product.updated_at = datetime.now(timezone.utc)

                batch = None
                if item.get("batch_id") is not None:
                    batch = CloudProjectionService._get_batch_snapshot(
                        db,
                        event,
                        local_product_id=int(product_id),
                        local_batch_id=int(item.get("batch_id")),
                    )
                elif item.get("batch_number"):
                    batch = CloudProjectionService._find_batch_by_number(db, event, int(product_id), str(item.get("batch_number")))
                if batch:
                    batch.quantity += quantity
                    batch.last_source_event_id = event.id
                    batch.payload = {**payload, "item": item}
                    batch.updated_at = datetime.now(timezone.utc)
                changed = True
            return changed

        return False

    @staticmethod
    def _apply_sale_stock_effect(db: Session, event: IngestedSyncEvent) -> bool:
        changed = False
        for item in event.payload.get("items") or []:
            product_id = item.get("product_id")
            quantity = int(item.get("quantity") or 0)
            if product_id is None or quantity <= 0:
                continue

            product = CloudProjectionService._get_product_snapshot(db, event, int(product_id))
            product.total_stock = max(0, product.total_stock - quantity)
            product.last_source_event_id = event.id
            product.updated_at = datetime.now(timezone.utc)

            batch_number = item.get("batch_number")
            if batch_number:
                batch = CloudProjectionService._find_batch_by_number(db, event, int(product_id), str(batch_number))
                if batch:
                    batch.quantity = max(0, batch.quantity - quantity)
                    batch.last_source_event_id = event.id
                    batch.updated_at = datetime.now(timezone.utc)
            changed = True
        return changed

    @staticmethod
    def _get_product_snapshot(db: Session, event: IngestedSyncEvent, local_product_id: int) -> CloudProductSnapshot:
        snapshot = db.query(CloudProductSnapshot).filter(
            CloudProductSnapshot.organization_id == event.organization_id,
            CloudProductSnapshot.branch_id == event.branch_id,
            CloudProductSnapshot.local_product_id == local_product_id,
        ).first()
        if snapshot:
            return snapshot
        snapshot = CloudProductSnapshot(
            organization_id=event.organization_id,
            branch_id=event.branch_id,
            local_product_id=local_product_id,
            name=f"Product {local_product_id}",
            sku=f"product-{local_product_id}",
            total_stock=0,
            low_stock_threshold=10,
            reorder_level=None,
            is_active=True,
            last_source_event_id=event.id,
            payload={},
        )
        db.add(snapshot)
        db.flush()
        return snapshot

    @staticmethod
    def _get_batch_snapshot(
        db: Session,
        event: IngestedSyncEvent,
        *,
        local_product_id: int,
        local_batch_id: int,
    ) -> CloudBatchSnapshot:
        snapshot = db.query(CloudBatchSnapshot).filter(
            CloudBatchSnapshot.organization_id == event.organization_id,
            CloudBatchSnapshot.branch_id == event.branch_id,
            CloudBatchSnapshot.local_batch_id == local_batch_id,
        ).first()
        if snapshot:
            return snapshot
        snapshot = CloudBatchSnapshot(
            organization_id=event.organization_id,
            branch_id=event.branch_id,
            local_batch_id=local_batch_id,
            local_product_id=local_product_id,
            batch_number=f"batch-{local_batch_id}",
            quantity=0,
            expiry_date=date(9999, 12, 31),
            is_quarantined=False,
            last_source_event_id=event.id,
            payload={},
        )
        db.add(snapshot)
        db.flush()
        return snapshot

    @staticmethod
    def _find_batch_by_number(
        db: Session,
        event: IngestedSyncEvent,
        local_product_id: int,
        batch_number: str,
    ) -> Optional[CloudBatchSnapshot]:
        return db.query(CloudBatchSnapshot).filter(
            CloudBatchSnapshot.organization_id == event.organization_id,
            CloudBatchSnapshot.branch_id == event.branch_id,
            CloudBatchSnapshot.local_product_id == local_product_id,
            CloudBatchSnapshot.batch_number == batch_number,
        ).first()

    @staticmethod
    def _product_batch_total(db: Session, event: IngestedSyncEvent, local_product_id: int) -> int:
        return int(
            db.query(func.coalesce(func.sum(CloudBatchSnapshot.quantity), 0)).filter(
                CloudBatchSnapshot.organization_id == event.organization_id,
                CloudBatchSnapshot.branch_id == event.branch_id,
                CloudBatchSnapshot.local_product_id == local_product_id,
                CloudBatchSnapshot.is_quarantined.is_(False),
            ).scalar() or 0
        )

    @staticmethod
    def _parse_date(value: Any) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))

    @staticmethod
    def _optional_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        return int(value)

    @staticmethod
    def _optional_decimal(value: Any) -> Optional[Decimal]:
        if value is None:
            return None
        return Decimal(str(value))
