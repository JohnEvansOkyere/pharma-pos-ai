"""
Sales/POS API endpoints.
"""
from decimal import Decimal
from uuid import uuid4
from typing import List, Optional
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.money import round_money, to_decimal
from app.db.base import get_db
from app.models.sale import (
    PaymentMethod,
    Sale,
    SaleItem,
    SalePricingMode,
    SaleReversal,
    SaleReversalType,
    SaleStatus,
)
from app.models.product import Product, ProductBatch
from app.models.stock_adjustment import StockAdjustment, AdjustmentType
from app.models.inventory_movement import InventoryMovementType
from app.models.sync_event import SyncEventType
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.inventory_service import InventoryService
from app.services.sync_outbox_service import SyncOutboxService
from app.schemas.sale import (
    Sale as SaleSchema,
    SaleActionRequest,
    SaleCreate,
    EndOfDayCloseout,
    SaleWithItems,
    SaleSummary,
)
from app.api.dependencies import get_current_active_user, require_refund_sale, require_view_reports, require_void_sale

router = APIRouter(prefix="/sales", tags=["Sales"])


def _resolve_sale_unit_price(product: Product, pricing_mode: SalePricingMode) -> Decimal:
    if pricing_mode == SalePricingMode.WHOLESALE:
        if product.wholesale_price is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product {product.name} has no wholesale price configured",
            )
        return round_money(product.wholesale_price)

    return round_money(product.selling_price)

def _allocate_product_batches(db: Session, product: Product, required_quantity: int) -> List[ProductBatch]:
    """
    Allocate sale quantity from available batches using FEFO.

    Returns a list containing the same ProductBatch object repeated in the
    order it should be consumed. The caller is responsible for decrementing
    quantities.
    """
    available_batches = InventoryService.sellable_batches_query(db, product.id).with_for_update().order_by(
        ProductBatch.expiry_date.asc(),
        ProductBatch.received_date.asc(),
        ProductBatch.id.asc(),
    ).all()

    allocated_batches: List[ProductBatch] = []
    remaining_quantity = required_quantity

    for batch in available_batches:
        if remaining_quantity <= 0:
            break

        take_quantity = min(batch.quantity, remaining_quantity)
        if take_quantity > 0:
            allocated_batches.extend([batch] * take_quantity)
            remaining_quantity -= take_quantity

    if remaining_quantity > 0:
        available_quantity = required_quantity - remaining_quantity
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Insufficient sellable stock for product {product.name}. "
                f"Available in valid batches: {available_quantity}"
            ),
        )

    return allocated_batches


def _restore_sale_item_stock(
    db: Session,
    sale_item: SaleItem,
    *,
    performed_by: int,
    reason: str,
) -> None:
    product = db.query(Product).filter(Product.id == sale_item.product_id).with_for_update().first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot reverse sale because product {sale_item.product_id} no longer exists",
        )

    batch = None
    if sale_item.batch_number:
        batch = db.query(ProductBatch).filter(
            ProductBatch.product_id == sale_item.product_id,
            ProductBatch.batch_number == sale_item.batch_number,
            ProductBatch.expiry_date == sale_item.expiry_date,
        ).with_for_update().first()

    if batch is None:
        batch = ProductBatch(
            product_id=sale_item.product_id,
            batch_number=sale_item.batch_number or f"RESTORED-SALE-{sale_item.sale_id}-{sale_item.id}",
            quantity=0,
            expiry_date=sale_item.expiry_date or (date.today() + timedelta(days=3650)),
            cost_price=product.cost_price,
            location="Restored from sale reversal",
        )
        db.add(batch)
        db.flush()

    batch.quantity += sale_item.quantity
    stock_after = InventoryService.recalculate_product_stock(db, product)
    stock_adjustment = StockAdjustment(
        product_id=product.id,
        batch_id=batch.id,
        adjustment_type=AdjustmentType.RETURN,
        quantity=sale_item.quantity,
        reason=reason,
        performed_by=performed_by,
    )
    db.add(stock_adjustment)
    db.flush()
    InventoryService.record_movement(
        db,
        product_id=product.id,
        batch_id=batch.id,
        movement_type=InventoryMovementType.SALE_REVERSED,
        quantity_delta=sale_item.quantity,
        stock_after=stock_after,
        source_document_type="stock_adjustment",
        source_document_id=stock_adjustment.id,
        reason=reason,
        created_by=performed_by,
    )


