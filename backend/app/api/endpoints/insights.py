"""
AI Insights API endpoints.
"""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.user import User
from app.services.ai_insights import AIInsightsService
from app.api.dependencies import get_current_active_user

router = APIRouter(prefix="/insights", tags=["AI Insights"])


@router.get("/dead-stock")
def get_dead_stock(
    days: int = Query(90, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """
    Get dead stock products (no sales in specified days).

    Args:
        days: Number of days to analyze
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of dead stock products
    """
    return AIInsightsService.detect_dead_stock(db, days)


@router.get("/reorder-suggestion/{product_id}")
def get_reorder_suggestion(
    product_id: int,
    analysis_days: int = Query(30, ge=7),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get AI-powered reorder quantity suggestion for a product.

    Args:
        product_id: Product ID
        analysis_days: Days to analyze for sales trend
        db: Database session
        current_user: Current authenticated user

    Returns:
        Reorder suggestion with reasoning
    """
    return AIInsightsService.suggest_reorder_quantity(db, product_id, analysis_days)


@router.get("/sales-pattern/{product_id}")
def get_sales_pattern(
    product_id: int,
    days: int = Query(30, ge=7),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Analyze sales pattern for a product.

    Args:
        product_id: Product ID
        days: Days to analyze
        db: Database session
        current_user: Current authenticated user

    Returns:
        Sales pattern analysis
    """
    return AIInsightsService.analyze_sales_pattern(db, product_id, days)


@router.get("/profit-margin-analysis")
def get_profit_margin_analysis(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """
    Get profit margin analysis for all products.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of products with profit margin data
    """
    return AIInsightsService.get_profit_margin_analysis(db)
