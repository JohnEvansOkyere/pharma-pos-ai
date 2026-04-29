"""
Stock take API endpoints.
"""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import get_current_active_user, require_perform_stock_take
from app.db.base import get_db
from app.models.inventory_movement import InventoryMovementType
from app.models.product import Product, ProductBatch
from app.models.stock_adjustment import AdjustmentType, StockAdjustment
from app.models.stock_take import StockTake, StockTakeItem, StockTakeStatus
from app.models.sync_event import SyncEventType
from app.models.user import User
from app.schemas.stock_take import (
    StockTake as StockTakeSchema,
    StockTakeComplete,
    StockTakeCreate,
)
from app.services.audit_service import AuditService
from app.services.inventory_service import InventoryService
from app.services.sync_outbox_service import SyncOutboxService

router = APIRouter(prefix="/stock-takes", tags=["Stock Takes"])


@router.get("", response_model=List[StockTakeSchema])
def list_stock_takes(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List recent stock take sessions."""
    return (
        db.query(StockTake)
        .options(joinedload(StockTake.items))
        .order_by(StockTake.created_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/{stock_take_id}", response_model=StockTakeSchema)
def get_stock_take(
    stock_take_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get one stock take session with counted lines."""
    stock_take = (
        db.query(StockTake)
        .options(joinedload(StockTake.items))
        .filter(StockTake.id == stock_take_id)
        .first()
    )
    if not stock_take:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stock take not found",
        )
    return stock_take


@router.post("", response_model=StockTakeSchema, status_code=status.HTTP_201_CREATED)
def create_stock_take(
    payload: StockTakeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_perform_stock_take),
):
    """Create a stock take draft from batch-level physical counts."""
    try:
        seen_batch_ids: set[int] = set()
        stock_take = StockTake(
            reference=f"PENDING-STOCK-TAKE-{datetime.now(timezone.utc).timestamp()}",
            reason=payload.reason.strip(),
            notes=payload.notes,
            created_by=current_user.id,
        )
        db.add(stock_take)
        db.flush()
        stock_take.reference = f"STK-{datetime.now().strftime('%Y%m%d')}-{stock_take.id:06d}"

        for item in payload.items:
            if item.batch_id in seen_batch_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Each batch can only appear once in a stock take",
                )
            seen_batch_ids.add(item.batch_id)

            product = db.query(Product).filter(Product.id == item.product_id).first()
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product {item.product_id} not found",
                )

            batch = db.query(ProductBatch).filter(ProductBatch.id == item.batch_id).first()
            if not batch or batch.product_id != product.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Batch does not belong to the selected product",
                )

            expected_quantity = batch.quantity
            counted_quantity = item.counted_quantity
            db.add(
                StockTakeItem(
                    stock_take_id=stock_take.id,
                    product_id=product.id,
                    batch_id=batch.id,
                    expected_quantity=expected_quantity,
                    counted_quantity=counted_quantity,
                    variance_quantity=counted_quantity - expected_quantity,
                    reason=item.reason,
                )
            )

        SyncOutboxService.record_event(
            db,
            event_type=SyncEventType.STOCK_TAKE_CREATED,
            aggregate_type="stock_take",
            aggregate_id=stock_take.id,
            organization_id=stock_take.organization_id,
            branch_id=stock_take.branch_id,
            source_device_id=stock_take.source_device_id,
            payload={
                "stock_take_id": stock_take.id,
                "reference": stock_take.reference,
                "reason": stock_take.reason,
                "line_count": len(payload.items),
                "created_by": current_user.id,
            },
        )
        AuditService.log(
            db,
            action="create_stock_take",
            user_id=current_user.id,
            entity_type="stock_take",
            entity_id=stock_take.id,
            description=f"Created stock take {stock_take.reference}",
            extra_data={"line_count": len(payload.items), "reason": stock_take.reason},
        )
        db.commit()
        db.refresh(stock_take)
        return stock_take
    except Exception:
        db.rollback()
        raise


@router.post("/{stock_take_id}/complete", response_model=StockTakeSchema)
def complete_stock_take(
    stock_take_id: int,
    payload: StockTakeComplete,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_perform_stock_take),
):
    """Approve a stock take and apply audited batch-level corrections."""
    try:
        stock_take = (
            db.query(StockTake)
            .options(joinedload(StockTake.items))
            .filter(StockTake.id == stock_take_id)
            .with_for_update()
            .first()
        )
        if not stock_take:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stock take not found",
            )

        if stock_take.status != StockTakeStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only draft stock takes can be completed",
            )

        movement_count = 0
        total_variance = 0

        for item in stock_take.items:
            batch = db.query(ProductBatch).filter(ProductBatch.id == item.batch_id).with_for_update().first()
            if not batch:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Batch {item.batch_id} no longer exists",
                )
            if batch.quantity != item.expected_quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Batch {batch.batch_number} changed after the count was recorded. "
                        "Create a new stock take for this batch."
                    ),
                )

            if item.variance_quantity == 0:
                continue

            product = db.query(Product).filter(Product.id == item.product_id).with_for_update().first()
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Product {item.product_id} no longer exists",
                )

            batch.quantity = item.counted_quantity
            stock_after = InventoryService.recalculate_product_stock(db, product)
            adjustment = StockAdjustment(
                product_id=product.id,
                batch_id=batch.id,
                adjustment_type=AdjustmentType.CORRECTION,
                quantity=abs(item.variance_quantity),
                reason=item.reason or f"Stock take {stock_take.reference}",
                performed_by=current_user.id,
            )
            db.add(adjustment)
            db.flush()
            InventoryService.record_movement(
                db,
                product_id=product.id,
                batch_id=batch.id,
                movement_type=InventoryMovementType.STOCK_CORRECTION,
                quantity_delta=item.variance_quantity,
                stock_after=stock_after,
                source_document_type="stock_take",
                source_document_id=stock_take.id,
                reason=adjustment.reason,
                created_by=current_user.id,
            )
            movement_count += 1
            total_variance += item.variance_quantity

        stock_take.status = StockTakeStatus.COMPLETED
        stock_take.completed_by = current_user.id
        stock_take.completed_at = datetime.now(timezone.utc)
        if payload.notes:
            stock_take.notes = payload.notes

        SyncOutboxService.record_event(
            db,
            event_type=SyncEventType.STOCK_TAKE_COMPLETED,
            aggregate_type="stock_take",
            aggregate_id=stock_take.id,
            organization_id=stock_take.organization_id,
            branch_id=stock_take.branch_id,
            source_device_id=stock_take.source_device_id,
            payload={
                "stock_take_id": stock_take.id,
                "reference": stock_take.reference,
                "movement_count": movement_count,
                "total_variance": total_variance,
                "line_count": len(stock_take.items),
                "completed_by": current_user.id,
            },
        )
        AuditService.log(
            db,
            action="complete_stock_take",
            user_id=current_user.id,
            entity_type="stock_take",
            entity_id=stock_take.id,
            description=f"Completed stock take {stock_take.reference}",
            extra_data={
                "movement_count": movement_count,
                "total_variance": total_variance,
                "line_count": len(stock_take.items),
            },
        )
        db.commit()
        db.refresh(stock_take)
        return stock_take
    except Exception:
        db.rollback()
        raise
