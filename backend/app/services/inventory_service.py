"""
Inventory service helpers for batch-aware stock calculations.
"""
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.inventory_movement import InventoryMovement, InventoryMovementType
from app.models.product import Product, ProductBatch


class InventoryService:
    """Helpers for maintaining sellable stock based on valid batches."""

    @staticmethod
    def sellable_batches_query(db: Session, product_id: int):
        """Return the base query for sellable product batches."""
        return db.query(ProductBatch).filter(
            ProductBatch.product_id == product_id,
            ProductBatch.quantity > 0,
            ProductBatch.is_quarantined == False,
            ProductBatch.expiry_date >= date.today(),
        )

    @staticmethod
    def get_nearest_sellable_expiry(db: Session, product_id: int) -> Optional[date]:
        """Get the nearest expiry date from sellable batches."""
        nearest_batch = InventoryService.sellable_batches_query(db, product_id).order_by(
            ProductBatch.expiry_date.asc(),
            ProductBatch.received_date.asc(),
            ProductBatch.id.asc(),
        ).first()
        return nearest_batch.expiry_date if nearest_batch else None

    @staticmethod
    def recalculate_product_stock(db: Session, product: Product) -> int:
        """Recalculate sellable stock from valid, non-quarantined, non-expired batches."""
        total_stock = sum(
            batch.quantity
            for batch in InventoryService.sellable_batches_query(db, product.id).all()
        )
        product.total_stock = total_stock
        return total_stock

    @staticmethod
    def record_movement(
        db: Session,
        *,
        product_id: int,
        batch_id: Optional[int],
        movement_type: InventoryMovementType,
        quantity_delta: int,
        stock_after: Optional[int],
        source_document_type: str,
        source_document_id: Optional[int],
        reason: Optional[str],
        created_by: Optional[int],
    ) -> InventoryMovement:
        """Append an inventory movement row for a committed stock change."""
        movement = InventoryMovement(
            product_id=product_id,
            batch_id=batch_id,
            movement_type=movement_type,
            quantity_delta=quantity_delta,
            stock_after=stock_after,
            source_document_type=source_document_type,
            source_document_id=source_document_id,
            reason=reason,
            created_by=created_by,
        )
        db.add(movement)
        return movement
