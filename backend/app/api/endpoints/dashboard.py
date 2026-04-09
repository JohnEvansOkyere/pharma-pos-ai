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


def _sum_or_zero(expression):
    return func.coalesce(func.sum(expression), 0.0)


def _count_or_zero(expression):
    return func.coalesce(func.count(expression), 0)


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

    sales_stats = db.query(
        _sum_or_zero(Sale.total_amount).label("total_sales_today"),
        _count_or_zero(Sale.id).label("total_sales_count"),
    ).filter(Sale.created_at >= today_start).one()

    total_profit_today = db.query(
        _sum_or_zero((SaleItem.unit_price - Product.cost_price) * SaleItem.quantity)
    ).join(
        Sale, Sale.id == SaleItem.sale_id
    ).join(
        Product, Product.id == SaleItem.product_id
    ).filter(
        Sale.created_at >= today_start
    ).scalar() or 0.0

    inventory_value = db.query(
        _sum_or_zero(Product.cost_price * Product.total_stock)
    ).filter(Product.is_active == True).scalar() or 0.0

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

    return {
        "total_sales_today": float(sales_stats.total_sales_today or 0.0),
        "profit_today": float(total_profit_today),
        "inventory_value": float(inventory_value),
        "items_near_expiry": near_expiry_count,
        "low_stock_items": low_stock_count,
        "total_products": total_products,
        "total_sales_count": int(sales_stats.total_sales_count or 0),
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

    sales_subquery = db.query(
        SaleItem.product_id,
        func.coalesce(func.sum(SaleItem.quantity), 0).label("total_sold")
    ).join(
        Sale, Sale.id == SaleItem.sale_id
    ).filter(
        Sale.created_at >= start_date
    ).group_by(
        SaleItem.product_id
    ).subquery()

    products = db.query(
        Product.id,
        Product.name,
        Product.sku,
        Product.total_stock,
        func.coalesce(sales_subquery.c.total_sold, 0).label("total_sold"),
    ).outerjoin(
        sales_subquery, sales_subquery.c.product_id == Product.id
    ).filter(
        Product.is_active == True
    ).order_by(
        func.coalesce(sales_subquery.c.total_sold, 0).asc(),
        Product.name.asc(),
    ).limit(limit).all()

    return [
        {
            "product_id": product.id,
            "product_name": product.name,
            "sku": product.sku,
            "total_sold": int(product.total_sold or 0),
            "current_stock": product.total_stock,
        }
        for product in products
    ]


@router.get("/low-stock-items")
def get_low_stock_items(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """
    Get products with low stock (at or below low stock threshold).

    Args:
        limit: Maximum number of products to return
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of low stock products with details
    """
    products = db.query(Product).filter(
        Product.is_active == True,
        Product.total_stock <= Product.low_stock_threshold
    ).order_by(
        Product.total_stock.asc()
    ).limit(limit).all()

    return [
        {
            "product_id": p.id,
            "product_name": p.name,
            "sku": p.sku,
            "dosage_form": p.dosage_form.value if p.dosage_form else None,
            "strength": p.strength,
            "current_stock": p.total_stock,
            "low_stock_threshold": p.low_stock_threshold,
            "reorder_level": p.reorder_level,
            "units_needed": max(0, p.reorder_level - p.total_stock),
            "status": "out_of_stock" if p.total_stock == 0 else "low_stock",
        }
        for p in products
    ]


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


@router.get("/expiring-products")
def get_expiring_products(
    days: int = 30,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """
    Get products expiring within specified days.

    Args:
        days: Number of days threshold (30, 60, or 90)
        limit: Maximum number of products to return
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of expiring products with details
    """
    expiry_threshold = date.today() + timedelta(days=days)

    results = db.query(
        Product.id,
        Product.name,
        Product.sku,
        Product.dosage_form,
        Product.strength,
        Product.total_stock,
        Product.selling_price,
        ProductBatch.batch_number,
        ProductBatch.quantity.label("batch_quantity"),
        ProductBatch.expiry_date,
        Product.cost_price
    ).join(
        ProductBatch, ProductBatch.product_id == Product.id
    ).filter(
        ProductBatch.expiry_date <= expiry_threshold,
        ProductBatch.expiry_date >= date.today(),
        ProductBatch.quantity > 0,
        ProductBatch.is_quarantined == False,
        Product.is_active == True
    ).order_by(
        ProductBatch.expiry_date.asc()
    ).limit(limit).all()

    return [
        {
            "product_id": r.id,
            "product_name": r.name,
            "sku": r.sku,
            "dosage_form": r.dosage_form.value if r.dosage_form else None,
            "strength": r.strength,
            "total_stock": r.total_stock,
            "batch_number": r.batch_number,
            "batch_quantity": r.batch_quantity,
            "expiry_date": str(r.expiry_date),
            "days_until_expiry": (r.expiry_date - date.today()).days,
            "value_at_risk": float(r.cost_price * r.batch_quantity),
        }
        for r in results
    ]


@router.get("/overstock-items")
def get_overstock_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """
    Get products with overstock (stock significantly above reorder level).

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of overstocked products
    """
    products = db.query(Product).filter(
        Product.is_active == True,
        Product.total_stock > Product.reorder_level * 3  # 3x reorder level
    ).all()

    return [
        {
            "product_id": p.id,
            "product_name": p.name,
            "sku": p.sku,
            "dosage_form": p.dosage_form.value if p.dosage_form else None,
            "strength": p.strength,
            "total_stock": p.total_stock,
            "reorder_level": p.reorder_level,
            "excess_stock": p.total_stock - p.reorder_level,
            "capital_tied": float(p.cost_price * p.total_stock),
        }
        for p in products
    ]


@router.get("/profit-by-category")
def get_profit_by_category(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """
    Get profit margins by product category.

    Args:
        days: Number of days to analyze
        db: Database session
        current_user: Current authenticated user

    Returns:
        Profit data by category
    """
    from app.models.category import Category

    start_date = datetime.now() - timedelta(days=days)

    results = db.query(
        Category.id,
        Category.name,
        _sum_or_zero(SaleItem.total_price).label("total_revenue"),
        _sum_or_zero((SaleItem.unit_price - Product.cost_price) * SaleItem.quantity).label("total_profit"),
        func.coalesce(func.sum(SaleItem.quantity), 0).label("total_quantity"),
    ).join(
        Product, Product.category_id == Category.id
    ).join(
        SaleItem, SaleItem.product_id == Product.id
    ).join(
        Sale, Sale.id == SaleItem.sale_id
    ).filter(
        Sale.created_at >= start_date
    ).group_by(
        Category.id, Category.name
    ).all()

    return sorted(
        [
            {
                "category_id": r.id,
                "category_name": r.name,
                "total_revenue": float(r.total_revenue or 0.0),
                "total_profit": float(r.total_profit or 0.0),
                "profit_margin": (
                    float(r.total_profit or 0.0) / float(r.total_revenue) * 100
                    if r.total_revenue and float(r.total_revenue) > 0
                    else 0.0
                ),
                "items_sold": int(r.total_quantity or 0),
            }
            for r in results
        ],
        key=lambda x: x["total_profit"],
        reverse=True,
    )


@router.get("/revenue-analysis")
def get_revenue_analysis(
    period: str = "daily",  # daily, weekly, monthly
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get revenue analysis for different periods.

    Args:
        period: Time period (daily, weekly, monthly)
        db: Database session
        current_user: Current authenticated user

    Returns:
        Revenue analysis data
    """
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    daily_stats = db.query(
        _sum_or_zero(Sale.total_amount).label("revenue"),
        _count_or_zero(Sale.id).label("transactions"),
    ).filter(Sale.created_at >= today_start).one()

    weekly_stats = db.query(
        _sum_or_zero(Sale.total_amount).label("revenue"),
        _count_or_zero(Sale.id).label("transactions"),
    ).filter(Sale.created_at >= week_start).one()

    monthly_stats = db.query(
        _sum_or_zero(Sale.total_amount).label("revenue"),
        _count_or_zero(Sale.id).label("transactions"),
    ).filter(Sale.created_at >= month_start).one()

    avg_basket = (
        float(daily_stats.revenue or 0.0) / int(daily_stats.transactions)
        if daily_stats.transactions
        else 0.0
    )

    return {
        "daily_revenue": float(daily_stats.revenue or 0.0),
        "daily_transactions": int(daily_stats.transactions or 0),
        "weekly_revenue": float(weekly_stats.revenue or 0.0),
        "weekly_transactions": int(weekly_stats.transactions or 0),
        "monthly_revenue": float(monthly_stats.revenue or 0.0),
        "monthly_transactions": int(monthly_stats.transactions or 0),
        "average_basket_value": avg_basket,
    }


@router.get("/financial-kpis")
def get_financial_kpis(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get comprehensive financial KPIs.

    Args:
        days: Number of days to analyze
        db: Database session
        current_user: Current authenticated user

    Returns:
        Financial KPI data
    """
    start_date = datetime.now() - timedelta(days=days)

    sales_stats = db.query(
        _sum_or_zero(Sale.total_amount).label("total_revenue"),
        _count_or_zero(Sale.id).label("total_transactions"),
    ).filter(Sale.created_at >= start_date).one()

    total_revenue = float(sales_stats.total_revenue or 0.0)

    gross_profit = db.query(
        _sum_or_zero((SaleItem.unit_price - Product.cost_price) * SaleItem.quantity)
    ).join(
        Sale, Sale.id == SaleItem.sale_id
    ).join(
        Product, Product.id == SaleItem.product_id
    ).filter(
        Sale.created_at >= start_date
    ).scalar() or 0.0

    # Net profit (simplified - just subtracting estimated overhead)
    overhead_rate = 0.15  # 15% overhead estimate
    net_profit = float(gross_profit) * (1 - overhead_rate)

    # Average basket value
    avg_basket = (
        total_revenue / int(sales_stats.total_transactions)
        if sales_stats.total_transactions
        else 0.0
    )

    # Credit sales (sales with payment method = credit)
    credit_stats = db.query(
        _sum_or_zero(Sale.total_amount).label("outstanding_credit"),
        _count_or_zero(Sale.id).label("credit_sales_count"),
    ).filter(
        Sale.created_at >= start_date,
        Sale.payment_method == "credit"
    ).one()

    return {
        "total_revenue": total_revenue,
        "gross_profit": float(gross_profit),
        "net_profit": net_profit,
        "profit_margin": (float(gross_profit) / total_revenue * 100) if total_revenue > 0 else 0,
        "average_basket_value": avg_basket,
        "total_transactions": int(sales_stats.total_transactions or 0),
        "outstanding_credit": float(credit_stats.outstanding_credit or 0.0),
        "credit_sales_count": int(credit_stats.credit_sales_count or 0),
    }
