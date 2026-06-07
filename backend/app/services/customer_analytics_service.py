"""
Customer analytics service for Phase D.

Computes retention and churn metrics, customer rankings, and product affinity
directly from the ``customers`` and ``sales`` tables.

This service is used by:
  - The customer analytics API endpoint (``/customers/analytics``)
  - The AI manager tool ``get_customer_analytics``
  - The daily Telegram briefing (retention summary block)

All queries are organization-scoped and work in the operational runtime. The
Customer table is populated only when customer-retention features are enabled.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import func, distinct
from sqlalchemy.orm import Session

from app.models.customer import Customer, CustomerFollowUp, FollowUpStatus
from app.models.sale import Sale

logger = logging.getLogger(__name__)

# Days without a purchase before a customer is considered "at risk"
CHURN_RISK_DAYS = 30
# Days without a purchase before considered "churned"
CHURNED_DAYS = 90


class CustomerAnalyticsService:
    """Compute customer retention and engagement metrics from live tables."""

    @staticmethod
    def summary(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int] = None,
        period_days: int = 30,
    ) -> Dict[str, Any]:
        """Top-level retention summary.

        Returns:
          - total_customers
          - new_customers (registered within period_days)
          - repeat_customers (≥2 purchases overall)
          - at_risk_customers (no purchase in 30–89 days)
          - churned_customers (no purchase in 90+ days)
          - consent_stats (sms/whatsapp granted counts)
          - follow_up_stats (sent/pending/failed)
          - top_customers (top 5 by total spend)
          - top_products_by_customer_count (up to 10 products bought by most customers)
        """
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=period_days)

        base_q = db.query(Customer).filter(
            Customer.organization_id == organization_id,
            Customer.is_active.is_(True),
        )
        if branch_id is not None:
            base_q = base_q.filter(Customer.branch_id == branch_id)

        total_customers: int = base_q.count()

        new_customers: int = base_q.filter(
            Customer.created_at >= period_start,
        ).count()

        # Repeat customers: those with ≥2 linked sales
        repeat_subq = (
            db.query(Sale.customer_id, func.count(Sale.id).label("purchase_count"))
            .filter(
                Sale.customer_id.is_not(None),
                Sale.organization_id == organization_id,
            )
            .group_by(Sale.customer_id)
            .having(func.count(Sale.id) >= 2)
            .subquery()
        )
        repeat_customers: int = db.query(func.count(repeat_subq.c.customer_id)).scalar() or 0

        # At-risk: last purchase 30–89 days ago
        churn_start = now - timedelta(days=CHURNED_DAYS)
        risk_start = now - timedelta(days=CHURN_RISK_DAYS)

        at_risk_subq = (
            db.query(Sale.customer_id, func.max(Sale.created_at).label("last_purchase"))
            .filter(
                Sale.customer_id.is_not(None),
                Sale.organization_id == organization_id,
            )
            .group_by(Sale.customer_id)
            .subquery()
        )
        at_risk_customers: int = (
            db.query(func.count(at_risk_subq.c.customer_id))
            .filter(
                at_risk_subq.c.last_purchase >= churn_start,
                at_risk_subq.c.last_purchase < risk_start,
            )
            .scalar()
        ) or 0

        # Churned: last purchase 90+ days ago (or never purchased)
        churned_customers: int = (
            db.query(func.count(at_risk_subq.c.customer_id))
            .filter(at_risk_subq.c.last_purchase < churn_start)
            .scalar()
        ) or 0

        # Consent stats
        sms_granted: int = base_q.filter(Customer.sms_consent == "granted").count()
        wa_granted: int  = base_q.filter(Customer.whatsapp_consent == "granted").count()

        # Follow-up stats (all-time for this org)
        fu_base = db.query(CustomerFollowUp).filter(
            CustomerFollowUp.organization_id == organization_id,
        )
        fu_sent    = fu_base.filter(CustomerFollowUp.status.in_(["sent", "delivered"])).count()
        fu_pending = fu_base.filter(CustomerFollowUp.status == FollowUpStatus.PENDING).count()
        fu_failed  = fu_base.filter(CustomerFollowUp.status == FollowUpStatus.FAILED).count()

        # Top 5 customers by total spend
        top_customers = CustomerAnalyticsService.top_customers_by_spend(
            db, organization_id=organization_id, branch_id=branch_id, limit=5
        )

        # Top products by distinct customer reach
        top_products = CustomerAnalyticsService.top_products_by_customer_reach(
            db, organization_id=organization_id, branch_id=branch_id, period_days=period_days, limit=10
        )

        return {
            "organization_id": organization_id,
            "branch_id": branch_id,
            "period_days": period_days,
            "generated_at": now.isoformat(),
            "total_customers": total_customers,
            "new_customers_in_period": new_customers,
            "repeat_customers": repeat_customers,
            "repeat_rate_pct": round(repeat_customers / total_customers * 100, 1) if total_customers else 0.0,
            "at_risk_customers": at_risk_customers,
            "churned_customers": churned_customers,
            "consent_stats": {
                "sms_granted": sms_granted,
                "whatsapp_granted": wa_granted,
                "sms_rate_pct": round(sms_granted / total_customers * 100, 1) if total_customers else 0.0,
            },
            "follow_up_stats": {
                "sent": fu_sent,
                "pending": fu_pending,
                "failed": fu_failed,
            },
            "top_customers": top_customers,
            "top_products_by_customer_reach": top_products,
        }

    @staticmethod
    def top_customers_by_spend(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Return top customers ranked by total spend across all time."""
        q = (
            db.query(
                Customer.id,
                Customer.full_name,
                Customer.phone,
                func.count(Sale.id).label("purchase_count"),
                func.coalesce(func.sum(Sale.total_amount), 0).label("total_spend"),
                func.max(Sale.created_at).label("last_purchase_at"),
            )
            .join(Sale, Sale.customer_id == Customer.id, isouter=True)
            .filter(Customer.organization_id == organization_id, Customer.is_active.is_(True))
        )
        if branch_id is not None:
            q = q.filter(Customer.branch_id == branch_id)

        rows = (
            q.group_by(Customer.id, Customer.full_name, Customer.phone)
            .order_by(func.coalesce(func.sum(Sale.total_amount), 0).desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "customer_id": row.id,
                "full_name": row.full_name,
                "phone": row.phone,
                "purchase_count": int(row.purchase_count or 0),
                "total_spend": float(row.total_spend or Decimal("0")),
                "last_purchase_at": row.last_purchase_at.isoformat() if row.last_purchase_at else None,
            }
            for row in rows
        ]

    @staticmethod
    def top_products_by_customer_reach(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int] = None,
        period_days: int = 30,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Return products that were purchased by the most distinct customers in the period.

        Uses sale_items (product_name snapshot + product_id) joined to sales
        which are linked to a registered customer.
        """
        from app.models.sale import SaleItem

        period_start = datetime.now(timezone.utc) - timedelta(days=period_days)

        q = (
            db.query(
                SaleItem.product_id,
                SaleItem.product_name,
                func.count(distinct(Sale.customer_id)).label("customer_count"),
                func.sum(SaleItem.quantity).label("total_units_sold"),
            )
            .join(Sale, Sale.id == SaleItem.sale_id)
            .filter(
                Sale.organization_id == organization_id,
                Sale.customer_id.is_not(None),
                Sale.created_at >= period_start,
            )
        )
        if branch_id is not None:
            q = q.filter(Sale.branch_id == branch_id)

        rows = (
            q.group_by(SaleItem.product_id, SaleItem.product_name)
            .order_by(func.count(distinct(Sale.customer_id)).desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "product_id": row.product_id,
                "product_name": row.product_name,
                "distinct_customers": int(row.customer_count or 0),
                "total_units_sold": int(row.total_units_sold or 0),
            }
            for row in rows
        ]
