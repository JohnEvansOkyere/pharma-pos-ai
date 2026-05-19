"""
On-demand CEO briefing: ranked findings from deterministic cloud analyzers.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.services.cloud_dead_stock_service import CloudDeadStockService
from app.services.cloud_reconciliation_service import CloudReconciliationService
from app.services.cloud_sales_trend_service import CloudSalesTrendService
from app.services.cloud_stock_velocity_service import CloudStockVelocityService
from app.services.ai_manager_service import AIManagerService


_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2}


class AIBriefingService:
    """Generate a ranked list of findings from approved cloud data."""

    @staticmethod
    def briefing(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        period_days: int,
        max_findings: int = 5,
    ) -> dict[str, Any]:
        stock_velocity = CloudStockVelocityService.stock_velocity(
            db,
            organization_id=organization_id,
            branch_id=branch_id,
            period_days=period_days,
            limit=50,
            include_stable=False,
        )
        dead_stock = CloudDeadStockService.dead_stock(
            db,
            organization_id=organization_id,
            branch_id=branch_id,
            period_days=period_days,
            limit=50,
        )
        revenue_comparison = CloudSalesTrendService.revenue_comparison(
            db,
            organization_id=organization_id,
            branch_id=branch_id,
            period_days=period_days,
            limit=20,
        )
        stock_risk = AIManagerService._stock_risk_summary(
            db,
            organization_id=organization_id,
            branch_id=branch_id,
        )
        sync_health = AIManagerService._sync_health(
            db,
            organization_id=organization_id,
            branch_id=branch_id,
        )
        reconciliation = CloudReconciliationService.reconcile(
            db,
            organization_id=organization_id,
            branch_id=branch_id,
            limit=10,
        )

        findings: list[dict[str, Any]] = []
        findings.extend(AIBriefingService._velocity_findings(stock_velocity))
        findings.extend(AIBriefingService._expiry_findings(stock_risk))
        findings.extend(AIBriefingService._dead_stock_findings(dead_stock, period_days))
        findings.extend(AIBriefingService._revenue_drop_findings(revenue_comparison, period_days))
        findings.extend(AIBriefingService._sync_findings(sync_health))
        findings.extend(AIBriefingService._reconciliation_findings(reconciliation))

        findings.sort(key=lambda f: (_SEVERITY_RANK.get(f["severity"], 99), -f["affected_count"]))
        top_findings = findings[:max_findings]

        data_trust_status, data_trust_notes = AIBriefingService._data_trust(sync_health, reconciliation)

        return {
            "organization_id": organization_id,
            "branch_id": branch_id,
            "period_days": period_days,
            "data_trust_status": data_trust_status,
            "data_trust_notes": data_trust_notes,
            "finding_count": len(findings),
            "findings": top_findings,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # --- Finding generators ---

    @staticmethod
    def _velocity_findings(stock_velocity: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out_of_stock = [i for i in stock_velocity if i["status"] == "out_of_stock"]
        critical = [i for i in stock_velocity if i["status"] == "critical"]
        urgent = [i for i in stock_velocity if i["status"] == "urgent"]
        findings = []

        if out_of_stock:
            names = ", ".join(i["product_name"] for i in out_of_stock[:3])
            extra = f" and {len(out_of_stock) - 3} more" if len(out_of_stock) > 3 else ""
            findings.append({
                "type": "stock_out",
                "severity": "critical",
                "title": f"{len(out_of_stock)} product(s) out of stock",
                "summary": f"These products have zero stock but active demand: {names}{extra}.",
                "affected_count": len(out_of_stock),
                "action_hint": "Replenish immediately. Loss of sale and patient safety risk.",
            })

        if critical:
            names = ", ".join(
                f"{i['product_name']} ({i['days_of_stock_remaining']:.0f}d)" if i['days_of_stock_remaining'] is not None
                else i['product_name']
                for i in critical[:3]
            )
            extra = f" and {len(critical) - 3} more" if len(critical) > 3 else ""
            findings.append({
                "type": "critical_velocity",
                "severity": "high",
                "title": f"{len(critical)} product(s) have ≤3 days of stock remaining",
                "summary": f"At current sell rate, these products stock out within 3 days: {names}{extra}.",
                "affected_count": len(critical),
                "action_hint": "Place purchase orders now or source emergency stock.",
            })

        if urgent:
            names = ", ".join(i["product_name"] for i in urgent[:3])
            extra = f" and {len(urgent) - 3} more" if len(urgent) > 3 else ""
            findings.append({
                "type": "urgent_velocity",
                "severity": "medium",
                "title": f"{len(urgent)} product(s) have ≤7 days of stock remaining",
                "summary": f"Stock will be depleted within 7 days: {names}{extra}.",
                "affected_count": len(urgent),
                "action_hint": "Order this week. Do not wait for the regular purchase cycle.",
            })

        return findings

    @staticmethod
    def _expiry_findings(stock_risk: dict[str, Any]) -> list[dict[str, Any]]:
        findings = []
        if stock_risk["expired_batch_count"] > 0:
            findings.append({
                "type": "expired_batch",
                "severity": "critical",
                "title": f"{stock_risk['expired_batch_count']} expired batch(es) still in stock",
                "summary": "Expired stock must not be dispensed. Quarantine immediately.",
                "affected_count": stock_risk["expired_batch_count"],
                "action_hint": "Quarantine expired batches and initiate write-off or supplier return process.",
            })
        if stock_risk["near_expiry_batch_count"] > 0:
            findings.append({
                "type": "near_expiry",
                "severity": "medium",
                "title": f"{stock_risk['near_expiry_batch_count']} batch(es) expiring within {stock_risk['expiry_warning_days']} days",
                "summary": "Near-expiry stock is at risk of becoming a write-off. Sell or return proactively.",
                "affected_count": stock_risk["near_expiry_batch_count"],
                "action_hint": "Prioritise FEFO dispensing and consider promotional push for near-expiry lines.",
            })
        return findings

    @staticmethod
    def _dead_stock_findings(dead_stock: list[dict[str, Any]], period_days: int) -> list[dict[str, Any]]:
        dead_items = [i for i in dead_stock if i["status"] == "dead_stock"]
        slow_items = [i for i in dead_stock if i["status"] == "slow_mover"]
        findings = []

        if dead_items:
            names = ", ".join(i["product_name"] for i in dead_items[:3])
            extra = f" and {len(dead_items) - 3} more" if len(dead_items) > 3 else ""
            findings.append({
                "type": "dead_stock",
                "severity": "medium",
                "title": f"{len(dead_items)} product(s) with zero sales in {period_days} days",
                "summary": f"No customer demand recorded for: {names}{extra}. Stock is tying up capital with no return.",
                "affected_count": len(dead_items),
                "action_hint": "Review for clearance, supplier return, or write-off. Avoid re-ordering these lines.",
            })

        if slow_items:
            findings.append({
                "type": "slow_mover",
                "severity": "medium",
                "title": f"{len(slow_items)} slow-moving product(s)",
                "summary": f"{len(slow_items)} product(s) have very low sales velocity (<0.3 units/day) over {period_days} days.",
                "affected_count": len(slow_items),
                "action_hint": "Consider promotional pricing or reducing future order quantities.",
            })

        return findings

    @staticmethod
    def _revenue_drop_findings(revenue_comparison: dict[str, Any], period_days: int) -> list[dict[str, Any]]:
        branches = revenue_comparison.get("branches", [])
        severe = [b for b in branches if b["status"] in {"severe_drop", "no_sales_current"}]
        drop = [b for b in branches if b["status"] == "drop"]
        findings = []

        if severe:
            names = ", ".join(b["branch_name"] for b in severe[:3])
            extra = f" and {len(severe) - 3} more" if len(severe) > 3 else ""
            findings.append({
                "type": "revenue_drop",
                "severity": "high",
                "title": f"{len(severe)} branch(es) with severe revenue drop",
                "summary": f"Severe revenue fall or no reported sales: {names}{extra}. Compare to prior {period_days}-day window.",
                "affected_count": len(severe),
                "action_hint": "Verify connectivity, check local outbox backlog, and contact branch manager.",
            })

        if drop:
            names = ", ".join(b["branch_name"] for b in drop[:3])
            extra = f" and {len(drop) - 3} more" if len(drop) > 3 else ""
            findings.append({
                "type": "revenue_decline",
                "severity": "medium",
                "title": f"{len(drop)} branch(es) with declining revenue",
                "summary": f"Revenue fell compared to prior {period_days}-day window: {names}{extra}.",
                "affected_count": len(drop),
                "action_hint": "Review sales patterns and discuss with branch manager.",
            })

        return findings

    @staticmethod
    def _sync_findings(sync_health: dict[str, Any]) -> list[dict[str, Any]]:
        findings = []
        if sync_health.get("projection_failed_count", 0) > 0:
            count = sync_health["projection_failed_count"]
            findings.append({
                "type": "sync_failure",
                "severity": "high",
                "title": f"{count} cloud event(s) failed to project",
                "summary": f"{count} ingested sync event(s) could not be projected into cloud read models. Reports may be incomplete.",
                "affected_count": count,
                "action_hint": "Use reconciliation tools to inspect and retry failed projections.",
            })
        last_received = sync_health.get("last_received_at")
        if last_received:
            try:
                last_ts = datetime.fromisoformat(last_received)
                if last_ts.tzinfo is None:
                    last_ts = last_ts.replace(tzinfo=timezone.utc)
                stale_hours = (datetime.now(timezone.utc) - last_ts).total_seconds() / 3600
                if stale_hours > 48:
                    findings.append({
                        "type": "stale_sync",
                        "severity": "high",
                        "title": f"No new sync events in {stale_hours:.0f} hour(s)",
                        "summary": "Cloud data has not been updated recently. Figures may not reflect current pharmacy state.",
                        "affected_count": 1,
                        "action_hint": "Check local scheduler and outbox on the pharmacy device(s).",
                    })
                elif stale_hours > 24:
                    findings.append({
                        "type": "stale_sync",
                        "severity": "medium",
                        "title": f"Sync data is {stale_hours:.0f} hour(s) old",
                        "summary": "Cloud data may be slightly delayed. Verify local device is uploading.",
                        "affected_count": 1,
                        "action_hint": "Check the local sync scheduler and outbox.",
                    })
            except (ValueError, TypeError):
                pass
        elif sync_health.get("ingested_event_count", 0) == 0:
            findings.append({
                "type": "no_sync",
                "severity": "high",
                "title": "No sync data has ever been received",
                "summary": "The cloud has never received events for this scope. The briefing is based on empty data.",
                "affected_count": 1,
                "action_hint": "Verify cloud sync is enabled on the local device and the correct device UID/token is set.",
            })
        return findings

    @staticmethod
    def _reconciliation_findings(reconciliation: dict[str, Any]) -> list[dict[str, Any]]:
        findings = []
        critical = reconciliation.get("critical_issue_count", 0)
        high = reconciliation.get("high_issue_count", 0)
        if critical > 0:
            findings.append({
                "type": "reconciliation",
                "severity": "critical",
                "title": f"{critical} critical cloud reconciliation issue(s)",
                "summary": f"{critical} critical issue(s) found — cloud stock figures may not match local reality.",
                "affected_count": critical,
                "action_hint": "Resolve reconciliation issues before relying on cloud data for purchasing decisions.",
            })
        elif high > 0:
            findings.append({
                "type": "reconciliation",
                "severity": "high",
                "title": f"{high} high-severity cloud reconciliation issue(s)",
                "summary": f"{high} high-severity reconciliation issue(s) detected — some cloud data may be inaccurate.",
                "affected_count": high,
                "action_hint": "Review reconciliation details and repair or acknowledge known issues.",
            })
        return findings

    @staticmethod
    def _data_trust(
        sync_health: dict[str, Any],
        reconciliation: dict[str, Any],
    ) -> tuple[str, list[str]]:
        notes: list[str] = []
        unsafe = False
        degraded = False

        if reconciliation.get("critical_issue_count", 0) > 0:
            unsafe = True
            notes.append(f"{reconciliation['critical_issue_count']} critical reconciliation issue(s)")
        if sync_health.get("projection_failed_count", 0) > 0:
            unsafe = True
            notes.append(f"{sync_health['projection_failed_count']} projection failure(s)")
        if reconciliation.get("high_issue_count", 0) > 0:
            degraded = True
            notes.append(f"{reconciliation['high_issue_count']} high-severity reconciliation issue(s)")

        last_received = sync_health.get("last_received_at")
        if last_received:
            try:
                last_ts = datetime.fromisoformat(last_received)
                if last_ts.tzinfo is None:
                    last_ts = last_ts.replace(tzinfo=timezone.utc)
                stale_hours = (datetime.now(timezone.utc) - last_ts).total_seconds() / 3600
                if stale_hours > 48:
                    degraded = True
                    notes.append(f"No sync in {stale_hours:.0f}h")
            except (ValueError, TypeError):
                pass
        elif sync_health.get("ingested_event_count", 0) == 0:
            unsafe = True
            notes.append("No sync data received")

        if unsafe:
            return "unsafe", notes
        if degraded:
            return "degraded", notes
        return "ok", notes
