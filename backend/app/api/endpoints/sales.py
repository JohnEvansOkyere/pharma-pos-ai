"""
Sales/POS API endpoints.
"""
from decimal import Decimal
from uuid import uuid4
from typing import List, Optional
from datetime import datetime, date, timedelta, timezone
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
from app.models.customer import Customer
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
from app.core.app_mode import apply_tenant_scope, require_online_tenant_scope, scope_query_to_user
from app.core.config import settings
from app.services import customer_retention_service as retention

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


def _resolve_sale_customer(
    db: Session,
    customer_id: Optional[int],
    current_user: User,
) -> Optional[Customer]:
    """Return an active customer owned by the cashier's organization and branch."""
    if customer_id is None:
        return None

    if current_user.organization_id is None or current_user.branch_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must be assigned to an organization and branch to link a customer",
        )

    customer = (
        db.query(Customer)
        .filter(
            Customer.id == customer_id,
            Customer.organization_id == current_user.organization_id,
            Customer.branch_id == current_user.branch_id,
            Customer.is_active.is_(True),
        )
        .first()
    )
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active customer not found for this organization and branch",
        )
    return customer


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
            organization_id=sale_item.organization_id,
            branch_id=sale_item.branch_id,
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
        organization_id=sale_item.organization_id,
        branch_id=sale_item.branch_id,
        source_device_id=sale_item.sale.source_device_id,
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
        organization_id=stock_adjustment.organization_id,
        branch_id=stock_adjustment.branch_id,
        source_device_id=stock_adjustment.source_device_id,
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
        sale_query = scope_query_to_user(
            db.query(Sale),
            Sale,
            current_user,
            app_mode=settings.APP_MODE,
        )
        sale = sale_query.filter(Sale.id == sale_id).with_for_update().first()
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
            organization_id=sale.organization_id,
            branch_id=sale.branch_id,
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
            organization_id=sale.organization_id,
            branch_id=sale.branch_id,
            source_device_id=sale.source_device_id,
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
        require_online_tenant_scope(current_user, app_mode=settings.APP_MODE)
        linked_customer = _resolve_sale_customer(
            db,
            getattr(sale_data, "customer_id", None),
            current_user,
        )

        # Calculate totals
        subtotal = Decimal("0.00")
        sale_items_data = []

        for item in sale_data.items:
            # Lock the product row first to keep stock checks and updates
            # consistent across concurrent tills.
            product_query = scope_query_to_user(
                db.query(Product),
                Product,
                current_user,
                app_mode=settings.APP_MODE,
            )
            product = product_query.filter(Product.id == item.product_id).with_for_update().first()
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

            # Catalog compliance flags are retained as metadata for this
            # deployment, but they do not block POS sales.

            # ── Stock validation ──

            InventoryService.recalculate_product_stock(db, product)
            if product.total_stock < item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient stock for product {product.name}. Available: {product.total_stock}"
                )

            allocated_batches = _allocate_product_batches(db, product, item.quantity)
            unit_price = _resolve_sale_unit_price(product, sale_data.pricing_mode)
            line_discount = round_money(item.discount_amount)

            # ── Reject item-level discount exceeding line subtotal (V2-P1-01) ──
            line_subtotal = unit_price * Decimal(item.quantity)
            if line_discount > line_subtotal:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Discount for '{product.name}' ({line_discount}) "
                        f"exceeds the line subtotal ({line_subtotal})"
                    ),
                )

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
                    "batch_id": batch.id,
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
        sale_level_discount = round_money(sale_data.discount_amount)
        if sale_level_discount > subtotal:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Sale-level discount ({sale_level_discount}) "
                    f"exceeds subtotal ({subtotal})"
                ),
            )

        total_amount_decimal = (
            subtotal
            - sale_level_discount
            + round_money(sale_data.tax_amount)
        )
        total_amount = round_money(total_amount_decimal)

        if total_amount < Decimal("0"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Total amount cannot be negative. Check discounts.",
            )

        amount_paid = round_money(sale_data.amount_paid)

        # Validate payment
        if amount_paid < total_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient payment. Total: {total_amount}, Paid: {amount_paid}"
            )

        change_amount = round_money(amount_paid - total_amount)

        # Use the database-assigned sale id to derive a transaction-safe invoice.
        sale_occurred_at = datetime.now(timezone.utc)
        db_sale = Sale(
            invoice_number=f"PENDING-{uuid4().hex}",
            user_id=current_user.id,
            pricing_mode=sale_data.pricing_mode,
            subtotal=round_money(subtotal),
            discount_amount=sale_level_discount,
            tax_amount=round_money(sale_data.tax_amount),
            total_amount=total_amount,
            payment_method=sale_data.payment_method,
            amount_paid=amount_paid,
            change_amount=change_amount,
            customer_id=linked_customer.id if linked_customer else None,
            customer_name=sale_data.customer_name,
            customer_phone=sale_data.customer_phone,
            customer_id_number=getattr(sale_data, 'customer_id_number', None),
            customer_address=getattr(sale_data, 'customer_address', None),
            momo_reference=getattr(sale_data, 'momo_reference', None),
            momo_number=getattr(sale_data, 'momo_number', None),
            prescription_number=getattr(sale_data, 'prescription_number', None),
            doctor_name=getattr(sale_data, 'doctor_name', None),
            has_prescription=getattr(sale_data, 'has_prescription', False),
            notes=sale_data.notes,
            created_at=sale_occurred_at,
        )

        # Tenant fields must be present before the first INSERT/flush.
        apply_tenant_scope(db_sale, current_user, app_mode=settings.APP_MODE)
        db.add(db_sale)
        db.flush()  # Get sale ID from the database
        db_sale.invoice_number = f"INV-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{db_sale.id:06d}"

        # Create sale items and update stock
        touched_products = {}
        movement_records = []
        for item_data in sale_items_data:
            allocated_batch = item_data["allocated_batch"]
            product = item_data["product"]
            sale_item_fields = {
                key: value
                for key, value in item_data.items()
                if key not in {"allocated_batch", "product", "batch_id"}
            }
            sale_item = SaleItem(sale_id=db_sale.id, **sale_item_fields)
            apply_tenant_scope(sale_item, current_user, app_mode=settings.APP_MODE)
            db.add(sale_item)

            allocated_batch.quantity -= item_data["quantity"]
            touched_products[product.id] = product
            movement_records.append(
                {
                    "product": product,
                    "batch_id": item_data["batch_id"],
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
                organization_id=db_sale.organization_id,
                branch_id=db_sale.branch_id,
                source_device_id=db_sale.source_device_id,
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
                "occurred_at": db_sale.created_at.isoformat() if db_sale.created_at else None,
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
                        "product_name": item["product_name"],
                        "sku": item["product"].sku,
                        "batch_id": item["batch_id"],
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
            organization_id=db_sale.organization_id,
            branch_id=db_sale.branch_id,
            source_device_id=db_sale.source_device_id,
        )
        db.commit()
        db.refresh(db_sale)

        # ── Customer retention: receipt + follow-up (non-fatal) ───────────
        if linked_customer:
            try:
                retention.dispatch_receipt(
                    db,
                    customer=linked_customer,
                    sale=db_sale,
                )
                retention.schedule_follow_up(
                    db,
                    customer=linked_customer,
                    sale=db_sale,
                )
                db.commit()
            except Exception as retention_err:
                import logging
                logging.getLogger(__name__).warning(
                    "Retention post-sale actions failed for sale %s: %s",
                    db_sale.invoice_number, retention_err,
                )

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
    query = scope_query_to_user(
        db.query(Sale),
        Sale,
        current_user,
        app_mode=settings.APP_MODE,
    )

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
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    sales_query = scope_query_to_user(
        db.query(
            func.count(Sale.id).label("total_sales"),
            func.coalesce(func.sum(Sale.total_amount), 0).label("total_revenue"),
        ),
        Sale,
        current_user,
        app_mode=settings.APP_MODE,
    )
    sales_stats = sales_query.filter(
        Sale.created_at >= today_start,
        Sale.status == SaleStatus.COMPLETED,
    ).one()

    items_query = db.query(
        func.coalesce(func.sum(SaleItem.quantity), 0)
    ).join(
        Sale, Sale.id == SaleItem.sale_id
    )
    items_query = scope_query_to_user(
        items_query,
        Sale,
        current_user,
        app_mode=settings.APP_MODE,
    )
    total_items_sold = items_query.filter(
        Sale.created_at >= today_start,
        Sale.status == SaleStatus.COMPLETED,
    ).scalar() or 0

    profit_query = db.query(
        func.coalesce(func.sum((SaleItem.unit_price - Product.cost_price) * SaleItem.quantity), 0)
    ).join(
        Sale, Sale.id == SaleItem.sale_id
    ).join(
        Product, Product.id == SaleItem.product_id
    )
    profit_query = scope_query_to_user(
        profit_query,
        Sale,
        current_user,
        app_mode=settings.APP_MODE,
    )
    total_profit = profit_query.filter(
        Sale.created_at >= today_start,
        Sale.status == SaleStatus.COMPLETED,
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

    status_query = db.query(
        Sale.status,
        func.count(Sale.id).label("count"),
        func.coalesce(func.sum(Sale.total_amount), 0).label("amount"),
    )
    status_query = scope_query_to_user(
        status_query,
        Sale,
        current_user,
        app_mode=settings.APP_MODE,
    )
    status_rows = status_query.filter(
        func.date(Sale.created_at) == closeout_date
    ).group_by(
        Sale.status
    ).all()

    status_totals = {
        row.status: {"count": int(row.count or 0), "amount": float(to_decimal(row.amount))}
        for row in status_rows
    }

    payment_query = db.query(
        Sale.payment_method,
        func.coalesce(func.sum(Sale.total_amount), 0).label("amount"),
    )
    payment_query = scope_query_to_user(
        payment_query,
        Sale,
        current_user,
        app_mode=settings.APP_MODE,
    )
    payment_rows = payment_query.filter(
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
    query = scope_query_to_user(
        db.query(Sale),
        Sale,
        current_user,
        app_mode=settings.APP_MODE,
    )
    sale = query.filter(Sale.id == sale_id).first()
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale not found"
        )
    return sale
