"""
Inventory service helpers for batch-aware stock calculations.
"""
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

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
