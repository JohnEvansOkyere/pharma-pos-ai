"""
Weekly AI manager report generation over approved cloud reporting data.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.ai_report import AIWeeklyManagerReport
from app.models.cloud_projection import (
    CloudBatchSnapshot,
    CloudInventoryMovementFact,
    CloudProductSnapshot,
    CloudSaleFact,
)
from app.models.sync_ingestion import IngestedSyncEvent
from app.models.tenancy import Organization
from app.services.ai_report_delivery_service import AIReportDeliveryService
from app.services.ai_llm_provider import AIManagerLLMProvider
from app.services.ai_manager_service import AIManagerService


class AIWeeklyReportService:
    """Generate and persist read-only weekly reports for pharmacy managers."""

    @staticmethod
    def generate_for_organization(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int] = None,
        generated_by_user_id: Optional[int] = None,
        as_of: Optional[datetime] = None,
        deliver: bool = False,
        idempotent: bool = True,
    ) -> AIWeeklyManagerReport:
        as_of_utc = AIWeeklyReportService._coerce_utc(as_of or datetime.now(timezone.utc))
        performance_start, performance_end, action_start, action_end = AIWeeklyReportService._periods(as_of_utc)
        report_scope_key = AIWeeklyReportService.scope_key(branch_id)

        if idempotent:
            existing_report = AIWeeklyReportService._find_existing_report(
                db,
                organization_id=organization_id,
                report_scope_key=report_scope_key,
                action_start=action_start,
                action_end=action_end,
            )
            if existing_report is not None:
                return existing_report

        tool_results = AIWeeklyReportService._collect_tool_results(
            db,
            organization_id=organization_id,
            branch_id=branch_id,
            performance_start=performance_start,
            performance_end=performance_end,
            action_start=action_start,
            action_end=action_end,
        )
        sections = AIWeeklyReportService._build_sections(
            tool_results=tool_results,
            performance_start=performance_start,
            performance_end=performance_end,
            action_start=action_start,
            action_end=action_end,
        )
        deterministic_summary = AIWeeklyReportService._deterministic_executive_summary(
            organization_id=organization_id,
            branch_id=branch_id,
            sections=sections,
            performance_start=performance_start,
            performance_end=performance_end,
            action_start=action_start,
            action_end=action_end,
        )
        provider_result = AIManagerLLMProvider.generate_answer(
            prompt=AIWeeklyReportService._provider_prompt(
                organization_id=organization_id,
                branch_id=branch_id,
                performance_start=performance_start,
                performance_end=performance_end,
                action_start=action_start,
                action_end=action_end,
                tool_results=tool_results,
                sections=sections,
                deterministic_summary=deterministic_summary,
            ),
            deterministic_answer=deterministic_summary,
        )

        report = AIWeeklyManagerReport(
            organization_id=organization_id,
            branch_id=branch_id,
            report_scope_key=report_scope_key,
            generated_by_user_id=generated_by_user_id,
            performance_period_start=performance_start,
            performance_period_end=performance_end,
            action_period_start=action_start,
            action_period_end=action_end,
            title=AIWeeklyReportService._title(performance_start, performance_end, action_start, action_end),
            executive_summary=provider_result["answer"],
            sections=sections,
            tool_results=tool_results,
            safety_notes=AIManagerService._safety_notes(),
            provider=provider_result["provider"],
            model=provider_result["model"],
            fallback_used=provider_result["fallback_used"],
            generated_at=as_of_utc,
        )
        db.add(report)
        try:
            db.commit()
            db.refresh(report)
        except IntegrityError:
            db.rollback()
            existing_report = AIWeeklyReportService._find_existing_report(
                db,
                organization_id=organization_id,
                report_scope_key=report_scope_key,
                action_start=action_start,
                action_end=action_end,
            )
            if existing_report is None:
                raise
            return existing_report
        if deliver:
            AIReportDeliveryService.deliver(db, report)
        return report

    @staticmethod
    def generate_all(
        db: Session,
        *,
        as_of: Optional[datetime] = None,
        deliver: bool = False,
        idempotent: bool = True,
    ) -> List[AIWeeklyManagerReport]:
        reports: List[AIWeeklyManagerReport] = []
        organizations = db.query(Organization).filter(Organization.is_active.is_(True)).order_by(Organization.id.asc()).all()
        for organization in organizations:
            reports.append(
                AIWeeklyReportService.generate_for_organization(
                    db,
                    organization_id=organization.id,
                    branch_id=None,
                    generated_by_user_id=None,
                    as_of=as_of,
                    deliver=deliver,
                    idempotent=idempotent,
                )
            )
        return reports

    @staticmethod
    def list_reports(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        limit: int,
    ) -> List[AIWeeklyManagerReport]:
        query = db.query(AIWeeklyManagerReport).filter(AIWeeklyManagerReport.organization_id == organization_id)
        if branch_id is not None:
            query = query.filter(AIWeeklyManagerReport.branch_id == branch_id)
        return query.order_by(AIWeeklyManagerReport.generated_at.desc(), AIWeeklyManagerReport.id.desc()).limit(limit).all()

    @staticmethod
    def scope_key(branch_id: Optional[int]) -> str:
        return "organization" if branch_id is None else f"branch:{branch_id}"

    @staticmethod
    def _find_existing_report(
        db: Session,
        *,
        organization_id: int,
        report_scope_key: str,
        action_start: date,
        action_end: date,
    ) -> Optional[AIWeeklyManagerReport]:
        return (
            db.query(AIWeeklyManagerReport)
            .filter(
                AIWeeklyManagerReport.organization_id == organization_id,
                AIWeeklyManagerReport.report_scope_key == report_scope_key,
                AIWeeklyManagerReport.action_period_start == action_start,
                AIWeeklyManagerReport.action_period_end == action_end,
            )
            .first()
        )

    @staticmethod
    def get_report(db: Session, *, report_id: int, organization_id: int) -> Optional[AIWeeklyManagerReport]:
        return (
            db.query(AIWeeklyManagerReport)
            .filter(
                AIWeeklyManagerReport.id == report_id,
                AIWeeklyManagerReport.organization_id == organization_id,
            )
            .first()
        )

    @staticmethod
    def _collect_tool_results(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        performance_start: datetime,
        performance_end: datetime,
        action_start: date,
        action_end: date,
    ) -> Dict[str, Any]:
        return {
            "sales_performance": AIWeeklyReportService._sales_performance(
                db,
                organization_id=organization_id,
                branch_id=branch_id,
                start=performance_start,
                end=performance_end,
            ),
            "branch_sales": AIWeeklyReportService._branch_sales(
                db,
                organization_id=organization_id,
                branch_id=branch_id,
                start=performance_start,
                end=performance_end,
            ),
            "inventory_movement": AIWeeklyReportService._inventory_movement(
                db,
                organization_id=organization_id,
                branch_id=branch_id,
                start=performance_start,
                end=performance_end,
            ),
            "stock_risks": AIWeeklyReportService._stock_risks(
                db,
                organization_id=organization_id,
                branch_id=branch_id,
                current_date=performance_end.date(),
                action_end=action_end,
            ),
            "sync_health": AIWeeklyReportService._sync_health(
                db,
                organization_id=organization_id,
                branch_id=branch_id,
                start=performance_start,
                end=performance_end,
            ),
        }

    @staticmethod
    def _sales_performance(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        start: datetime,
        end: datetime,
    ) -> Dict[str, Any]:
        query = db.query(
            func.count(CloudSaleFact.id).label("sales_count"),
            func.coalesce(func.sum(CloudSaleFact.total_amount), 0).label("total_revenue"),
            func.coalesce(func.sum(CloudSaleFact.item_count), 0).label("total_items"),
        ).filter(
            CloudSaleFact.organization_id == organization_id,
            CloudSaleFact.created_at >= start,
            CloudSaleFact.created_at <= end,
        )
        if branch_id is not None:
            query = query.filter(CloudSaleFact.branch_id == branch_id)
        row = query.one()
        return {
            "sales_count": int(row.sales_count or 0),
            "total_revenue": float(row.total_revenue or Decimal("0")),
            "total_items": int(row.total_items or 0),
            "average_sale_value": AIWeeklyReportService._safe_average(row.total_revenue, row.sales_count),
        }

    @staticmethod
    def _branch_sales(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        start: datetime,
        end: datetime,
    ) -> List[Dict[str, Any]]:
        query = db.query(
            CloudSaleFact.branch_id,
            func.count(CloudSaleFact.id).label("sales_count"),
            func.coalesce(func.sum(CloudSaleFact.total_amount), 0).label("total_revenue"),
            func.coalesce(func.sum(CloudSaleFact.item_count), 0).label("total_items"),
        ).filter(
            CloudSaleFact.organization_id == organization_id,
            CloudSaleFact.created_at >= start,
            CloudSaleFact.created_at <= end,
        )
        if branch_id is not None:
            query = query.filter(CloudSaleFact.branch_id == branch_id)
        rows = query.group_by(CloudSaleFact.branch_id).order_by(func.sum(CloudSaleFact.total_amount).desc()).all()
        return [
            {
                "branch_id": row.branch_id,
                "sales_count": int(row.sales_count or 0),
                "total_revenue": float(row.total_revenue or Decimal("0")),
                "total_items": int(row.total_items or 0),
                "average_sale_value": AIWeeklyReportService._safe_average(row.total_revenue, row.sales_count),
            }
            for row in rows
        ]

    @staticmethod
    def _inventory_movement(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        start: datetime,
        end: datetime,
    ) -> Dict[str, Any]:
        positive_quantity = func.coalesce(
            func.sum(case((CloudInventoryMovementFact.quantity_delta > 0, CloudInventoryMovementFact.quantity_delta), else_=0)),
            0,
        )
        negative_quantity = func.coalesce(
            func.sum(case((CloudInventoryMovementFact.quantity_delta < 0, CloudInventoryMovementFact.quantity_delta), else_=0)),
            0,
        )
        query = db.query(
            func.count(CloudInventoryMovementFact.id).label("movement_count"),
            positive_quantity.label("total_positive_quantity"),
            negative_quantity.label("total_negative_quantity"),
            func.coalesce(func.sum(CloudInventoryMovementFact.quantity_delta), 0).label("net_quantity_delta"),
        ).filter(
            CloudInventoryMovementFact.organization_id == organization_id,
            CloudInventoryMovementFact.created_at >= start,
            CloudInventoryMovementFact.created_at <= end,
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
    def _stock_risks(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        current_date: date,
        action_end: date,
    ) -> Dict[str, Any]:
        product_query = db.query(CloudProductSnapshot).filter(
            CloudProductSnapshot.organization_id == organization_id,
            CloudProductSnapshot.is_active.is_(True),
        )
        batch_query = db.query(CloudBatchSnapshot, CloudProductSnapshot).join(
            CloudProductSnapshot,
            (CloudProductSnapshot.organization_id == CloudBatchSnapshot.organization_id)
            & (CloudProductSnapshot.branch_id == CloudBatchSnapshot.branch_id)
            & (CloudProductSnapshot.local_product_id == CloudBatchSnapshot.local_product_id),
        ).filter(
            CloudBatchSnapshot.organization_id == organization_id,
            CloudBatchSnapshot.quantity > 0,
            CloudBatchSnapshot.is_quarantined.is_(False),
            CloudBatchSnapshot.expiry_date <= action_end,
            CloudProductSnapshot.is_active.is_(True),
        )
        if branch_id is not None:
            product_query = product_query.filter(CloudProductSnapshot.branch_id == branch_id)
            batch_query = batch_query.filter(CloudBatchSnapshot.branch_id == branch_id)

        products = product_query.all()
        low_stock_rows = sorted(
            [product for product in products if product.total_stock <= product.low_stock_threshold],
            key=lambda product: (product.total_stock, product.name),
        )
        expiry_rows = batch_query.order_by(CloudBatchSnapshot.expiry_date.asc(), CloudProductSnapshot.name.asc()).all()
        expiring_batches = [
            {
                "branch_id": batch.branch_id,
                "product_id": batch.local_product_id,
                "product_name": product.name,
                "sku": product.sku,
                "batch_id": batch.local_batch_id,
                "batch_number": batch.batch_number,
                "quantity": batch.quantity,
                "expiry_date": batch.expiry_date.isoformat(),
                "days_until_expiry": (batch.expiry_date - current_date).days,
                "value_at_risk": float((batch.cost_price or 0) * batch.quantity),
                "status": "expired" if batch.expiry_date < current_date else "near_expiry",
            }
            for batch, product in expiry_rows
        ]
        low_stock_products = [
            {
                "branch_id": product.branch_id,
                "product_id": product.local_product_id,
                "product_name": product.name,
                "sku": product.sku,
                "total_stock": product.total_stock,
                "low_stock_threshold": product.low_stock_threshold,
                "reorder_level": product.reorder_level,
                "units_needed": max((product.reorder_level or product.low_stock_threshold) - product.total_stock, 0),
                "status": "out_of_stock" if product.total_stock <= 0 else "low_stock",
            }
            for product in low_stock_rows
        ]
        return {
            "low_stock_count": sum(1 for product in low_stock_products if product["status"] == "low_stock"),
            "out_of_stock_count": sum(1 for product in low_stock_products if product["status"] == "out_of_stock"),
            "near_expiry_batch_count": sum(1 for batch in expiring_batches if batch["status"] == "near_expiry"),
            "expired_batch_count": sum(1 for batch in expiring_batches if batch["status"] == "expired"),
            "value_at_risk": round(sum(batch["value_at_risk"] for batch in expiring_batches), 2),
            "low_stock_products": low_stock_products[:25],
            "expiry_batches": expiring_batches[:25],
        }

    @staticmethod
    def _sync_health(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        start: datetime,
        end: datetime,
    ) -> Dict[str, Any]:
        base_query = db.query(IngestedSyncEvent).filter(IngestedSyncEvent.organization_id == organization_id)
        window_query = base_query.filter(IngestedSyncEvent.received_at >= start, IngestedSyncEvent.received_at <= end)
        if branch_id is not None:
            base_query = base_query.filter(IngestedSyncEvent.branch_id == branch_id)
            window_query = window_query.filter(IngestedSyncEvent.branch_id == branch_id)

        all_row = base_query.with_entities(
            func.count(IngestedSyncEvent.id).label("ingested_event_count"),
            func.coalesce(func.sum(case((IngestedSyncEvent.projected_at.is_not(None), 1), else_=0)), 0).label("projected_event_count"),
            func.coalesce(func.sum(case((IngestedSyncEvent.projection_error.is_not(None), 1), else_=0)), 0).label("projection_failed_count"),
            func.coalesce(func.sum(IngestedSyncEvent.duplicate_count), 0).label("duplicate_delivery_count"),
            func.max(IngestedSyncEvent.received_at).label("last_received_at"),
            func.max(IngestedSyncEvent.projected_at).label("last_projected_at"),
        ).one()
        window_row = window_query.with_entities(func.count(IngestedSyncEvent.id).label("events_received_in_period")).one()
        return {
            "ingested_event_count": int(all_row.ingested_event_count or 0),
            "projected_event_count": int(all_row.projected_event_count or 0),
            "projection_failed_count": int(all_row.projection_failed_count or 0),
            "duplicate_delivery_count": int(all_row.duplicate_delivery_count or 0),
            "events_received_in_period": int(window_row.events_received_in_period or 0),
            "last_received_at": all_row.last_received_at.isoformat() if all_row.last_received_at else None,
            "last_projected_at": all_row.last_projected_at.isoformat() if all_row.last_projected_at else None,
        }

    @staticmethod
    def _build_sections(
        *,
        tool_results: Dict[str, Any],
        performance_start: datetime,
        performance_end: datetime,
        action_start: date,
        action_end: date,
    ) -> Dict[str, Any]:
        stock = tool_results["stock_risks"]
        sync = tool_results["sync_health"]
        actions = []
        if stock["expired_batch_count"]:
            actions.append("Quarantine or review expired batches before opening sales for the week.")
        if stock["out_of_stock_count"]:
            actions.append("Replenish out-of-stock products first because active demand cannot be served.")
        if stock["near_expiry_batch_count"]:
            actions.append("Review FEFO placement and commercial handling for batches expiring in the action week.")
        if stock["low_stock_count"]:
            actions.append("Prepare purchase orders for low-stock products using reorder levels where configured.")
        if sync["projection_failed_count"]:
            actions.append("Resolve failed cloud projections before relying on the report for owner-level decisions.")
        if not actions:
            actions.append("No critical projected stock or sync risks were found; keep normal daily checks running.")

        return {
            "performance_review": {
                "period_start": performance_start.isoformat(),
                "period_end": performance_end.isoformat(),
                **tool_results["sales_performance"],
                "inventory_movement": tool_results["inventory_movement"],
            },
            "branch_performance": {
                "branches": tool_results["branch_sales"],
                "top_branch": tool_results["branch_sales"][0] if tool_results["branch_sales"] else None,
            },
            "coming_week_action_plan": {
                "period_start": action_start.isoformat(),
                "period_end": action_end.isoformat(),
                "priorities": actions,
                "low_stock_products": stock["low_stock_products"],
                "expiry_batches": stock["expiry_batches"],
                "risk_counts": {
                    "low_stock_count": stock["low_stock_count"],
                    "out_of_stock_count": stock["out_of_stock_count"],
                    "near_expiry_batch_count": stock["near_expiry_batch_count"],
                    "expired_batch_count": stock["expired_batch_count"],
                    "value_at_risk": stock["value_at_risk"],
                },
            },
            "sync_and_data_quality": sync,
            "data_limits": {
                "source": "Approved cloud projection tables only.",
                "excludes": "Patient-level records, clinical advice, dispensing overrides, and unsynced local-only events.",
            },
        }

    @staticmethod
    def _deterministic_executive_summary(
        *,
        organization_id: int,
        branch_id: Optional[int],
        sections: Dict[str, Any],
        performance_start: datetime,
        performance_end: datetime,
        action_start: date,
        action_end: date,
    ) -> str:
        performance = sections["performance_review"]
        risks = sections["coming_week_action_plan"]["risk_counts"]
        sync = sections["sync_and_data_quality"]
        scope = f"organization {organization_id}" if branch_id is None else f"organization {organization_id}, branch {branch_id}"
        return (
            f"Weekly manager report for {scope}. Performance window: "
            f"{performance_start.date().isoformat()} to {performance_end.date().isoformat()}. "
            f"Projected sales were GHS {performance['total_revenue']:.2f} from {performance['sales_count']} sale(s), "
            f"with {performance['total_items']} item(s) sold. Coming-week action window: "
            f"{action_start.isoformat()} to {action_end.isoformat()}. Priority risks are "
            f"{risks['out_of_stock_count']} out-of-stock product(s), {risks['low_stock_count']} low-stock product(s), "
            f"{risks['expired_batch_count']} expired batch(es), and {risks['near_expiry_batch_count']} near-expiry batch(es), "
            f"with projected expiry value at risk of GHS {risks['value_at_risk']:.2f}. "
            f"Sync health shows {sync['projected_event_count']} projected event(s), "
            f"{sync['projection_failed_count']} projection failure(s), and "
            f"{sync['duplicate_delivery_count']} duplicate delivery attempt(s)."
        )

    @staticmethod
    def _provider_prompt(
        *,
        organization_id: int,
        branch_id: Optional[int],
        performance_start: datetime,
        performance_end: datetime,
        action_start: date,
        action_end: date,
        tool_results: Dict[str, Any],
        sections: Dict[str, Any],
        deterministic_summary: str,
    ) -> str:
        return (
            "Create a weekly pharmacy manager report executive summary.\n"
            f"Scope: organization_id={organization_id}, branch_id={branch_id}.\n"
            f"Performance window: {performance_start.isoformat()} to {performance_end.isoformat()}.\n"
            f"Action window: {action_start.isoformat()} to {action_end.isoformat()}.\n\n"
            f"Approved reporting data: {tool_results}\n\n"
            f"Structured report sections: {sections}\n\n"
            f"Deterministic baseline: {deterministic_summary}\n\n"
            "Use only the supplied aggregate reporting data. Focus on manager decisions: "
            "what happened last week, what needs attention next week, stock-risk priorities, "
            "sync/data-quality concerns, and operational follow-up. Do not provide clinical advice, "
            "controlled-drug guidance, dispensing approval, or stock mutation instructions."
        )

    @staticmethod
    def _periods(as_of: datetime) -> Tuple[datetime, datetime, date, date]:
        performance_end = as_of
        performance_start = as_of - timedelta(days=7)
        days_until_monday = (7 - as_of.date().weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        action_start = as_of.date() + timedelta(days=days_until_monday)
        action_end = action_start + timedelta(days=6)
        return performance_start, performance_end, action_start, action_end

    @staticmethod
    def _coerce_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _safe_average(total: Any, count: Any) -> float:
        if not count:
            return 0.0
        return float((total or Decimal("0")) / count)

    @staticmethod
    def _title(performance_start: datetime, performance_end: datetime, action_start: date, action_end: date) -> str:
        return (
            f"Weekly Manager Report: {performance_start.date().isoformat()} to "
            f"{performance_end.date().isoformat()} | Action Plan {action_start.isoformat()} to {action_end.isoformat()}"
        )
