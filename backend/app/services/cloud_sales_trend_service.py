"""
Deterministic cloud revenue comparison and branch anomaly analysis.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.cloud_projection import CloudSaleFact
from app.models.tenancy import Branch


class CloudSalesTrendService:
    """Compare current cloud sales windows against the previous equal window."""

    @staticmethod
    def revenue_comparison(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        period_days: int,
        limit: int,
    ) -> dict[str, Any]:
        period_days = max(1, period_days)
        current_end = datetime.now(timezone.utc)
        current_start = current_end - timedelta(days=period_days)
        previous_start = current_start - timedelta(days=period_days)

        current_rows = CloudSalesTrendService._sales_by_branch(
            db,
            organization_id=organization_id,
            branch_id=branch_id,
            start_at=current_start,
            end_at=current_end,
        )
        previous_rows = CloudSalesTrendService._sales_by_branch(
            db,
            organization_id=organization_id,
            branch_id=branch_id,
            start_at=previous_start,
            end_at=current_start,
        )

        branch_ids = sorted(set(current_rows) | set(previous_rows))
        branch_names = CloudSalesTrendService._branch_names(db, branch_ids)
        branch_items = []
        for branch_key in branch_ids:
            current = current_rows.get(branch_key, CloudSalesTrendService._empty_row(branch_key))
            previous = previous_rows.get(branch_key, CloudSalesTrendService._empty_row(branch_key))
            revenue_change = current["total_revenue"] - previous["total_revenue"]
            sales_change = current["sales_count"] - previous["sales_count"]
            revenue_change_percent = CloudSalesTrendService._percent_change(
                current=current["total_revenue"],
                previous=previous["total_revenue"],
            )
            branch_items.append(
                {
                    "branch_id": branch_key,
                    "branch_name": branch_names.get(branch_key, f"Branch {branch_key}"),
                    "current_sales_count": current["sales_count"],
                    "current_revenue": float(current["total_revenue"]),
                    "previous_sales_count": previous["sales_count"],
                    "previous_revenue": float(previous["total_revenue"]),
                    "sales_count_change": sales_change,
                    "revenue_change": float(revenue_change),
                    "revenue_change_percent": revenue_change_percent,
                    "status": CloudSalesTrendService._status(
                        current_revenue=current["total_revenue"],
                        previous_revenue=previous["total_revenue"],
                        current_sales_count=current["sales_count"],
                        previous_sales_count=previous["sales_count"],
                        revenue_change_percent=revenue_change_percent,
                    ),
                }
            )

        current_total = CloudSalesTrendService._total(current_rows.values())
        previous_total = CloudSalesTrendService._total(previous_rows.values())
        branch_items.sort(key=CloudSalesTrendService._branch_sort_key)
        return {
            "organization_id": organization_id,
            "branch_id": branch_id,
            "period_days": period_days,
            "current_period_start": current_start,
            "current_period_end": current_end,
            "previous_period_start": previous_start,
            "previous_period_end": current_start,
            "current_sales_count": current_total["sales_count"],
            "current_revenue": float(current_total["total_revenue"]),
            "previous_sales_count": previous_total["sales_count"],
            "previous_revenue": float(previous_total["total_revenue"]),
            "sales_count_change": current_total["sales_count"] - previous_total["sales_count"],
            "revenue_change": float(current_total["total_revenue"] - previous_total["total_revenue"]),
            "revenue_change_percent": CloudSalesTrendService._percent_change(
                current=current_total["total_revenue"],
                previous=previous_total["total_revenue"],
            ),
            "branch_count": len(branch_items),
            "anomaly_count": sum(1 for item in branch_items if item["status"] in {"no_sales_current", "severe_drop", "drop"}),
            "branches": branch_items[:limit],
        }

    @staticmethod
    def _sales_by_branch(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        start_at: datetime,
        end_at: datetime,
    ) -> dict[int, dict[str, Any]]:
        sale_time = func.coalesce(CloudSaleFact.occurred_at, CloudSaleFact.created_at)
        query = db.query(
            CloudSaleFact.branch_id,
            func.count(CloudSaleFact.id).label("sales_count"),
            func.coalesce(func.sum(CloudSaleFact.total_amount), 0).label("total_revenue"),
        ).filter(
            CloudSaleFact.organization_id == organization_id,
            sale_time >= start_at,
            sale_time < end_at,
        )
        if branch_id is not None:
            query = query.filter(CloudSaleFact.branch_id == branch_id)

        rows = query.group_by(CloudSaleFact.branch_id).all()
        return {
            int(row.branch_id): {
                "branch_id": int(row.branch_id),
                "sales_count": int(row.sales_count or 0),
                "total_revenue": Decimal(str(row.total_revenue or "0")),
            }
            for row in rows
        }

    @staticmethod
    def _branch_names(db: Session, branch_ids: list[int]) -> dict[int, str]:
        if not branch_ids:
            return {}
        rows = db.query(Branch.id, Branch.name).filter(Branch.id.in_(branch_ids)).all()
        return {int(row.id): row.name for row in rows}

    @staticmethod
    def _empty_row(branch_id: int) -> dict[str, Any]:
        return {"branch_id": branch_id, "sales_count": 0, "total_revenue": Decimal("0")}

    @staticmethod
    def _total(rows) -> dict[str, Any]:
        total_revenue = Decimal("0")
        total_sales = 0
        for row in rows:
            total_revenue += row["total_revenue"]
            total_sales += row["sales_count"]
        return {"sales_count": total_sales, "total_revenue": total_revenue}

    @staticmethod
    def _percent_change(*, current: Decimal, previous: Decimal) -> Optional[float]:
        if previous == 0:
            return None
        return round(float((current - previous) / previous * Decimal("100")), 2)

    @staticmethod
    def _status(
        *,
        current_revenue: Decimal,
        previous_revenue: Decimal,
        current_sales_count: int,
        previous_sales_count: int,
        revenue_change_percent: Optional[float],
    ) -> str:
        if current_sales_count == 0 and previous_sales_count > 0:
            return "no_sales_current"
        if previous_revenue == 0 and current_revenue > 0:
            return "new_sales"
        if revenue_change_percent is not None and revenue_change_percent <= -50:
            return "severe_drop"
        if revenue_change_percent is not None and revenue_change_percent <= -20:
            return "drop"
        if revenue_change_percent is not None and revenue_change_percent >= 20:
            return "growth"
        return "stable"

    @staticmethod
    def _branch_sort_key(item: dict[str, Any]) -> tuple[int, float, str]:
        priority = {
            "no_sales_current": 0,
            "severe_drop": 1,
            "drop": 2,
            "new_sales": 3,
            "growth": 4,
            "stable": 5,
        }
        return (
            priority.get(item["status"], 99),
            item["revenue_change"],
            item["branch_name"],
        )