def _reverse_sale(
    db: Session,
    *,
    sale_id: int,
    action_reason: str,
    current_user: User,
    target_status: SaleStatus,
) -> Sale:
    try:
        sale = db.query(Sale).filter(Sale.id == sale_id).with_for_update().first()
        if not sale:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sale not found",
            )

        if sale.status != SaleStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only completed sales can be reversed",
            )

        reason = action_reason.strip()
        if not reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reason is required",
            )

        restored_quantity = sum(item.quantity for item in sale.items)
        restored_items = [
            {
                "product_id": item.product_id,
                "product_name": item.product_name,
                "batch_number": item.batch_number,
                "expiry_date": item.expiry_date,
                "quantity": item.quantity,
            }
            for item in sale.items
        ]
        reversal_type = (
            SaleReversalType.REFUND
            if target_status == SaleStatus.REFUNDED
            else SaleReversalType.VOID
        )
        reversal = SaleReversal(
            sale_id=sale.id,
            reversal_type=reversal_type,
            reason=reason,
            total_amount=round_money(sale.total_amount),
            restored_quantity=restored_quantity,
            performed_by=current_user.id,
        )
        db.add(reversal)
        db.flush()

        for sale_item in sale.items:
            _restore_sale_item_stock(
                db,
                sale_item,
                performed_by=current_user.id,
                reason=f"{target_status.value}: {reason}",
            )

        sale.status = target_status
        SyncOutboxService.record_event(
            db,
            event_type=SyncEventType.SALE_REVERSED,
            aggregate_type="sale",
            aggregate_id=sale.id,
            organization_id=sale.organization_id,
            branch_id=sale.branch_id,
            source_device_id=sale.source_device_id,
            payload={
                "sale_id": sale.id,
                "invoice_number": sale.invoice_number,
                "status": target_status.value,
                "reversal_id": reversal.id,
                "reversal_type": reversal.reversal_type.value,
                "reason": reason,
                "total_amount": reversal.total_amount,
                "restored_quantity": restored_quantity,
                "items": restored_items,
                "performed_by": current_user.id,
            },
        )
        AuditService.log(
            db,
            action=f"{target_status.value}_sale",
            user_id=current_user.id,
            entity_type="sale",
            entity_id=sale.id,
            description=f"{target_status.value.title()} sale {sale.invoice_number}",
            extra_data={
                "invoice_number": sale.invoice_number,
                "reason": reason,
                "reversal_id": reversal.id,
                "reversal_type": reversal.reversal_type.value,
                "restored_items": restored_quantity,
                "total_amount": reversal.total_amount,
            },
        )
        db.commit()
        db.refresh(sale)
        return sale
    except Exception:
        db.rollback()
        raise


