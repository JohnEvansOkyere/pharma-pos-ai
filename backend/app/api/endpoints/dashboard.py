"""
Dashboard API endpoints for KPIs and analytics.
"""
from typing import List, Dict, Any
from datetime import datetime, timedelta, date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.base import get_db
from app.models.sale import Sale, SaleItem
from app.models.product import Product, ProductBatch
from app.models.user import User
from app.api.dependencies import get_current_active_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/kpis")
def get_dashboard_kpis(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get dashboard KPIs.

    Returns:
        Dictionary with key performance indicators
    """
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Total sales today
    today_sales = db.query(Sale).filter(Sale.created_at >= today_start).all()
    total_sales_today = sum(sale.total_amount for sale in today_sales)

    # Profit today
    total_profit_today = 0.0
    for sale in today_sales:
        for item in sale.items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            if product:
                profit = (item.unit_price - product.cost_price) * item.quantity
                total_profit_today += profit

    # Inventory value
    products = db.query(Product).filter(Product.is_active == True).all()
    inventory_value = sum(p.cost_price * p.total_stock for p in products)

    # Items near expiry (next 30 days)
    expiry_threshold = date.today() + timedelta(days=30)
    near_expiry_count = db.query(ProductBatch).filter(
        ProductBatch.expiry_date <= expiry_threshold,
        ProductBatch.expiry_date >= date.today(),
        ProductBatch.quantity > 0
    ).count()

    # Low stock items
    low_stock_count = db.query(Product).filter(
        Product.total_stock <= Product.low_stock_threshold,
        Product.is_active == True
    ).count()

    # Total products
    total_products = db.query(Product).filter(Product.is_active == True).count()

    # Total sales count
    total_sales_count = len(today_sales)

    return {
        "total_sales_today": total_sales_today,
        "profit_today": total_profit_today,
        "inventory_value": inventory_value,
        "items_near_expiry": near_expiry_count,
        "low_stock_items": low_stock_count,
        "total_products": total_products,
        "total_sales_count": total_sales_count,
    }


@router.get("/fast-moving-products")
def get_fast_moving_products(
    limit: int = 10,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """
    Get fast-moving products based on sales volume.

    Args:
        limit: Number of products to return
        days: Number of days to analyze
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of top-selling products
    """
    start_date = datetime.now() - timedelta(days=days)

    results = db.query(
        Product.id,
        Product.name,
        Product.sku,
        func.sum(SaleItem.quantity).label("total_sold"),
        func.sum(SaleItem.total_price).label("total_revenue")
    ).join(
        SaleItem, SaleItem.product_id == Product.id
    ).join(
        Sale, Sale.id == SaleItem.sale_id
    ).filter(
        Sale.created_at >= start_date
    ).group_by(
        Product.id, Product.name, Product.sku
    ).order_by(
        func.sum(SaleItem.quantity).desc()
    ).limit(limit).all()

    return [
        {
            "product_id": r.id,
            "product_name": r.name,
            "sku": r.sku,
            "total_sold": r.total_sold,
            "total_revenue": float(r.total_revenue),
        }
        for r in results
    ]


@router.get("/slow-moving-products")
def get_slow_moving_products(
    limit: int = 10,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """
    Get slow-moving products with low sales.

    Args:
        limit: Number of products to return
        days: Number of days to analyze
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of slow-moving products
    """
    start_date = datetime.now() - timedelta(days=days)

    # Get all active products
    all_products = db.query(Product).filter(Product.is_active == True).all()

    # Get sales data
    sales_data = db.query(
        SaleItem.product_id,
        func.sum(SaleItem.quantity).label("total_sold")
    ).join(
        Sale, Sale.id == SaleItem.sale_id
    ).filter(
        Sale.created_at >= start_date
    ).group_by(
        SaleItem.product_id
    ).all()

    sales_dict = {item.product_id: item.total_sold for item in sales_data}

    # Find products with low sales
    slow_movers = []
    for product in all_products:
        total_sold = sales_dict.get(product.id, 0)
        slow_movers.append({
            "product_id": product.id,
            "product_name": product.name,
            "sku": product.sku,
            "total_sold": total_sold,
            "current_stock": product.total_stock,
        })

    # Sort by lowest sales
    slow_movers.sort(key=lambda x: x["total_sold"])

    return slow_movers[:limit]


@router.get("/sales-trend")
def get_sales_trend(
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """
    Get sales trend data for charts.

    Args:
        days: Number of days to analyze
        db: Database session
        current_user: Current authenticated user

    Returns:
        Daily sales data for the period
    """
    start_date = datetime.now() - timedelta(days=days)

    results = db.query(
        func.date(Sale.created_at).label("date"),
        func.count(Sale.id).label("sales_count"),
        func.sum(Sale.total_amount).label("total_revenue")
    ).filter(
        Sale.created_at >= start_date
    ).group_by(
        func.date(Sale.created_at)
    ).order_by(
        func.date(Sale.created_at)
    ).all()

    return [
        {
            "date": str(r.date),
            "sales_count": r.sales_count,
            "total_revenue": float(r.total_revenue) if r.total_revenue else 0.0,
        }
        for r in results
    ]


@router.get("/staff-performance")
def get_staff_performance(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """
    Get staff performance metrics.

    Args:
        days: Number of days to analyze
        db: Database session
        current_user: Current authenticated user

    Returns:
        Performance data for each staff member
    """
    start_date = datetime.now() - timedelta(days=days)

    results = db.query(
        User.id,
        User.full_name,
        User.username,
        func.count(Sale.id).label("total_sales"),
        func.sum(Sale.total_amount).label("total_revenue")
    ).join(
        Sale, Sale.user_id == User.id
    ).filter(
        Sale.created_at >= start_date
    ).group_by(
        User.id, User.full_name, User.username
    ).order_by(
        func.sum(Sale.total_amount).desc()
    ).all()

    return [
        {
            "user_id": r.id,
            "full_name": r.full_name,
            "username": r.username,
            "total_sales": r.total_sales,
            "total_revenue": float(r.total_revenue) if r.total_revenue else 0.0,
        }
        for r in results
    ]
