"""
Cloud reporting endpoints backed by projected sync facts.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.api.dependencies import require_organization_access
from app.db.base import get_db
from app.models.user import User
from app.models.cloud_projection import CloudInventoryMovementFact, CloudSaleFact
from app.models.sync_ingestion import IngestedSyncEvent
from app.schemas.cloud_reports import (
    CloudBranchSalesSummary,
    CloudInventoryMovementSummary,
    CloudSalesSummary,
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
