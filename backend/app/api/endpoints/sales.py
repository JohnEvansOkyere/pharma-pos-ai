"""
Sales/POS API endpoints.
"""
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from typing import List, Optional
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.base import get_db
from app.models.sale import Sale, SaleItem
from app.models.product import Product, ProductBatch
from app.models.user import User
from app.services.inventory_service import InventoryService
from app.schemas.sale import (
    Sale as SaleSchema,
    SaleCreate,
    SaleWithItems,
    SaleSummary,
)
from app.api.dependencies import get_current_active_user

router = APIRouter(prefix="/sales", tags=["Sales"])


def _round_money(value: Decimal) -> float:
    """Round currency values consistently for stored sale rows."""
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


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
            unit_price = Decimal(str(item.unit_price))
            line_discount = Decimal(str(item.discount_amount))
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
                        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        if batch_discount > discount_remaining:
                            batch_discount = discount_remaining

                batch_total = (unit_price * batch_quantity_decimal) - batch_discount
                subtotal += batch_total

                sale_items_data.append({
                    "product_id": item.product_id,
                    "product_name": product.name,
                    "dosage_form": product.dosage_form.value if product.dosage_form else None,
                    "strength": product.strength,
                    "batch_number": batch.batch_number,
                    "expiry_date": batch.expiry_date,
                    "quantity": batch_quantity,
                    "unit_price": float(unit_price),
                    "discount_amount": _round_money(batch_discount),
                    "total_price": _round_money(batch_total),
                    "allocated_batch": batch,
                    "product": product,
                })

                quantity_remaining -= batch_quantity
                discount_remaining -= batch_discount

        # Calculate final total
        total_amount_decimal = (
            subtotal
            - Decimal(str(sale_data.discount_amount))
            + Decimal(str(sale_data.tax_amount))
        )
        total_amount = _round_money(total_amount_decimal)

        # Validate payment
        if sale_data.amount_paid < total_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient payment. Total: {total_amount}, Paid: {sale_data.amount_paid}"
            )

        change_amount = sale_data.amount_paid - total_amount

        # Use the database-assigned sale id to derive a transaction-safe invoice.
        db_sale = Sale(
            invoice_number=f"PENDING-{uuid4().hex}",
            user_id=current_user.id,
            subtotal=_round_money(subtotal),
            discount_amount=sale_data.discount_amount,
            tax_amount=sale_data.tax_amount,
            total_amount=total_amount,
            payment_method=sale_data.payment_method,
            amount_paid=sale_data.amount_paid,
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
        for item_data in sale_items_data:
            allocated_batch = item_data.pop("allocated_batch")
            product = item_data.pop("product")
            sale_item = SaleItem(sale_id=db_sale.id, **item_data)
            db.add(sale_item)

            allocated_batch.quantity -= item_data["quantity"]
            touched_products[product.id] = product

        for product in touched_products.values():
            InventoryService.recalculate_product_stock(db, product)

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

    # Get today's sales
    sales = db.query(Sale).filter(Sale.created_at >= today_start).all()

    total_revenue = sum(sale.total_amount for sale in sales)
    total_items_sold = sum(
        item.quantity
        for sale in sales
        for item in sale.items
    )

    # Calculate profit (selling_price - cost_price) * quantity
    total_profit = 0.0
    for sale in sales:
        for item in sale.items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            if product:
                profit_per_item = (item.unit_price - product.cost_price) * item.quantity
                total_profit += profit_per_item

    return {
        "total_sales": len(sales),
        "total_revenue": total_revenue,
        "total_profit": total_profit,
        "total_items_sold": total_items_sold,
    }


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
