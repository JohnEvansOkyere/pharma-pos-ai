"""
AI Insights service for rule-based analytics and predictions.
"""
from typing import Dict, List, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.product import Product
from app.models.sale import Sale, SaleItem
from app.core.config import settings


class AIInsightsService:
    """Service for AI-powered insights (rule-based)."""

    @staticmethod
    def detect_dead_stock(db: Session, days: int = None) -> List[Dict[str, Any]]:
        """
        Detect dead stock (products with no sales in specified days).

        Args:
            db: Database session
            days: Number of days to check (default from settings)

        Returns:
            List of dead stock products
        """
        if days is None:
            days = settings.DEAD_STOCK_DAYS

        start_date = datetime.now() - timedelta(days=days)

        # Get all active products
        all_products = db.query(Product).filter(Product.is_active == True).all()

        # Get products with sales in the period
        products_with_sales = db.query(SaleItem.product_id).join(
            Sale, Sale.id == SaleItem.sale_id
        ).filter(
            Sale.created_at >= start_date
        ).distinct().all()

        products_with_sales_ids = {p.product_id for p in products_with_sales}

        # Find dead stock
        dead_stock = []
        for product in all_products:
            if product.id not in products_with_sales_ids and product.total_stock > 0:
                dead_stock.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "sku": product.sku,
                    "current_stock": product.total_stock,
                    "stock_value": product.cost_price * product.total_stock,
                    "days_without_sale": days,
                })

        return dead_stock

    @staticmethod
    def suggest_reorder_quantity(
        db: Session,
        product_id: int,
        analysis_days: int = 30
    ) -> Dict[str, Any]:
        """
        Suggest reorder quantity based on sales velocity.

        Args:
            db: Database session
            product_id: Product ID
            analysis_days: Days to analyze for trend

        Returns:
            Reorder suggestion with reasoning
        """
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return {"error": "Product not found"}

        start_date = datetime.now() - timedelta(days=analysis_days)

        # Get total quantity sold in the period
        total_sold = db.query(func.sum(SaleItem.quantity)).join(
            Sale, Sale.id == SaleItem.sale_id
        ).filter(
            SaleItem.product_id == product_id,
            Sale.created_at >= start_date
        ).scalar() or 0

        # Calculate daily average
        daily_avg = total_sold / analysis_days

        # Calculate suggested reorder (30 days supply)
        suggested_quantity = int(daily_avg * 30)

        # Calculate lead time buffer (7 days)
        lead_time_buffer = int(daily_avg * 7)

        total_suggested = suggested_quantity + lead_time_buffer

        return {
            "product_id": product.id,
            "product_name": product.name,
            "current_stock": product.total_stock,
            "daily_average_sales": round(daily_avg, 2),
            "suggested_reorder_quantity": total_suggested,
            "reasoning": f"Based on {analysis_days} days analysis. "
                        f"Average daily sales: {daily_avg:.2f} units. "
                        f"Suggested: 30 days supply + 7 days lead time.",
            "urgency": "high" if product.total_stock < (daily_avg * 7) else "medium",
        }

    @staticmethod
    def analyze_sales_pattern(
        db: Session,
        product_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze sales pattern for a product.

        Args:
            db: Database session
            product_id: Product ID
            days: Days to analyze

        Returns:
            Sales pattern analysis
        """
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return {"error": "Product not found"}

        start_date = datetime.now() - timedelta(days=days)

        # Get daily sales
        daily_sales = db.query(
            func.date(Sale.created_at).label("date"),
            func.sum(SaleItem.quantity).label("quantity")
        ).join(
            Sale, Sale.id == SaleItem.sale_id
        ).filter(
            SaleItem.product_id == product_id,
            Sale.created_at >= start_date
        ).group_by(
            func.date(Sale.created_at)
        ).all()

        if not daily_sales:
            return {
                "product_id": product.id,
                "product_name": product.name,
                "pattern": "no_sales",
                "trend": "unknown",
            }

        # Calculate trend
        quantities = [s.quantity for s in daily_sales]
        avg_quantity = sum(quantities) / len(quantities)

        # Simple trend detection (compare first half to second half)
        mid = len(quantities) // 2
        first_half_avg = sum(quantities[:mid]) / mid if mid > 0 else 0
        second_half_avg = sum(quantities[mid:]) / (len(quantities) - mid) if (len(quantities) - mid) > 0 else 0

        if second_half_avg > first_half_avg * 1.2:
            trend = "increasing"
        elif second_half_avg < first_half_avg * 0.8:
            trend = "decreasing"
        else:
            trend = "stable"

        return {
            "product_id": product.id,
            "product_name": product.name,
            "average_daily_sales": round(avg_quantity, 2),
            "trend": trend,
            "total_sales_in_period": sum(quantities),
            "sales_days": len(daily_sales),
        }

    @staticmethod
    def get_profit_margin_analysis(db: Session) -> List[Dict[str, Any]]:
        """
        Analyze profit margins for all active products.

        Args:
            db: Database session

        Returns:
            List of products with profit margin analysis
        """
        products = db.query(Product).filter(Product.is_active == True).all()

        analysis = []
        for product in products:
            profit_per_unit = product.selling_price - product.cost_price
            profit_margin = (profit_per_unit / product.selling_price * 100) if product.selling_price > 0 else 0

            potential_profit = profit_per_unit * product.total_stock

            analysis.append({
                "product_id": product.id,
                "product_name": product.name,
                "sku": product.sku,
                "cost_price": product.cost_price,
                "selling_price": product.selling_price,
                "profit_per_unit": round(profit_per_unit, 2),
                "profit_margin_percentage": round(profit_margin, 2),
                "current_stock": product.total_stock,
                "potential_profit_from_stock": round(potential_profit, 2),
            })

        # Sort by profit margin
        analysis.sort(key=lambda x: x["profit_margin_percentage"], reverse=True)

        return analysis
