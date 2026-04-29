"""
Cloud reporting endpoints backed by projected sync facts.
"""
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.api.dependencies import require_organization_access
from app.db.base import get_db
from app.models.user import User
from app.models.cloud_projection import (
    CloudBatchSnapshot,
    CloudInventoryMovementFact,
    CloudProductSnapshot,
    CloudSaleFact,
)
from app.models.sync_ingestion import IngestedSyncEvent
from app.schemas.cloud_reports import (
    CloudBranchSalesSummary,
    CloudExpiryRiskItem,
    CloudInventoryMovementSummary,
    CloudLowStockItem,
    CloudSalesSummary,
    CloudStockRiskSummary,
    CloudSyncHealth,
)

router = APIRouter(prefix="/cloud-reports", tags=["Cloud Reports"])


def _apply_time_filters(query, model, start_at: Optional[datetime], end_at: Optional[datetime]):
    if start_at is not None:
        query = query.filter(model.created_at >= start_at)
    if end_at is not None:
        query = query.filter(model.created_at <= end_at)
    return query


def _resolve_branch_scope(current_user: User, branch_id: Optional[int]) -> Optional[int]:
    if current_user.branch_id is not None:
        return current_user.branch_id
    return branch_id


@router.get("/sales-summary", response_model=CloudSalesSummary)
def get_cloud_sales_summary(
    organization_id: int,
    branch_id: Optional[int] = None,
    start_at: Optional[datetime] = None,
    end_at: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organization_access),
):
    effective_branch_id = _resolve_branch_scope(current_user, branch_id)
    query = db.query(
        func.count(CloudSaleFact.id).label("sales_count"),
        func.coalesce(func.sum(CloudSaleFact.total_amount), 0).label("total_revenue"),
        func.coalesce(func.sum(CloudSaleFact.item_count), 0).label("total_items"),
    ).filter(CloudSaleFact.organization_id == organization_id)

    if effective_branch_id is not None:
        query = query.filter(CloudSaleFact.branch_id == effective_branch_id)
    query = _apply_time_filters(query, CloudSaleFact, start_at, end_at)
    row = query.one()

    return CloudSalesSummary(
        organization_id=organization_id,
        branch_id=effective_branch_id,
        sales_count=int(row.sales_count or 0),
        total_revenue=float(row.total_revenue or 0),
        total_items=int(row.total_items or 0),
    )


@router.get("/branch-sales", response_model=List[CloudBranchSalesSummary])
def get_cloud_branch_sales(
    organization_id: int,
    start_at: Optional[datetime] = None,
    end_at: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organization_access),
):
    effective_branch_id = _resolve_branch_scope(current_user, None)
    query = db.query(
        CloudSaleFact.branch_id,
        func.count(CloudSaleFact.id).label("sales_count"),
        func.coalesce(func.sum(CloudSaleFact.total_amount), 0).label("total_revenue"),
        func.coalesce(func.sum(CloudSaleFact.item_count), 0).label("total_items"),
    ).filter(CloudSaleFact.organization_id == organization_id)

    if effective_branch_id is not None:
        query = query.filter(CloudSaleFact.branch_id == effective_branch_id)

    query = _apply_time_filters(query, CloudSaleFact, start_at, end_at)
    rows = query.group_by(CloudSaleFact.branch_id).order_by(CloudSaleFact.branch_id.asc()).all()

    return [
        CloudBranchSalesSummary(
            branch_id=row.branch_id,
            sales_count=int(row.sales_count or 0),
            total_revenue=float(row.total_revenue or 0),
            total_items=int(row.total_items or 0),
        )
        for row in rows
    ]


