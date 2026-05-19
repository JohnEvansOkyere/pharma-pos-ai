"""
Read-only manager assistant backed by approved cloud reporting data.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.cloud_projection import (
    CloudBatchSnapshot,
    CloudInventoryMovementFact,
    CloudProductSnapshot,
    CloudSaleFact,
)
from app.models.sync_ingestion import IngestedSyncEvent
from app.models.tenancy import Branch
from app.models.user import User
from app.services.ai_llm_provider import AIManagerLLMProvider
from app.services.ai_provider_policy_service import AIProviderPolicyService
from app.services.cloud_dead_stock_service import CloudDeadStockService
from app.services.cloud_reconciliation_service import CloudReconciliationService
from app.services.cloud_sales_trend_service import CloudSalesTrendService
from app.services.cloud_stock_velocity_service import CloudStockVelocityService


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
    PRODUCT_SNAPSHOT_SOURCE = "cloud_product_snapshots"
    BATCH_SNAPSHOT_SOURCE = "cloud_batch_snapshots"
    RECONCILIATION_SOURCE = "cloud_reconciliation_checks"

    @staticmethod
    def answer(
        db: Session,
        *,
        message: str,
        organization_id: int,
        branch_id: Optional[int],
        period_days: int,
        current_user: User,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        effective_branch_id = AIManagerService._effective_branch_id(current_user, branch_id)
        normalized_message = message.strip().lower()

        if AIManagerService._is_disallowed_request(normalized_message):
            provider_policy = AIProviderPolicyService.resolve_provider(db, organization_id=organization_id)
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
                "provider": provider_policy["provider"],
                "model": provider_policy["model"],
                "fallback_used": False,
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
        stock_risk = AIManagerService._stock_risk_summary(
            db,
            organization_id=organization_id,
            branch_id=effective_branch_id,
        )
        stock_velocity = CloudStockVelocityService.stock_velocity(
            db,
            organization_id=organization_id,
            branch_id=effective_branch_id,
            period_days=period_days,
            limit=10,
            include_stable=False,
        )
        dead_stock = CloudDeadStockService.dead_stock(
            db,
            organization_id=organization_id,
            branch_id=effective_branch_id,
            period_days=period_days,
            limit=10,
        )
        revenue_comparison = CloudSalesTrendService.revenue_comparison(
            db,
            organization_id=organization_id,
            branch_id=effective_branch_id,
            period_days=period_days,
            limit=10,
        )
        reconciliation = CloudReconciliationService.reconcile(
            db,
            organization_id=organization_id,
            branch_id=effective_branch_id,
            limit=10,
        )

        tool_results = {
            "sales_summary": sales_summary,
            "branch_sales": branch_sales,
            "inventory_summary": inventory_summary,
            "sync_health": sync_health,
            "stock_risk": stock_risk,
            "stock_velocity": stock_velocity,
            "dead_stock": dead_stock,
            "revenue_comparison": revenue_comparison,
            "reconciliation": reconciliation,
        }

        deterministic_answer = AIManagerService._compose_answer(
            normalized_message,
            sales_summary=sales_summary,
            branch_sales=branch_sales,
            inventory_summary=inventory_summary,
            sync_health=sync_health,
            stock_risk=stock_risk,
            stock_velocity=stock_velocity,
            dead_stock=dead_stock,
            revenue_comparison=revenue_comparison,
            reconciliation=reconciliation,
            period_days=period_days,
            branch_id=effective_branch_id,
        )

        # Trust gate: warn when data is stale or has projection failures.
        trust_warning = AIManagerService._build_trust_warning(sync_health, reconciliation)
        if trust_warning:
            deterministic_answer = f"DATA TRUST WARNING: {trust_warning}\n\n{deterministic_answer}"

        provider_policy = AIProviderPolicyService.resolve_provider(db, organization_id=organization_id)
        provider_result = AIManagerLLMProvider.generate_answer(
            prompt=AIManagerService._provider_prompt(
                message=message.strip(),
                deterministic_answer=deterministic_answer,
                tool_results=tool_results,
                organization_id=organization_id,
                branch_id=effective_branch_id,
                period_days=period_days,
            ),
            deterministic_answer=deterministic_answer,
            provider=provider_policy["provider"],
            model=provider_policy["model"],
            conversation_history=conversation_history or [],
        )

        return {
            "answer": provider_result["answer"],
            "data_scope": AIManagerService._scope_payload(
                organization_id,
                effective_branch_id,
                period_days,
                [
                    AIManagerService.SALES_SOURCE,
                    AIManagerService.INVENTORY_SOURCE,
                    AIManagerService.SYNC_SOURCE,
                    AIManagerService.PRODUCT_SNAPSHOT_SOURCE,
                    AIManagerService.BATCH_SNAPSHOT_SOURCE,
                    AIManagerService.RECONCILIATION_SOURCE,
                ],
            ),
            "tool_results": tool_results,
            "safety_notes": AIManagerService._safety_notes(),
            "provider": provider_result["provider"],
            "model": provider_result["model"],
            "fallback_used": provider_result["fallback_used"],
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
        sale_time = func.coalesce(CloudSaleFact.occurred_at, CloudSaleFact.created_at)
        query = db.query(
            func.count(CloudSaleFact.id).label("sales_count"),
            func.coalesce(func.sum(CloudSaleFact.total_amount), 0).label("total_revenue"),
            func.coalesce(func.sum(CloudSaleFact.item_count), 0).label("total_items"),
        ).filter(
            CloudSaleFact.organization_id == organization_id,
            sale_time >= AIManagerService._window_start(period_days),
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
        sale_time = func.coalesce(CloudSaleFact.occurred_at, CloudSaleFact.created_at)
        query = db.query(
            CloudSaleFact.branch_id,
            func.count(CloudSaleFact.id).label("sales_count"),
            func.coalesce(func.sum(CloudSaleFact.total_amount), 0).label("total_revenue"),
            func.coalesce(func.sum(CloudSaleFact.item_count), 0).label("total_items"),
        ).filter(
            CloudSaleFact.organization_id == organization_id,
            sale_time >= AIManagerService._window_start(period_days),
        )

        if branch_id is not None:
            query = query.filter(CloudSaleFact.branch_id == branch_id)

        rows = query.group_by(CloudSaleFact.branch_id).order_by(CloudSaleFact.branch_id.asc()).all()

        # Resolve branch names for richer display
        branch_names: Dict[int, str] = {}
        branch_ids = [row.branch_id for row in rows]
        if branch_ids:
            branches = db.query(Branch.id, Branch.name).filter(Branch.id.in_(branch_ids)).all()
            branch_names = {b.id: b.name for b in branches}

        return [
            {
                "branch_id": row.branch_id,
                "branch_name": branch_names.get(row.branch_id, f"Branch {row.branch_id}"),
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
        movement_time = func.coalesce(
            CloudInventoryMovementFact.occurred_at,
            CloudInventoryMovementFact.created_at,
        )

        query = db.query(
            func.count(CloudInventoryMovementFact.id).label("movement_count"),
            positive_quantity.label("total_positive_quantity"),
            negative_quantity.label("total_negative_quantity"),
            net_quantity.label("net_quantity_delta"),
        ).filter(
            CloudInventoryMovementFact.organization_id == organization_id,
            movement_time >= AIManagerService._window_start(period_days),
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
    def _stock_risk_summary(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        expiry_warning_days: int = 90,
    ) -> Dict[str, Any]:
        product_query = db.query(CloudProductSnapshot).filter(
            CloudProductSnapshot.organization_id == organization_id,
            CloudProductSnapshot.is_active.is_(True),
        )
        batch_query = db.query(CloudBatchSnapshot).filter(
            CloudBatchSnapshot.organization_id == organization_id,
            CloudBatchSnapshot.quantity > 0,
            CloudBatchSnapshot.is_quarantined.is_(False),
        )
        if branch_id is not None:
            product_query = product_query.filter(CloudProductSnapshot.branch_id == branch_id)
            batch_query = batch_query.filter(CloudBatchSnapshot.branch_id == branch_id)

        today = date.today()
        warning_date = today + timedelta(days=expiry_warning_days)
        products = product_query.all()
        batches = batch_query.all()
        low_stock_products = [
            {"product_id": product.local_product_id, "name": product.name, "stock": product.total_stock}
            for product in products
            if 0 < product.total_stock <= product.low_stock_threshold
        ]
        out_of_stock_products = [
            {"product_id": product.local_product_id, "name": product.name, "stock": product.total_stock}
            for product in products
            if product.total_stock <= 0
        ]
        expiry_batches = [
            {
                "product_id": batch.local_product_id,
                "batch_id": batch.local_batch_id,
                "batch_number": batch.batch_number,
                "quantity": batch.quantity,
                "expiry_date": batch.expiry_date.isoformat(),
                "days_until_expiry": (batch.expiry_date - today).days,
                "status": "expired" if batch.expiry_date < today else "near_expiry",
            }
            for batch in batches
            if batch.expiry_date <= warning_date
        ]
        return {
            "low_stock_count": len(low_stock_products),
            "out_of_stock_count": len(out_of_stock_products),
            "near_expiry_batch_count": sum(1 for batch in expiry_batches if batch["status"] == "near_expiry"),
            "expired_batch_count": sum(1 for batch in expiry_batches if batch["status"] == "expired"),
            "expiry_warning_days": expiry_warning_days,
            "low_stock_products": low_stock_products[:10],
            "out_of_stock_products": out_of_stock_products[:10],
            "expiry_batches": expiry_batches[:10],
        }

    @staticmethod
    def _compose_answer(
        message: str,
        *,
        sales_summary: Dict[str, Any],
        branch_sales: List[Dict[str, Any]],
        inventory_summary: Dict[str, Any],
        sync_health: Dict[str, Any],
        stock_risk: Dict[str, Any],
        stock_velocity: List[Dict[str, Any]],
        dead_stock: List[Dict[str, Any]],
        revenue_comparison: Dict[str, Any],
        reconciliation: Dict[str, Any],
        period_days: int,
        branch_id: Optional[int],
    ) -> str:
        scope = f"branch {branch_id}" if branch_id is not None else "all permitted branches"
        top_branch = max(branch_sales, key=lambda row: row["total_revenue"], default=None)

        if any(keyword in message for keyword in ["risk", "expiry", "expire", "expired", "low stock", "out of stock"]):
            top_velocity_risk = stock_velocity[0] if stock_velocity else None
            velocity_sentence = ""
            if top_velocity_risk:
                days_remaining = top_velocity_risk["days_of_stock_remaining"]
                days_text = f"{days_remaining} day(s)" if days_remaining is not None else "unknown days"
                velocity_sentence = (
                    f" Highest velocity risk: {top_velocity_risk['product_name']} "
                    f"({top_velocity_risk['status']}, {days_text} remaining)."
                )
            return (
                f"For {scope}, stock risk shows {stock_risk['out_of_stock_count']} out-of-stock product(s), "
                f"{stock_risk['low_stock_count']} low-stock product(s), "
                f"{stock_risk['expired_batch_count']} expired batch(es), and "
                f"{stock_risk['near_expiry_batch_count']} batch(es) expiring within "
                f"{stock_risk['expiry_warning_days']} day(s). Investigate expired and out-of-stock items first."
                f"{velocity_sentence}"
            )

        if any(keyword in message for keyword in ["velocity", "days of stock", "days remaining", "stock remaining", "reorder", "buy"]):
            if not stock_velocity:
                return (
                    f"For {scope}, I do not have enough projected sale movement data in the last "
                    f"{period_days} day(s) to rank products by velocity."
                )
            top_items = stock_velocity[:3]
            item_text = "; ".join(
                (
                    f"{item['product_name']}: {item['status']}, "
                    f"{item['average_daily_units_sold']} unit(s)/day, "
                    f"{item['days_of_stock_remaining'] if item['days_of_stock_remaining'] is not None else 'unknown'} day(s) remaining"
                )
                for item in top_items
            )
            return (
                f"For {scope}, the top stock velocity priorities over the last {period_days} day(s) are: "
                f"{item_text}. Prioritize out-of-stock, critical, and urgent items before stable lines."
            )

        if any(keyword in message for keyword in ["dead stock", "dead_stock", "slow mover", "slow_mover", "not selling", "no sales", "stagnant", "dormant"]):
            dead_stock_items = [item for item in dead_stock if item["status"] == "dead_stock"]
            slow_mover_items = [item for item in dead_stock if item["status"] == "slow_mover"]
            if not dead_stock:
                return (
                    f"For {scope}, no dead stock or slow movers were detected in the last {period_days} day(s) "
                    "based on projected cloud movement facts."
                )
            top_dead = dead_stock_items[0] if dead_stock_items else None
            dead_text = (
                f" Top dead-stock item: {top_dead['product_name']} ({top_dead['total_stock']} units on hand, "
                f"last sale {top_dead['last_sale_date'] or 'never recorded'})."
            ) if top_dead else ""
            return (
                f"For {scope}, {len(dead_stock_items)} product(s) are dead stock (zero sales in {period_days} day(s)) "
                f"and {len(slow_mover_items)} product(s) are slow movers (very low velocity).{dead_text} "
                "Consider clearance promotions, write-off review, or supplier returns for expired or overstocked lines."
            )

        if any(keyword in message for keyword in ["reconcile", "reconciliation", "data quality", "trust", "accurate", "reliable"]):
            if reconciliation["critical_issue_count"] or reconciliation["high_issue_count"]:
                return (
                    f"For {scope}, cloud reconciliation found {reconciliation['issue_count']} issue(s): "
                    f"{reconciliation['critical_issue_count']} critical, {reconciliation['high_issue_count']} high, and "
                    f"{reconciliation['medium_issue_count']} medium. Review these before relying on cloud reports for "
                    "purchasing or stock decisions."
                )
            return (
                f"For {scope}, cloud reconciliation found no critical or high severity issues across "
                f"{reconciliation['product_snapshot_count']} product snapshot(s), "
                f"{reconciliation['batch_snapshot_count']} batch snapshot(s), and "
                f"{reconciliation['movement_fact_count']} movement fact(s)."
            )

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

        if any(keyword in message for keyword in ["trend", "week", "compare", "drop", "growth", "anomaly", "no sales"]):
            anomaly_rows = [
                item
                for item in revenue_comparison["branches"]
                if item["status"] in {"no_sales_current", "severe_drop", "drop"}
            ]
            if anomaly_rows:
                top = anomaly_rows[0]
                change = top["revenue_change_percent"]
                change_text = f"{change:.1f}%" if change is not None else "from no baseline"
                return (
                    f"For {scope}, revenue changed from GHS {revenue_comparison['previous_revenue']:.2f} "
                    f"to GHS {revenue_comparison['current_revenue']:.2f} over the compared "
                    f"{period_days}-day windows. Highest branch anomaly: {top['branch_name']} "
                    f"({top['status']}, {change_text}, GHS {top['revenue_change']:.2f})."
                )
            change = revenue_comparison["revenue_change_percent"]
            change_text = f"{change:.1f}%" if change is not None else "no previous baseline"
            return (
                f"For {scope}, revenue changed from GHS {revenue_comparison['previous_revenue']:.2f} "
                f"to GHS {revenue_comparison['current_revenue']:.2f} over the compared "
                f"{period_days}-day windows ({change_text}). No branch drop anomalies were flagged."
            )

        if any(keyword in message for keyword in ["branch", "best", "perform"]):
            if top_branch is None:
                return f"For {scope}, no branch sales have been projected in the last {period_days} day(s)."
            branch_label = top_branch.get("branch_name") or f"Branch {top_branch['branch_id']}"
            return (
                f"In the last {period_days} day(s), {branch_label} is the strongest projected branch by revenue "
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
    def _build_trust_warning(
        sync_health: Dict[str, Any],
        reconciliation: Dict[str, Any],
    ) -> Optional[str]:
        """Return a trust warning string if data quality is degraded, else None."""
        warnings: List[str] = []
        if sync_health.get("projection_failed_count", 0) > 0:
            warnings.append(
                f"{sync_health['projection_failed_count']} projection failure(s) - some events are not reflected in reports"
            )
        last_received = sync_health.get("last_received_at")
        if last_received:
            try:
                from datetime import datetime as _dt
                last_ts = _dt.fromisoformat(last_received)
                if last_ts.tzinfo is None:
                    last_ts = last_ts.replace(tzinfo=timezone.utc)
                stale_hours = (datetime.now(timezone.utc) - last_ts).total_seconds() / 3600
                if stale_hours > 24:
                    warnings.append(
                        f"No sync events received in {stale_hours:.0f} hour(s) - data may be outdated"
                    )
            except (ValueError, TypeError):
                pass
        elif sync_health.get("ingested_event_count", 0) == 0:
            warnings.append("No sync events have ever been received for this scope")
        critical = reconciliation.get("critical_issue_count", 0)
        high = reconciliation.get("high_issue_count", 0)
        if critical or high:
            warnings.append(
                f"Cloud reconciliation has {critical} critical and {high} high severity issue(s)"
            )
        return "; ".join(warnings) if warnings else None

    @staticmethod
    def _provider_prompt(
        *,
        message: str,
        deterministic_answer: str,
        tool_results: Dict[str, Any],
        organization_id: int,
        branch_id: Optional[int],
        period_days: int,
    ) -> str:
        scope = f"organization_id={organization_id}, branch_id={branch_id}, period_days={period_days}"
        return (
            "User question:\n"
            f"{message}\n\n"
            "Authorized reporting scope:\n"
            f"{scope}\n\n"
            "Approved reporting data:\n"
            f"{tool_results}\n\n"
            "Deterministic baseline answer:\n"
            f"{deterministic_answer}\n\n"
            "Write a concise manager-facing answer using only the approved reporting data. "
            "Do not add clinical, dispensing, controlled-drug, patient, or stock mutation advice."
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