@router.post("", response_model=SaleWithItems, status_code=status.HTTP_201_CREATED)
def create_sale(
    sale_data: SaleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new sale transaction.

    Args:
        sale_data: Sale data with items
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created sale with items

    Raises:
        HTTPException: If product not found or insufficient stock
    """
    try:
        # Calculate totals
        subtotal = Decimal("0.00")
        sale_items_data = []

        for item in sale_data.items:
            # Lock the product row first to keep stock checks and updates
            # consistent across concurrent tills.
            product = db.query(Product).filter(Product.id == item.product_id).with_for_update().first()
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product with ID {item.product_id} not found"
                )

            if not product.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Product {product.name} is inactive and cannot be sold"
                )

            InventoryService.recalculate_product_stock(db, product)
            if product.total_stock < item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient stock for product {product.name}. Available: {product.total_stock}"
                )

            allocated_batches = _allocate_product_batches(db, product, item.quantity)
            unit_price = _resolve_sale_unit_price(product, sale_data.pricing_mode)
            line_discount = round_money(item.discount_amount)
            quantity_remaining = item.quantity
            discount_remaining = line_discount

            # Group repeated batch allocations back into per-batch sale lines.
            batch_quantities: List[tuple[ProductBatch, int]] = []
            for batch in allocated_batches:
                if batch_quantities and batch_quantities[-1][0].id == batch.id:
                    existing_batch, existing_quantity = batch_quantities[-1]
                    batch_quantities[-1] = (existing_batch, existing_quantity + 1)
                else:
                    batch_quantities.append((batch, 1))

            for batch, batch_quantity in batch_quantities:
                batch_quantity_decimal = Decimal(batch_quantity)
                batch_discount = Decimal("0.00")
                if line_discount > 0:
                    if quantity_remaining == batch_quantity:
                        batch_discount = discount_remaining
                    else:
                        batch_discount = (
                            line_discount * batch_quantity_decimal / Decimal(item.quantity)
                        )
                        if batch_discount > discount_remaining:
                            batch_discount = discount_remaining

                batch_total = round_money((unit_price * batch_quantity_decimal) - batch_discount)
                subtotal += batch_total

                sale_items_data.append({
                    "product_id": item.product_id,
                    "product_name": product.name,
                    "dosage_form": product.dosage_form.value if product.dosage_form else None,
                    "strength": product.strength,
                    "batch_number": batch.batch_number,
                    "expiry_date": batch.expiry_date,
                    "quantity": batch_quantity,
                    "unit_price": round_money(unit_price),
                    "discount_amount": round_money(batch_discount),
                    "total_price": round_money(batch_total),
                    "allocated_batch": batch,
                    "product": product,
                })

                quantity_remaining -= batch_quantity
                discount_remaining -= batch_discount

        # Calculate final total
        total_amount_decimal = (
            subtotal
            - round_money(sale_data.discount_amount)
            + round_money(sale_data.tax_amount)
        )
        total_amount = round_money(total_amount_decimal)
        amount_paid = round_money(sale_data.amount_paid)

        # Validate payment
        if amount_paid < total_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient payment. Total: {total_amount}, Paid: {amount_paid}"
            )

        change_amount = round_money(amount_paid - total_amount)

        # Use the database-assigned sale id to derive a transaction-safe invoice.
        db_sale = Sale(
            invoice_number=f"PENDING-{uuid4().hex}",
            user_id=current_user.id,
            pricing_mode=sale_data.pricing_mode,
            subtotal=round_money(subtotal),
            discount_amount=round_money(sale_data.discount_amount),
            tax_amount=round_money(sale_data.tax_amount),
            total_amount=total_amount,
            payment_method=sale_data.payment_method,
            amount_paid=amount_paid,
            change_amount=change_amount,
            customer_name=sale_data.customer_name,
            customer_phone=sale_data.customer_phone,
            notes=sale_data.notes,
        )

        db.add(db_sale)
        db.flush()  # Get sale ID from the database
        db_sale.invoice_number = f"INV-{datetime.now().strftime('%Y%m%d')}-{db_sale.id:06d}"

        # Create sale items and update stock
        touched_products = {}
        movement_records = []
        for item_data in sale_items_data:
            allocated_batch = item_data.pop("allocated_batch")
            product = item_data.pop("product")
            sale_item = SaleItem(sale_id=db_sale.id, **item_data)
            db.add(sale_item)

            allocated_batch.quantity -= item_data["quantity"]
            touched_products[product.id] = product
            movement_records.append(
                {
                    "product": product,
                    "batch_id": allocated_batch.id,
                    "quantity": item_data["quantity"],
                    "reason": f"Sale {db_sale.invoice_number}",
                }
            )

        for product in touched_products.values():
            InventoryService.recalculate_product_stock(db, product)

        for record in movement_records:
            product = record["product"]
            InventoryService.record_movement(
                db,
                product_id=product.id,
                batch_id=record["batch_id"],
                movement_type=InventoryMovementType.SALE_DISPENSED,
                quantity_delta=-record["quantity"],
                stock_after=product.total_stock,
                source_document_type="sale",
                source_document_id=db_sale.id,
                reason=record["reason"],
                created_by=current_user.id,
            )

        SyncOutboxService.record_event(
            db,
            event_type=SyncEventType.SALE_CREATED,
            aggregate_type="sale",
            aggregate_id=db_sale.id,
            organization_id=db_sale.organization_id,
            branch_id=db_sale.branch_id,
            source_device_id=db_sale.source_device_id,
            payload={
                "sale_id": db_sale.id,
                "invoice_number": db_sale.invoice_number,
                "pricing_mode": db_sale.pricing_mode.value,
                "payment_method": db_sale.payment_method.value,
                "subtotal": db_sale.subtotal,
                "discount_amount": db_sale.discount_amount,
                "tax_amount": db_sale.tax_amount,
                "total_amount": db_sale.total_amount,
                "user_id": current_user.id,
                "items": [
                    {
                        "product_id": item["product_id"],
                        "batch_number": item["batch_number"],
                        "expiry_date": item["expiry_date"],
                        "quantity": item["quantity"],
                        "unit_price": item["unit_price"],
                        "total_price": item["total_price"],
                    }
                    for item in sale_items_data
                ],
            },
        )
        AuditService.log(
            db,
            action="create_sale",
            user_id=current_user.id,
            entity_type="sale",
            entity_id=db_sale.id,
            description=f"Completed sale {db_sale.invoice_number}",
            extra_data={
                "invoice_number": db_sale.invoice_number,
                "total_amount": db_sale.total_amount,
                "item_lines": len(sale_items_data),
                "pricing_mode": db_sale.pricing_mode.value,
            },
        )
        db.commit()
        db.refresh(db_sale)
        return db_sale
    except Exception:
        db.rollback()
        raise


@router.get("", response_model=List[SaleWithItems])
def list_sales(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List sales with pagination and date filtering.

    Args:
        skip: Number of records to skip
        limit: Maximum records to return
        start_date: Filter by start date
        end_date: Filter by end date
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of sales with items
    """
    query = db.query(Sale)

    if start_date:
        query = query.filter(func.date(Sale.created_at) >= start_date)

    if end_date:
        query = query.filter(func.date(Sale.created_at) <= end_date)

    sales = query.order_by(Sale.created_at.desc()).offset(skip).limit(limit).all()
    return sales


@router.get("/summary/today", response_model=SaleSummary)
def get_today_sales_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get today's sales summary.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        Sales summary with totals
    """
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    sales_stats = db.query(
        func.count(Sale.id).label("total_sales"),
        func.coalesce(func.sum(Sale.total_amount), 0).label("total_revenue"),
    ).filter(Sale.created_at >= today_start).one()

    total_items_sold = db.query(
        func.coalesce(func.sum(SaleItem.quantity), 0)
    ).join(
        Sale, Sale.id == SaleItem.sale_id
    ).filter(
        Sale.created_at >= today_start
    ).scalar() or 0

    total_profit = db.query(
        func.coalesce(func.sum((SaleItem.unit_price - Product.cost_price) * SaleItem.quantity), 0)
    ).join(
        Sale, Sale.id == SaleItem.sale_id
    ).join(
        Product, Product.id == SaleItem.product_id
    ).filter(
        Sale.created_at >= today_start
    ).scalar() or 0

    return {
        "total_sales": int(sales_stats.total_sales or 0),
        "total_revenue": float(to_decimal(sales_stats.total_revenue)),
        "total_profit": float(to_decimal(total_profit)),
        "total_items_sold": int(total_items_sold),
    }


@router.get("/summary/closeout", response_model=EndOfDayCloseout)
def get_end_of_day_closeout(
    business_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_view_reports),
):
    closeout_date = business_date or date.today()

    status_rows = db.query(
        Sale.status,
        func.count(Sale.id).label("count"),
        func.coalesce(func.sum(Sale.total_amount), 0).label("amount"),
    ).filter(
        func.date(Sale.created_at) == closeout_date
    ).group_by(
        Sale.status
    ).all()

    status_totals = {
        row.status: {"count": int(row.count or 0), "amount": float(to_decimal(row.amount))}
        for row in status_rows
    }

    payment_rows = db.query(
        Sale.payment_method,
        func.coalesce(func.sum(Sale.total_amount), 0).label("amount"),
    ).filter(
        func.date(Sale.created_at) == closeout_date,
        Sale.status == SaleStatus.COMPLETED,
    ).group_by(
        Sale.payment_method
    ).all()

    payment_totals = {
        row.payment_method: float(to_decimal(row.amount))
        for row in payment_rows
    }

    return {
        "business_date": closeout_date,
        "completed_sales_count": status_totals.get(SaleStatus.COMPLETED, {}).get("count", 0),
        "refunded_sales_count": status_totals.get(SaleStatus.REFUNDED, {}).get("count", 0),
        "cancelled_sales_count": status_totals.get(SaleStatus.CANCELLED, {}).get("count", 0),
        "completed_revenue": status_totals.get(SaleStatus.COMPLETED, {}).get("amount", 0.0),
        "refunded_revenue": status_totals.get(SaleStatus.REFUNDED, {}).get("amount", 0.0),
        "cancelled_revenue": status_totals.get(SaleStatus.CANCELLED, {}).get("amount", 0.0),
        "cash_revenue": payment_totals.get(PaymentMethod.CASH, 0.0),
        "momo_revenue": payment_totals.get(PaymentMethod.MOMO, 0.0),
        "card_revenue": payment_totals.get(PaymentMethod.CARD, 0.0),
        "bank_transfer_revenue": payment_totals.get(PaymentMethod.BANK_TRANSFER, 0.0),
        "credit_revenue": payment_totals.get(PaymentMethod.CREDIT, 0.0),
    }


@router.post("/{sale_id}/void", response_model=SaleWithItems)
def void_sale(
    sale_id: int,
    payload: SaleActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_void_sale),
):
    return _reverse_sale(
        db,
        sale_id=sale_id,
        action_reason=payload.reason,
        current_user=current_user,
        target_status=SaleStatus.CANCELLED,
    )


@router.post("/{sale_id}/refund", response_model=SaleWithItems)
def refund_sale(
    sale_id: int,
    payload: SaleActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_refund_sale),
):
    return _reverse_sale(
        db,
        sale_id=sale_id,
        action_reason=payload.reason,
        current_user=current_user,
        target_status=SaleStatus.REFUNDED,
    )


@router.get("/{sale_id}", response_model=SaleWithItems)
def get_sale(
    sale_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a specific sale by ID with items.

    Args:
        sale_id: Sale ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Sale with items

    Raises:
        HTTPException: If sale not found
    """
    sale = db.query(Sale).filter(Sale.id == sale_id).first()
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale not found"
        )
    return sale