@router.get("/inventory-movements-summary", response_model=CloudInventoryMovementSummary)
def get_cloud_inventory_movement_summary(
    organization_id: int,
    branch_id: Optional[int] = None,
    start_at: Optional[datetime] = None,
    end_at: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organization_access),
):
    effective_branch_id = _resolve_branch_scope(current_user, branch_id)
    positive_quantity = func.coalesce(
        func.sum(case((CloudInventoryMovementFact.quantity_delta > 0, CloudInventoryMovementFact.quantity_delta), else_=0)),
        0,
    )
    negative_quantity = func.coalesce(
        func.sum(case((CloudInventoryMovementFact.quantity_delta < 0, CloudInventoryMovementFact.quantity_delta), else_=0)),
        0,
    )
    net_quantity = func.coalesce(func.sum(CloudInventoryMovementFact.quantity_delta), 0)

    query = db.query(
        func.count(CloudInventoryMovementFact.id).label("movement_count"),
        positive_quantity.label("total_positive_quantity"),
        negative_quantity.label("total_negative_quantity"),
        net_quantity.label("net_quantity_delta"),
    ).filter(CloudInventoryMovementFact.organization_id == organization_id)

    if effective_branch_id is not None:
        query = query.filter(CloudInventoryMovementFact.branch_id == effective_branch_id)
    query = _apply_time_filters(query, CloudInventoryMovementFact, start_at, end_at)
    row = query.one()

    return CloudInventoryMovementSummary(
        organization_id=organization_id,
        branch_id=effective_branch_id,
        movement_count=int(row.movement_count or 0),
        total_positive_quantity=int(row.total_positive_quantity or 0),
        total_negative_quantity=int(row.total_negative_quantity or 0),
        net_quantity_delta=int(row.net_quantity_delta or 0),
    )


@router.get("/sync-health", response_model=CloudSyncHealth)
def get_cloud_sync_health(
    organization_id: int,
    branch_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organization_access),
):
    effective_branch_id = _resolve_branch_scope(current_user, branch_id)
    query = db.query(IngestedSyncEvent).filter(IngestedSyncEvent.organization_id == organization_id)
    if effective_branch_id is not None:
        query = query.filter(IngestedSyncEvent.branch_id == effective_branch_id)

    row = query.with_entities(
        func.count(IngestedSyncEvent.id).label("ingested_event_count"),
        func.coalesce(func.sum(case((IngestedSyncEvent.projected_at.is_not(None), 1), else_=0)), 0).label("projected_event_count"),
        func.coalesce(func.sum(case((IngestedSyncEvent.projection_error.is_not(None), 1), else_=0)), 0).label("projection_failed_count"),
        func.coalesce(func.sum(IngestedSyncEvent.duplicate_count), 0).label("duplicate_delivery_count"),
        func.max(IngestedSyncEvent.received_at).label("last_received_at"),
        func.max(IngestedSyncEvent.projected_at).label("last_projected_at"),
    ).one()

    return CloudSyncHealth(
        organization_id=organization_id,
        branch_id=effective_branch_id,
        ingested_event_count=int(row.ingested_event_count or 0),
        projected_event_count=int(row.projected_event_count or 0),
        projection_failed_count=int(row.projection_failed_count or 0),
        duplicate_delivery_count=int(row.duplicate_delivery_count or 0),
        last_received_at=row.last_received_at,
        last_projected_at=row.last_projected_at,
    )


@router.get("/stock-risk-summary", response_model=CloudStockRiskSummary)
def get_cloud_stock_risk_summary(
    organization_id: int,
    branch_id: Optional[int] = None,
    expiry_warning_days: int = Query(90, ge=1, le=730),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organization_access),
):
    effective_branch_id = _resolve_branch_scope(current_user, branch_id)
    product_query = db.query(CloudProductSnapshot).filter(
        CloudProductSnapshot.organization_id == organization_id,
        CloudProductSnapshot.is_active.is_(True),
    )
    batch_query = db.query(CloudBatchSnapshot).filter(
        CloudBatchSnapshot.organization_id == organization_id,
        CloudBatchSnapshot.quantity > 0,
        CloudBatchSnapshot.is_quarantined.is_(False),
    )

    if effective_branch_id is not None:
        product_query = product_query.filter(CloudProductSnapshot.branch_id == effective_branch_id)
        batch_query = batch_query.filter(CloudBatchSnapshot.branch_id == effective_branch_id)

    today = date.today()
    warning_date = today + timedelta(days=expiry_warning_days)
    products = product_query.all()
    batches = batch_query.all()

    return CloudStockRiskSummary(
        organization_id=organization_id,
        branch_id=effective_branch_id,
        low_stock_count=sum(1 for product in products if 0 < product.total_stock <= product.low_stock_threshold),
        out_of_stock_count=sum(1 for product in products if product.total_stock <= 0),
        near_expiry_batch_count=sum(1 for batch in batches if today <= batch.expiry_date <= warning_date),
        expired_batch_count=sum(1 for batch in batches if batch.expiry_date < today),
        total_quantity_on_hand=sum(max(product.total_stock, 0) for product in products),
        value_at_risk=float(
            sum(
                (batch.cost_price or 0) * batch.quantity
                for batch in batches
                if batch.expiry_date <= warning_date
            )
        ),
        expiry_warning_days=expiry_warning_days,
    )


