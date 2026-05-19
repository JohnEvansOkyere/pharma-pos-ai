"""
Deterministic cloud stock velocity and days-of-stock analysis.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from math import ceil
from typing import Any, Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.cloud_projection import CloudInventoryMovementFact, CloudProductSnapshot
from app.models.sync_event import SyncEventType
from app.models.tenancy import Branch


class CloudStockVelocityService:
    """Calculate product sales velocity from projected cloud movement facts."""

    @staticmethod
    def stock_velocity(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        period_days: int,
        limit: int,
        include_stable: bool = True,
    ) -> list[dict[str, Any]]:
        period_days = max(1, period_days)
        window_start = datetime.now(timezone.utc) - timedelta(days=period_days)
        sales_by_product = CloudStockVelocityService._sales_velocity_by_product(
            db,
            organization_id=organization_id,
            branch_id=branch_id,
            window_start=window_start,
        )

        product_query = db.query(CloudProductSnapshot).filter(
            CloudProductSnapshot.organization_id == organization_id,
            CloudProductSnapshot.is_active.is_(True),
        )
        if branch_id is not None:
            product_query = product_query.filter(CloudProductSnapshot.branch_id == branch_id)

        all_products = product_query.all()
        branch_ids_seen = list({p.branch_id for p in all_products})
        branch_names: dict[int, str] = {}
        if branch_ids_seen:
            branches = db.query(Branch.id, Branch.name).filter(Branch.id.in_(branch_ids_seen)).all()
            branch_names = {b.id: b.name for b in branches}

        items = []
        for product in all_products:
            sales = sales_by_product.get((product.branch_id, product.local_product_id), {})
            units_sold = int(sales.get("units_sold", 0))
            movement_count = int(sales.get("movement_count", 0))
            average_daily_units_sold = round(units_sold / period_days, 2)
            days_remaining = None
            estimated_stockout_date = None
            if average_daily_units_sold > 0:
                days_remaining = round(max(product.total_stock, 0) / average_daily_units_sold, 1)
                estimated_stockout_date = date.today() + timedelta(days=ceil(days_remaining))

            status = CloudStockVelocityService._status(
                total_stock=product.total_stock,
                low_stock_threshold=product.low_stock_threshold,
                days_remaining=days_remaining,
                average_daily_units_sold=average_daily_units_sold,
            )
            if not include_stable and status == "stable":
                continue

            items.append(
                {
                    "branch_id": product.branch_id,
                    "branch_name": branch_names.get(product.branch_id, f"Branch {product.branch_id}"),
                    "product_id": product.local_product_id,
                    "product_name": product.name,
                    "sku": product.sku,
                    "total_stock": product.total_stock,
                    "low_stock_threshold": product.low_stock_threshold,
                    "reorder_level": product.reorder_level,
                    "units_sold": units_sold,
                    "movement_count": movement_count,
                    "average_daily_units_sold": average_daily_units_sold,
                    "days_of_stock_remaining": days_remaining,
                    "estimated_stockout_date": estimated_stockout_date,
                    "units_needed": max((product.reorder_level or product.low_stock_threshold) - product.total_stock, 0),
                    "confidence": CloudStockVelocityService._confidence(movement_count=movement_count, units_sold=units_sold),
                    "status": status,
                }
            )

        items.sort(key=CloudStockVelocityService._sort_key)
        return items[:limit]

    @staticmethod
    def _sales_velocity_by_product(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        window_start: datetime,
    ) -> dict[tuple[int, int], dict[str, Any]]:
        movement_time = func.coalesce(
            CloudInventoryMovementFact.occurred_at,
            CloudInventoryMovementFact.created_at,
        )
        sold_units = func.coalesce(
            func.sum(
                case(
                    (
                        CloudInventoryMovementFact.quantity_delta < 0,
                        -CloudInventoryMovementFact.quantity_delta,
                    ),
                    else_=0,
                )
            ),
            0,
        )
        query = db.query(
            CloudInventoryMovementFact.branch_id,
            CloudInventoryMovementFact.local_product_id,
            sold_units.label("units_sold"),
            func.count(CloudInventoryMovementFact.id).label("movement_count"),
        ).filter(
            CloudInventoryMovementFact.organization_id == organization_id,
            CloudInventoryMovementFact.event_type == SyncEventType.SALE_CREATED.value,
            CloudInventoryMovementFact.local_product_id.is_not(None),
            CloudInventoryMovementFact.quantity_delta < 0,
            movement_time >= window_start,
        )
        if branch_id is not None:
            query = query.filter(CloudInventoryMovementFact.branch_id == branch_id)

        rows = query.group_by(
            CloudInventoryMovementFact.branch_id,
            CloudInventoryMovementFact.local_product_id,
        ).all()
        return {
            (int(row.branch_id), int(row.local_product_id)): {
                "units_sold": int(row.units_sold or 0),
                "movement_count": int(row.movement_count or 0),
            }
            for row in rows
            if row.local_product_id is not None
        }

    @staticmethod
    def _status(
        *,
        total_stock: int,
        low_stock_threshold: int,
        days_remaining: Optional[float],
        average_daily_units_sold: float,
    ) -> str:
        if total_stock <= 0:
            return "out_of_stock"
        if average_daily_units_sold <= 0:
            return "no_velocity"
        if days_remaining is not None and days_remaining <= 3:
            return "critical"
        if days_remaining is not None and days_remaining <= 7:
            return "urgent"
        if total_stock <= low_stock_threshold or (days_remaining is not None and days_remaining <= 14):
            return "reorder_soon"
        return "stable"

    @staticmethod
    def _confidence(*, movement_count: int, units_sold: int) -> str:
        if movement_count == 0 or units_sold == 0:
            return "none"
        if movement_count < 3:
            return "low"
        if movement_count < 7:
            return "medium"
        return "high"

    @staticmethod
    def _sort_key(item: dict[str, Any]) -> tuple[int, float, int, str]:
        priority = {
            "out_of_stock": 0,
            "critical": 1,
            "urgent": 2,
            "reorder_soon": 3,
            "stable": 4,
            "no_velocity": 5,
        }
        days_remaining = item["days_of_stock_remaining"]
        return (
            priority.get(item["status"], 99),
            days_remaining if days_remaining is not None else 999999.0,
            item["total_stock"],
            item["product_name"],
        )
