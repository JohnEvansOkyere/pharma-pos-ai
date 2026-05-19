"""
Helpers for seeding cloud projections from an existing local catalog.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.models.product import Product, ProductBatch
from app.models.sync_event import SyncEventType
from app.services.inventory_service import InventoryService
from app.services.sync_outbox_service import SyncOutboxService


class FullSnapshotSyncService:
    """Enqueue current product and batch state into the local sync outbox."""

    @staticmethod
    def enqueue_catalog_snapshot(db: Session, *, include_inactive: bool = False) -> dict[str, Any]:
        generated_at = datetime.now(timezone.utc).isoformat()
        product_query = db.query(Product).options(selectinload(Product.batches)).order_by(Product.id.asc())
        if not include_inactive:
            product_query = product_query.filter(Product.is_active.is_(True))

        products = product_query.all()
        product_event_count = 0
        batch_event_count = 0

        for product in products:
            stock_after = InventoryService.recalculate_product_stock(db, product)
            SyncOutboxService.record_event(
                db,
                event_type=SyncEventType.PRODUCT_CREATED,
                aggregate_type="product",
                aggregate_id=product.id,
                organization_id=product.organization_id,
                branch_id=product.branch_id,
                payload={
                    "product_id": product.id,
                    "name": product.name,
                    "sku": product.sku,
                    "barcode": product.barcode,
                    "category_id": product.category_id,
                    "cost_price": product.cost_price,
                    "selling_price": product.selling_price,
                    "total_stock": stock_after,
                    "low_stock_threshold": product.low_stock_threshold,
                    "reorder_level": product.reorder_level,
                    "is_active": product.is_active,
                    "snapshot_reason": "full_catalog_snapshot",
                    "snapshot_generated_at": generated_at,
                },
            )
            product_event_count += 1

            batches = sorted(product.batches, key=lambda batch: (batch.id or 0))
            for batch in batches:
                FullSnapshotSyncService._enqueue_batch_snapshot(
                    db,
                    product=product,
                    batch=batch,
                    stock_after=stock_after,
                    generated_at=generated_at,
                )
                batch_event_count += 1

        return {
            "product_event_count": product_event_count,
            "batch_event_count": batch_event_count,
            "total_event_count": product_event_count + batch_event_count,
            "include_inactive": include_inactive,
            "snapshot_generated_at": generated_at,
        }

    @staticmethod
    def _enqueue_batch_snapshot(
        db: Session,
        *,
        product: Product,
        batch: ProductBatch,
        stock_after: int,
        generated_at: str,
    ) -> None:
        SyncOutboxService.record_event(
            db,
            event_type=SyncEventType.PRODUCT_BATCH_CREATED,
            aggregate_type="product_batch",
            aggregate_id=batch.id,
            organization_id=batch.organization_id or product.organization_id,
            branch_id=batch.branch_id or product.branch_id,
            payload={
                "product_id": product.id,
                "batch_id": batch.id,
                "batch_number": batch.batch_number,
                "quantity": batch.quantity,
                "expiry_date": batch.expiry_date,
                "cost_price": batch.cost_price,
                "is_quarantined": batch.is_quarantined,
                "stock_after": stock_after,
                "snapshot_reason": "full_catalog_snapshot",
                "snapshot_generated_at": generated_at,
            },
        )
