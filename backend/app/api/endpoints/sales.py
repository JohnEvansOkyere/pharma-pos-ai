"""
Sales/POS API endpoints.
"""
from typing import List, Optional
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.base import get_db
from app.models.sale import Sale, SaleItem
from app.models.product import Product
from app.models.user import User
from app.schemas.sale import (
    Sale as SaleSchema,
    SaleCreate,
    SaleWithItems,
    SaleSummary,
)
from app.api.dependencies import get_current_active_user

router = APIRouter(prefix="/sales", tags=["Sales"])


def generate_invoice_number(db: Session) -> str:
    """
    Generate a unique invoice number.

    Args:
        db: Database session

    Returns:
        Invoice number in format INV-YYYYMMDD-XXXX
    """
    today = datetime.now().strftime("%Y%m%d")
    prefix = f"INV-{today}-"

    # Get count of sales today
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    count = db.query(Sale).filter(Sale.created_at >= today_start).count()

    return f"{prefix}{count + 1:04d}"


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
    # Calculate totals
    subtotal = 0.0
    sale_items_data = []

    for item in sale_data.items:
        # Verify product exists and has sufficient stock
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with ID {item.product_id} not found"
            )

        if product.total_stock < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock for product {product.name}. Available: {product.total_stock}"
            )

        # Calculate item total
        item_total = (item.unit_price * item.quantity) - item.discount_amount
        subtotal += item_total

        sale_items_data.append({
            "product_id": item.product_id,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "discount_amount": item.discount_amount,
            "total_price": item_total,
        })

    # Calculate final total
    total_amount = subtotal - sale_data.discount_amount + sale_data.tax_amount

    # Validate payment
    if sale_data.amount_paid < total_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient payment. Total: {total_amount}, Paid: {sale_data.amount_paid}"
        )

    change_amount = sale_data.amount_paid - total_amount

    # Generate invoice number
    invoice_number = generate_invoice_number(db)

    # Create sale
    db_sale = Sale(
        invoice_number=invoice_number,
        user_id=current_user.id,
        subtotal=subtotal,
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
    db.flush()  # Get sale ID

    # Create sale items and update stock
    for item_data in sale_items_data:
        sale_item = SaleItem(sale_id=db_sale.id, **item_data)
        db.add(sale_item)

        # Reduce product stock
        product = db.query(Product).filter(Product.id == item_data["product_id"]).first()
        product.total_stock -= item_data["quantity"]

    db.commit()
    db.refresh(db_sale)

    return db_sale


@router.get("", response_model=List[SaleSchema])
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
        List of sales
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
