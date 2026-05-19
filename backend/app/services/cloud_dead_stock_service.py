"""
Deterministic cloud dead-stock and slow-mover detection from projected cloud facts.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.cloud_projection import CloudInventoryMovementFact, CloudProductSnapshot
from app.models.sync_event import SyncEventType
from app.models.tenancy import Branch


# A product is a "slow mover" when average daily units sold is below this rate.
SLOW_MOVER_DAILY_THRESHOLD = 0.3


class CloudDeadStockService:
    """Identify dead stock and slow movers from projected cloud data."""

    @staticmethod
    def dead_stock(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        period_days: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        period_days = max(1, period_days)
        window_start = datetime.now(timezone.utc) - timedelta(days=period_days)

        sold_units = CloudDeadStockService._sold_units_by_product(
            db,
            organization_id=organization_id,
            branch_id=branch_id,
            window_start=window_start,
        )
        last_sale_dates = CloudDeadStockService._last_sale_date_by_product(
            db,
            organization_id=organization_id,
            branch_id=branch_id,
        )

        product_query = db.query(CloudProductSnapshot).filter(
            CloudProductSnapshot.organization_id == organization_id,
            CloudProductSnapshot.is_active.is_(True),
            CloudProductSnapshot.total_stock > 0,
        )
        if branch_id is not None:
            product_query = product_query.filter(CloudProductSnapshot.branch_id == branch_id)

        branch_ids_seen: list[int] = []
        all_products = product_query.all()
        for p in all_products:
            if p.branch_id not in branch_ids_seen:
                branch_ids_seen.append(p.branch_id)

        branch_names: dict[int, str] = {}
        if branch_ids_seen:
            branches = db.query(Branch.id, Branch.name).filter(Branch.id.in_(branch_ids_seen)).all()
            branch_names = {b.id: b.name for b in branches}

        today = datetime.now(timezone.utc).date()
        items: list[dict[str, Any]] = []
        for product in all_products:
            key = (product.branch_id, product.local_product_id)
            units_sold = float(sold_units.get(key, 0))
            avg_daily = units_sold / period_days
            last_sale_dt = last_sale_dates.get(key)
            last_sale_date = last_sale_dt.date() if last_sale_dt else None
            days_since_last_sale = (today - last_sale_date).days if last_sale_date else None

            if units_sold == 0:
                status = "dead_stock"
            elif avg_daily < SLOW_MOVER_DAILY_THRESHOLD:
                status = "slow_mover"
            else:
                continue

            cost_price = float(product.cost_price) if product.cost_price is not None else None
            value_at_risk = round(cost_price * product.total_stock, 2) if cost_price is not None else None
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
                    "units_sold_in_period": int(units_sold),
                    "average_daily_units_sold": round(avg_daily, 4),
                    "days_since_last_sale": days_since_last_sale,
                    "last_sale_date": last_sale_date.isoformat() if last_sale_date else None,
                    "value_at_risk": value_at_risk,
                    "status": status,
                }
            )

        # Sort: dead_stock first, then slow_mover; within each group highest stock first.
        items.sort(key=lambda x: (0 if x["status"] == "dead_stock" else 1, -x["total_stock"]))
        return items[:limit]

    @staticmethod
    def _sold_units_by_product(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        window_start: datetime,
    ) -> dict[tuple[int, int], float]:
        movement_time = func.coalesce(
            CloudInventoryMovementFact.occurred_at,
            CloudInventoryMovementFact.created_at,
        )
        query = (
            db.query(
                CloudInventoryMovementFact.branch_id,
                CloudInventoryMovementFact.local_product_id,
                func.coalesce(func.sum(-CloudInventoryMovementFact.quantity_delta), 0).label("units_sold"),
            )
            .filter(
                CloudInventoryMovementFact.organization_id == organization_id,
                CloudInventoryMovementFact.event_type == SyncEventType.SALE_CREATED.value,
                CloudInventoryMovementFact.quantity_delta < 0,
                movement_time >= window_start,
            )
        )
        if branch_id is not None:
            query = query.filter(CloudInventoryMovementFact.branch_id == branch_id)
        rows = query.group_by(
            CloudInventoryMovementFact.branch_id,
            CloudInventoryMovementFact.local_product_id,
        ).all()
        return {(row.branch_id, row.local_product_id): float(row.units_sold or 0) for row in rows}

    @staticmethod
    def _last_sale_date_by_product(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
    ) -> dict[tuple[int, int], datetime]:
        movement_time = func.coalesce(
            CloudInventoryMovementFact.occurred_at,
            CloudInventoryMovementFact.created_at,
        )
        query = (
            db.query(
                CloudInventoryMovementFact.branch_id,
                CloudInventoryMovementFact.local_product_id,
                func.max(movement_time).label("last_sale_at"),
            )
            .filter(
                CloudInventoryMovementFact.organization_id == organization_id,
                CloudInventoryMovementFact.event_type == SyncEventType.SALE_CREATED.value,
                CloudInventoryMovementFact.quantity_delta < 0,
            )
        )
        if branch_id is not None:
            query = query.filter(CloudInventoryMovementFact.branch_id == branch_id)
        rows = query.group_by(
            CloudInventoryMovementFact.branch_id,
            CloudInventoryMovementFact.local_product_id,
        ).all()
        return {(row.branch_id, row.local_product_id): row.last_sale_at for row in rows if row.last_sale_at}