@router.get("/low-stock", response_model=List[CloudLowStockItem])
def get_cloud_low_stock(
    organization_id: int,
    branch_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organization_access),
):
    effective_branch_id = _resolve_branch_scope(current_user, branch_id)
    query = db.query(CloudProductSnapshot).filter(
        CloudProductSnapshot.organization_id == organization_id,
        CloudProductSnapshot.is_active.is_(True),
        CloudProductSnapshot.total_stock <= CloudProductSnapshot.low_stock_threshold,
    )
    if effective_branch_id is not None:
        query = query.filter(CloudProductSnapshot.branch_id == effective_branch_id)

    rows = query.order_by(CloudProductSnapshot.total_stock.asc(), CloudProductSnapshot.name.asc()).limit(limit).all()
    return [
        CloudLowStockItem(
            branch_id=row.branch_id,
            product_id=row.local_product_id,
            product_name=row.name,
            sku=row.sku,
            total_stock=row.total_stock,
            low_stock_threshold=row.low_stock_threshold,
            reorder_level=row.reorder_level,
            units_needed=max((row.reorder_level or row.low_stock_threshold) - row.total_stock, 0),
            status="out_of_stock" if row.total_stock <= 0 else "low_stock",
        )
        for row in rows
    ]


@router.get("/expiry-risk", response_model=List[CloudExpiryRiskItem])
def get_cloud_expiry_risk(
    organization_id: int,
    branch_id: Optional[int] = None,
    days: int = Query(90, ge=1, le=730),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organization_access),
):
    effective_branch_id = _resolve_branch_scope(current_user, branch_id)
    today = date.today()
    warning_date = today + timedelta(days=days)
    query = db.query(CloudBatchSnapshot, CloudProductSnapshot).join(
        CloudProductSnapshot,
        (CloudProductSnapshot.organization_id == CloudBatchSnapshot.organization_id)
        & (CloudProductSnapshot.branch_id == CloudBatchSnapshot.branch_id)
        & (CloudProductSnapshot.local_product_id == CloudBatchSnapshot.local_product_id),
    ).filter(
        CloudBatchSnapshot.organization_id == organization_id,
        CloudBatchSnapshot.quantity > 0,
        CloudBatchSnapshot.is_quarantined.is_(False),
        CloudBatchSnapshot.expiry_date <= warning_date,
        CloudProductSnapshot.is_active.is_(True),
    )
    if effective_branch_id is not None:
        query = query.filter(CloudBatchSnapshot.branch_id == effective_branch_id)

    rows = query.order_by(CloudBatchSnapshot.expiry_date.asc(), CloudProductSnapshot.name.asc()).limit(limit).all()
    return [
        CloudExpiryRiskItem(
            branch_id=batch.branch_id,
            product_id=batch.local_product_id,
            product_name=product.name,
            sku=product.sku,
            batch_id=batch.local_batch_id,
            batch_number=batch.batch_number,
            quantity=batch.quantity,
            expiry_date=batch.expiry_date,
            days_until_expiry=(batch.expiry_date - today).days,
            value_at_risk=float((batch.cost_price or 0) * batch.quantity),
            status="expired" if batch.expiry_date < today else "near_expiry",
        )
        for batch, product in rows
    ]
