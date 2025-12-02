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
        func.sum(SaleItem.total_price).label("total_revenue"),
        func.sum(SaleItem.quantity).label("total_quantity")
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

    category_profits = []
    for r in results:
        # Calculate profit for this category
        category_profit = 0.0
        category_sales = db.query(SaleItem).join(
            Product, Product.id == SaleItem.product_id
        ).join(
            Sale, Sale.id == SaleItem.sale_id
        ).filter(
            Product.category_id == r.id,
            Sale.created_at >= start_date
        ).all()

        for item in category_sales:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            if product:
                profit = (item.unit_price - product.cost_price) * item.quantity
                category_profit += profit

        profit_margin = (category_profit / float(r.total_revenue) * 100) if r.total_revenue > 0 else 0

        category_profits.append({
            "category_id": r.id,
            "category_name": r.name,
            "total_revenue": float(r.total_revenue),
            "total_profit": category_profit,
            "profit_margin": profit_margin,
            "items_sold": r.total_quantity,
        })

    return sorted(category_profits, key=lambda x: x["total_profit"], reverse=True)


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

    # Daily revenue
    daily_sales = db.query(Sale).filter(Sale.created_at >= today_start).all()
    daily_revenue = sum(sale.total_amount for sale in daily_sales)

    # Weekly revenue
    weekly_sales = db.query(Sale).filter(Sale.created_at >= week_start).all()
    weekly_revenue = sum(sale.total_amount for sale in weekly_sales)

    # Monthly revenue
    monthly_sales = db.query(Sale).filter(Sale.created_at >= month_start).all()
    monthly_revenue = sum(sale.total_amount for sale in monthly_sales)

    # Average basket value
    avg_basket = daily_revenue / len(daily_sales) if daily_sales else 0.0

    return {
        "daily_revenue": daily_revenue,
        "daily_transactions": len(daily_sales),
        "weekly_revenue": weekly_revenue,
        "weekly_transactions": len(weekly_sales),
        "monthly_revenue": monthly_revenue,
        "monthly_transactions": len(monthly_sales),
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

    # Get all sales in period
    sales = db.query(Sale).filter(Sale.created_at >= start_date).all()

    total_revenue = sum(sale.total_amount for sale in sales)

    # Calculate gross profit
    gross_profit = 0.0
    for sale in sales:
        for item in sale.items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            if product:
                profit = (item.unit_price - product.cost_price) * item.quantity
                gross_profit += profit

    # Net profit (simplified - just subtracting estimated overhead)
    overhead_rate = 0.15  # 15% overhead estimate
    net_profit = gross_profit * (1 - overhead_rate)

    # Average basket value
    avg_basket = total_revenue / len(sales) if sales else 0.0

    # Credit sales (sales with payment method = credit)
    credit_sales = db.query(Sale).filter(
        Sale.created_at >= start_date,
        Sale.payment_method == "credit"
    ).all()
    outstanding_credit = sum(sale.total_amount for sale in credit_sales)

    return {
        "total_revenue": total_revenue,
        "gross_profit": gross_profit,
        "net_profit": net_profit,
        "profit_margin": (gross_profit / total_revenue * 100) if total_revenue > 0 else 0,
        "average_basket_value": avg_basket,
        "total_transactions": len(sales),
        "outstanding_credit": outstanding_credit,
        "credit_sales_count": len(credit_sales),
    }  