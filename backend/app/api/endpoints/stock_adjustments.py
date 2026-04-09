"""
Stock adjustment API endpoints.
"""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_active_user, require_manager
from app.db.base import get_db
from app.models.product import Product, ProductBatch
from app.models.stock_adjustment import AdjustmentType, StockAdjustment
from app.models.user import User
from app.services.audit_service import AuditService
from app.schemas.stock_adjustment import (
    StockAdjustment as StockAdjustmentSchema,
    StockAdjustmentCreate,
)
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/stock-adjustments", tags=["Stock Adjustments"])


DECREMENT_TYPES = {
    AdjustmentType.SUBTRACTION,
    AdjustmentType.DAMAGE,
    AdjustmentType.EXPIRED,
}

INCREMENT_TYPES = {
    AdjustmentType.ADDITION,
    AdjustmentType.RETURN,
}


def _consume_from_batches(product: Product, batches: List[ProductBatch], quantity: int) -> None:
    """Reduce quantity from batches in the provided order."""
    remaining = quantity
    for batch in batches:
        if remaining <= 0:
            break

        consumed = min(batch.quantity, remaining)
        batch.quantity -= consumed
        remaining -= consumed

    if remaining > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient batch stock for product {product.name}.",
        )


@router.get("", response_model=List[StockAdjustmentSchema])
def list_stock_adjustments(
    product_id: Optional[int] = None,
    batch_id: Optional[int] = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List stock adjustments for review and reporting."""
    query = db.query(StockAdjustment)

    if product_id is not None:
        query = query.filter(StockAdjustment.product_id == product_id)

    if batch_id is not None:
        query = query.filter(StockAdjustment.batch_id == batch_id)

    return query.order_by(StockAdjustment.created_at.desc()).limit(limit).all()


@router.post("", response_model=StockAdjustmentSchema, status_code=status.HTTP_201_CREATED)
def create_stock_adjustment(
    adjustment: StockAdjustmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """
    Record manual stock adjustments such as damage, expiry write-off, returns,
    and controlled inventory corrections.
    """
    try:
        product = db.query(Product).filter(Product.id == adjustment.product_id).with_for_update().first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )

        batch: Optional[ProductBatch] = None
        if adjustment.batch_id is not None:
            batch = db.query(ProductBatch).filter(
                ProductBatch.id == adjustment.batch_id
            ).with_for_update().first()
            if not batch or batch.product_id != product.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Batch does not belong to the selected product",
                )

        adjustment_type = adjustment.adjustment_type

        if adjustment_type in INCREMENT_TYPES and batch is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch ID is required for stock additions and returns",
            )

        if adjustment_type == AdjustmentType.CORRECTION and batch is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch ID is required for correction adjustments",
            )

        if adjustment_type == AdjustmentType.EXPIRED and batch is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch ID is required for expiry write-offs",
            )

        adjustment_quantity = adjustment.quantity

        if adjustment_type in INCREMENT_TYPES:
            batch.quantity += adjustment.quantity
        elif adjustment_type == AdjustmentType.CORRECTION:
            difference = adjustment.quantity - batch.quantity
            adjustment_quantity = abs(difference)
            if adjustment_quantity == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Correction made no stock change",
                )
            batch.quantity = adjustment.quantity
        elif batch is not None:
            if adjustment_type == AdjustmentType.EXPIRED and batch.expiry_date > date.today():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot mark a future-dated batch as expired",
                )
            if batch.quantity < adjustment.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Batch only has {batch.quantity} units available",
                )
            batch.quantity -= adjustment.quantity
        else:
            available_batches = InventoryService.sellable_batches_query(db, product.id).with_for_update().order_by(
                ProductBatch.expiry_date.asc(),
                ProductBatch.received_date.asc(),
                ProductBatch.id.asc(),
            ).all()
            sellable_quantity = sum(batch_item.quantity for batch_item in available_batches)
            if sellable_quantity < adjustment.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Only {sellable_quantity} sellable units are available for adjustment",
                )
            _consume_from_batches(product, available_batches, adjustment.quantity)

        InventoryService.recalculate_product_stock(db, product)

        db_adjustment = StockAdjustment(
            product_id=product.id,
            batch_id=batch.id if batch else None,
            adjustment_type=adjustment_type,
            quantity=adjustment_quantity,
            reason=adjustment.reason,
            performed_by=current_user.id,
        )
        db.add(db_adjustment)
        db.commit()
        db.refresh(db_adjustment)
        AuditService.log(
            db,
            action="create_stock_adjustment",
            user_id=current_user.id,
            entity_type="stock_adjustment",
            entity_id=db_adjustment.id,
            description=f"Recorded {adjustment_type.value} adjustment for product {product.name}",
            extra_data={
                "product_id": product.id,
                "batch_id": batch.id if batch else None,
                "quantity": adjustment_quantity,
            },
        )
        db.commit()
        return db_adjustment
    except Exception:
        db.rollback()
        raise
