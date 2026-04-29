"""
Read-only manager assistant backed by approved cloud reporting data.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.cloud_projection import CloudInventoryMovementFact, CloudSaleFact
from app.models.sync_ingestion import IngestedSyncEvent
from app.models.user import User


REFUSAL_MESSAGE = (
    "I cannot provide clinical advice, approve dispensing, override prescription "
    "or controlled-drug rules, or change stock. I can help summarize sales, "
    "inventory movement, and sync health from approved reporting data."
)


class AIManagerService:
    """Deterministic assistant facade over approved cloud report read models."""

    SALES_SOURCE = "cloud_sale_facts"
    INVENTORY_SOURCE = "cloud_inventory_movement_facts"
    SYNC_SOURCE = "ingested_sync_events"

    @staticmethod
    def answer(
        db: Session,
        *,
        message: str,
        organization_id: int,
        branch_id: Optional[int],
        period_days: int,
        current_user: User,
    ) -> Dict[str, Any]:
        effective_branch_id = AIManagerService._effective_branch_id(current_user, branch_id)
        normalized_message = message.strip().lower()

        if AIManagerService._is_disallowed_request(normalized_message):
            return {
                "answer": REFUSAL_MESSAGE,
                "data_scope": AIManagerService._scope_payload(
                    organization_id,
                    effective_branch_id,
                    period_days,
                    [],
                ),
                "tool_results": {},
                "safety_notes": AIManagerService._safety_notes(),
                "refused": True,
            }

        sales_summary = AIManagerService._sales_summary(
            db,
            organization_id=organization_id,
            branch_id=effective_branch_id,
            period_days=period_days,
        )
        branch_sales = AIManagerService._branch_sales(
            db,
            organization_id=organization_id,
            branch_id=effective_branch_id,
            period_days=period_days,
        )
        inventory_summary = AIManagerService._inventory_summary(
            db,
            organization_id=organization_id,
            branch_id=effective_branch_id,
            period_days=period_days,
        )
        sync_health = AIManagerService._sync_health(
            db,
            organization_id=organization_id,
            branch_id=effective_branch_id,
        )

        tool_results = {
            "sales_summary": sales_summary,
            "branch_sales": branch_sales,
            "inventory_summary": inventory_summary,
            "sync_health": sync_health,
        }

        return {
            "answer": AIManagerService._compose_answer(
                normalized_message,
                sales_summary=sales_summary,
                branch_sales=branch_sales,
                inventory_summary=inventory_summary,
                sync_health=sync_health,
                period_days=period_days,
                branch_id=effective_branch_id,
            ),
            "data_scope": AIManagerService._scope_payload(
                organization_id,
                effective_branch_id,
                period_days,
                [
                    AIManagerService.SALES_SOURCE,
                    AIManagerService.INVENTORY_SOURCE,
                    AIManagerService.SYNC_SOURCE,
                ],
            ),
            "tool_results": tool_results,
            "safety_notes": AIManagerService._safety_notes(),
            "refused": False,
        }

    @staticmethod
    def _effective_branch_id(current_user: User, requested_branch_id: Optional[int]) -> Optional[int]:
        if current_user.branch_id is not None:
            return current_user.branch_id
        return requested_branch_id

    @staticmethod
    def _window_start(period_days: int) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=period_days)

    @staticmethod
    def _sales_summary(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        period_days: int,
    ) -> Dict[str, Any]:
        query = db.query(
            func.count(CloudSaleFact.id).label("sales_count"),
            func.coalesce(func.sum(CloudSaleFact.total_amount), 0).label("total_revenue"),
            func.coalesce(func.sum(CloudSaleFact.item_count), 0).label("total_items"),
        ).filter(
            CloudSaleFact.organization_id == organization_id,
            CloudSaleFact.created_at >= AIManagerService._window_start(period_days),
        )

        if branch_id is not None:
            query = query.filter(CloudSaleFact.branch_id == branch_id)

        row = query.one()
        return {
            "sales_count": int(row.sales_count or 0),
            "total_revenue": float(row.total_revenue or Decimal("0")),
            "total_items": int(row.total_items or 0),
        }

    @staticmethod
    def _branch_sales(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        period_days: int,
    ) -> List[Dict[str, Any]]:
        query = db.query(
            CloudSaleFact.branch_id,
            func.count(CloudSaleFact.id).label("sales_count"),
            func.coalesce(func.sum(CloudSaleFact.total_amount), 0).label("total_revenue"),
            func.coalesce(func.sum(CloudSaleFact.item_count), 0).label("total_items"),
        ).filter(
            CloudSaleFact.organization_id == organization_id,
            CloudSaleFact.created_at >= AIManagerService._window_start(period_days),
        )

        if branch_id is not None:
            query = query.filter(CloudSaleFact.branch_id == branch_id)

        rows = query.group_by(CloudSaleFact.branch_id).order_by(CloudSaleFact.branch_id.asc()).all()
        return [
            {
                "branch_id": row.branch_id,
                "sales_count": int(row.sales_count or 0),
                "total_revenue": float(row.total_revenue or Decimal("0")),
                "total_items": int(row.total_items or 0),
            }
            for row in rows
        ]

    @staticmethod
    def _inventory_summary(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        period_days: int,
    ) -> Dict[str, Any]:
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
        ).filter(
            CloudInventoryMovementFact.organization_id == organization_id,
            CloudInventoryMovementFact.created_at >= AIManagerService._window_start(period_days),
        )

        if branch_id is not None:
            query = query.filter(CloudInventoryMovementFact.branch_id == branch_id)

        row = query.one()
        return {
            "movement_count": int(row.movement_count or 0),
            "total_positive_quantity": int(row.total_positive_quantity or 0),
            "total_negative_quantity": int(row.total_negative_quantity or 0),
            "net_quantity_delta": int(row.net_quantity_delta or 0),
        }

    @staticmethod
    def _sync_health(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
    ) -> Dict[str, Any]:
        query = db.query(IngestedSyncEvent).filter(IngestedSyncEvent.organization_id == organization_id)
        if branch_id is not None:
            query = query.filter(IngestedSyncEvent.branch_id == branch_id)

        row = query.with_entities(
            func.count(IngestedSyncEvent.id).label("ingested_event_count"),
            func.coalesce(func.sum(case((IngestedSyncEvent.projected_at.is_not(None), 1), else_=0)), 0).label("projected_event_count"),
            func.coalesce(func.sum(case((IngestedSyncEvent.projection_error.is_not(None), 1), else_=0)), 0).label("projection_failed_count"),
            func.coalesce(func.sum(IngestedSyncEvent.duplicate_count), 0).label("duplicate_delivery_count"),
            func.max(IngestedSyncEvent.received_at).label("last_received_at"),
            func.max(IngestedSyncEvent.projected_at).label("last_projected_at"),
        ).one()

        return {
            "ingested_event_count": int(row.ingested_event_count or 0),
            "projected_event_count": int(row.projected_event_count or 0),
            "projection_failed_count": int(row.projection_failed_count or 0),
            "duplicate_delivery_count": int(row.duplicate_delivery_count or 0),
            "last_received_at": row.last_received_at.isoformat() if row.last_received_at else None,
            "last_projected_at": row.last_projected_at.isoformat() if row.last_projected_at else None,
        }

    @staticmethod
    def _compose_answer(
        message: str,
        *,
        sales_summary: Dict[str, Any],
        branch_sales: List[Dict[str, Any]],
        inventory_summary: Dict[str, Any],
        sync_health: Dict[str, Any],
        period_days: int,
        branch_id: Optional[int],
    ) -> str:
        scope = f"branch {branch_id}" if branch_id is not None else "all permitted branches"
        top_branch = max(branch_sales, key=lambda row: row["total_revenue"], default=None)

        if any(keyword in message for keyword in ["sync", "upload", "project", "cloud"]):
            if sync_health["projection_failed_count"] > 0:
                return (
                    f"For {scope}, sync needs attention: {sync_health['projection_failed_count']} projected event(s) failed, "
                    f"{sync_health['duplicate_delivery_count']} duplicate delivery attempt(s) were recorded, and "
                    f"{sync_health['projected_event_count']} of {sync_health['ingested_event_count']} ingested event(s) are projected."
                )
            return (
                f"For {scope}, sync health looks stable from the reporting data: "
                f"{sync_health['projected_event_count']} of {sync_health['ingested_event_count']} ingested event(s) are projected, "
                f"with {sync_health['duplicate_delivery_count']} duplicate delivery attempt(s)."
            )

        if any(keyword in message for keyword in ["branch", "best", "perform"]):
            if top_branch is None:
                return f"For {scope}, no branch sales have been projected in the last {period_days} day(s)."
            return (
                f"In the last {period_days} day(s), branch {top_branch['branch_id']} is the strongest projected branch by revenue "
                f"with GHS {top_branch['total_revenue']:.2f} from {top_branch['sales_count']} sale(s) and "
                f"{top_branch['total_items']} item(s)."
            )

        if any(keyword in message for keyword in ["stock", "inventory", "movement"]):
            return (
                f"For {scope} over the last {period_days} day(s), inventory movement shows "
                f"{inventory_summary['movement_count']} movement row(s), "
                f"+{inventory_summary['total_positive_quantity']} received/positive quantity, "
                f"{inventory_summary['total_negative_quantity']} negative quantity, and "
                f"{inventory_summary['net_quantity_delta']} net quantity movement."
            )

        return (
            f"For {scope} over the last {period_days} day(s), projected sales total "
            f"GHS {sales_summary['total_revenue']:.2f} from {sales_summary['sales_count']} sale(s) and "
            f"{sales_summary['total_items']} item(s). Inventory net movement is "
            f"{inventory_summary['net_quantity_delta']}. Sync projection failures: "
            f"{sync_health['projection_failed_count']}."
        )

    @staticmethod
    def _is_disallowed_request(message: str) -> bool:
        disallowed_keywords = [
            "clinical",
            "diagnose",
            "diagnosis",
            "dosage",
            "dose",
            "controlled drug",
            "controlled-drug",
            "prescription override",
            "dispense without prescription",
            "approve dispensing",
            "change stock",
            "adjust stock",
            "delete sale",
            "void sale",
            "refund sale",
        ]
        return any(keyword in message for keyword in disallowed_keywords)

    @staticmethod
    def _scope_payload(
        organization_id: int,
        branch_id: Optional[int],
        period_days: int,
        sources: List[str],
    ) -> Dict[str, Any]:
        return {
            "organization_id": organization_id,
            "branch_id": branch_id,
            "period_days": period_days,
            "sources": sources,
        }

    @staticmethod
    def _safety_notes() -> List[str]:
        return [
            "Read-only assistant: it does not mutate stock, sales, users, or sync records.",
            "Uses approved reporting projections only.",
            "Does not provide clinical advice or controlled-drug dispensing approval.",
        ]
