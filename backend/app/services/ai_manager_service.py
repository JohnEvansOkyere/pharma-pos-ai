"""
Read-only manager assistant backed by approved cloud reporting data.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

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
from app.services.customer_analytics_service import CustomerAnalyticsService


TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_sales_summary",
            "description": (
                "Get total revenue (GHS), transaction count, and item count "
                "for the reporting period across permitted branches."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "enum": ["today", "yesterday", "period"],
                        "description": (
                            "'today' = today only, 'yesterday' = yesterday only, "
                            "'period' = configured reporting window (default)."
                        ),
                    }
                },
                "required": ["period"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_branch_sales",
            "description": "Get sales broken down by branch for the selected period, ranked by revenue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "enum": ["today", "yesterday", "period"],
                    }
                },
                "required": ["period"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_sales",
            "description": "Get the top-selling products by units sold for the selected period.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "enum": ["today", "yesterday", "period"],
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 20,
                        "description": "Number of top products to return (default 10).",
                    },
                },
                "required": ["period"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_inventory_summary",
            "description": (
                "Get aggregate inventory movement totals (units received vs dispensed) "
                "for the selected period."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "enum": ["today", "yesterday", "period"],
                    }
                },
                "required": ["period"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sync_health",
            "description": (
                "Get sync and data-projection health: event counts, projection failures, "
                "duplicate deliveries, and last sync timestamps."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_risk",
            "description": (
                "Get stock risk summary: out-of-stock products, low-stock products, "
                "expired batches, and batches nearing expiry."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expiry_warning_days": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 365,
                        "description": "Days ahead to flag near-expiry batches (default 90).",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_velocity",
            "description": (
                "Get stock velocity rankings: products ordered by daily sales rate "
                "with estimated days-of-stock remaining. Use for reorder planning."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 20,
                        "description": "Number of products to return (default 10).",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dead_stock",
            "description": (
                "Get dead stock and slow movers: products with zero or very low sales "
                "over the reporting period. Use for clearance or write-off decisions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 20,
                        "description": "Number of products to return (default 10).",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_revenue_comparison",
            "description": (
                "Compare revenue between the current period and the previous equivalent period. "
                "Flags branches with revenue drops, growth, or zero sales."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_reconciliation",
            "description": (
                "Get cloud data reconciliation results: checks product snapshot vs movement fact "
                "consistency. Use when assessing report reliability."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 50,
                        "description": "Number of issues to return (default 10).",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_analytics",
            "description": (
                "Get customer retention analytics: total registered customers, "
                "new customers in the period, repeat-purchase rate, at-risk "
                "customers (no purchase in 30–89 days), churned customers "
                "(90+ days silent), SMS/WhatsApp consent rates, follow-up "
                "delivery stats, top customers by spend, and the top products "
                "most frequently purchased by registered customers. "
                "Only available in online_pos mode where customers are registered."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


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
        current_user: Optional[User] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        effective_branch_id = AIManagerService._effective_branch_id(current_user, branch_id)
        normalized_message = message.strip().lower()
        reporting_window = AIManagerService._reporting_window(normalized_message, period_days)
        effective_period_days = int(reporting_window["period_days"])

        if AIManagerService._is_disallowed_request(normalized_message):
            provider_policy = AIProviderPolicyService.resolve_provider(db, organization_id=organization_id)
            return {
                "answer": REFUSAL_MESSAGE,
                "data_scope": AIManagerService._scope_payload(
                    organization_id,
                    effective_branch_id,
                    effective_period_days,
                    [],
                ),
                "tool_results": {},
                "tool_trace": [],
                "verification": {"verified": True, "unsupported_numbers": []},
                "safety_notes": AIManagerService._safety_notes(),
                "provider": provider_policy["provider"],
                "model": provider_policy["model"],
                "fallback_used": False,
                "refused": True,
            }

        start_at = reporting_window["start_at"]
        end_at = reporting_window["end_at"]

        sales_summary = AIManagerService._sales_summary(
            db, organization_id=organization_id, branch_id=effective_branch_id,
            start_at=start_at, end_at=end_at,
        )
        branch_sales = AIManagerService._branch_sales(
            db, organization_id=organization_id, branch_id=effective_branch_id,
            start_at=start_at, end_at=end_at,
        )
        inventory_summary = AIManagerService._inventory_summary(
            db, organization_id=organization_id, branch_id=effective_branch_id,
            start_at=start_at, end_at=end_at,
        )
        product_sales = AIManagerService._product_sales(
            db, organization_id=organization_id, branch_id=effective_branch_id,
            start_at=start_at, end_at=end_at, limit=10,
        )
        sync_health = AIManagerService._sync_health(
            db, organization_id=organization_id, branch_id=effective_branch_id,
        )
        stock_risk = AIManagerService._stock_risk_summary(
            db, organization_id=organization_id, branch_id=effective_branch_id,
        )
        stock_velocity = CloudStockVelocityService.stock_velocity(
            db, organization_id=organization_id, branch_id=effective_branch_id,
            period_days=effective_period_days, limit=10, include_stable=False,
        )
        dead_stock = CloudDeadStockService.dead_stock(
            db, organization_id=organization_id, branch_id=effective_branch_id,
            period_days=effective_period_days, limit=10,
        )
        revenue_comparison = CloudSalesTrendService.revenue_comparison(
            db, organization_id=organization_id, branch_id=effective_branch_id,
            period_days=effective_period_days, limit=10,
        )
        reconciliation = CloudReconciliationService.reconcile(
            db, organization_id=organization_id, branch_id=effective_branch_id, limit=10,
        )

        # Customer analytics — from live Customer/Sale tables (available in both modes)
        try:
            customer_analytics = CustomerAnalyticsService.summary(
                db, organization_id=organization_id, branch_id=effective_branch_id,
                period_days=effective_period_days,
            )
        except Exception:
            customer_analytics = {"error": "customer analytics unavailable"}

        tool_results = {
            "time_window": {
                "label": reporting_window["label"],
                "start_at": start_at.isoformat(),
                "end_at": end_at.isoformat(),
                "period_days": effective_period_days,
            },
            "sales_summary": sales_summary,
            "branch_sales": branch_sales,
            "product_sales": product_sales,
            "inventory_summary": inventory_summary,
            "sync_health": sync_health,
            "stock_risk": stock_risk,
            "stock_velocity": stock_velocity,
            "dead_stock": dead_stock,
            "revenue_comparison": revenue_comparison,
            "reconciliation": reconciliation,
            "customer_analytics": customer_analytics,
        }

        trust_warning = AIManagerService._build_trust_warning(sync_health, reconciliation)
        provider_policy = AIProviderPolicyService.resolve_provider(db, organization_id=organization_id)
        provider = provider_policy["provider"]
        model = provider_policy["model"]

        deterministic_answer = AIManagerService._compose_answer(
            normalized_message,
            sales_summary=sales_summary, branch_sales=branch_sales,
            inventory_summary=inventory_summary, sync_health=sync_health,
            stock_risk=stock_risk, stock_velocity=stock_velocity,
            dead_stock=dead_stock, revenue_comparison=revenue_comparison,
            reconciliation=reconciliation, period_days=effective_period_days,
            window_label=reporting_window["label"], product_sales=product_sales,
            branch_id=effective_branch_id, customer_analytics=customer_analytics,
        )
        if trust_warning:
            deterministic_answer = f"DATA TRUST WARNING: {trust_warning}\n\n{deterministic_answer}"

        if AIManagerLLMProvider.is_external_provider_configured(provider, model):
            provider_result = AIManagerLLMProvider.generate_answer_with_tools(
                message=message.strip(),
                system_prompt=AIManagerService._ceo_system_prompt(
                    organization_id=organization_id,
                    branch_id=effective_branch_id,
                    window_label=reporting_window["label"],
                    trust_warning=trust_warning,
                ),
                tools=TOOL_SCHEMAS,
                tool_dispatcher=AIManagerService._make_tool_dispatcher(
                    db,
                    organization_id=organization_id,
                    branch_id=effective_branch_id,
                    reporting_window=reporting_window,
                    prefetched=tool_results,
                ),
                conversation_history=conversation_history or [],
                provider=provider,
                model=model,
                fallback_summary=deterministic_answer,
            )
        else:
            provider_result = {
                "answer": deterministic_answer,
                "provider": provider,
                "model": model,
                "fallback_used": False,
                "tool_trace": [],
            }

        verification = AIManagerService._verify_answer_numbers(
            provider_result["answer"],
            evidence={
                "tool_results": tool_results,
                "tool_trace": provider_result.get("tool_trace", []),
            },
        )
        if not verification["verified"]:
            provider_result = {
                **provider_result,
                "answer": deterministic_answer,
                "fallback_used": True,
            }
            verification["fallback_reason"] = "unsupported_numeric_claims"

        return {
            "answer": provider_result["answer"],
            "data_scope": AIManagerService._scope_payload(
                organization_id,
                effective_branch_id,
                effective_period_days,
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
            "tool_trace": provider_result.get("tool_trace", []),
            "verification": verification,
            "safety_notes": AIManagerService._safety_notes(),
            "provider": provider_result["provider"],
            "model": provider_result["model"],
            "fallback_used": provider_result["fallback_used"],
            "refused": False,
        }

    @staticmethod
    def _effective_branch_id(current_user: Optional[User], requested_branch_id: Optional[int]) -> Optional[int]:
        if current_user is not None and current_user.branch_id is not None:
            return current_user.branch_id
        return requested_branch_id

    @staticmethod
    def _verify_answer_numbers(answer: str, *, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """
        Lightweight guardrail: if an external LLM states concrete numeric claims that
        do not appear anywhere in the approved evidence, reject the answer and fall
        back to deterministic text. This is intentionally conservative and focused
        on currency/count-style numbers, not dates.
        """
        if not answer:
            return {"verified": True, "unsupported_numbers": []}

        allowed_values = AIManagerService._collect_numeric_evidence(evidence)
        unsupported: List[str] = []
        for match in re.finditer(r"(?<![\w-])(?:GHS\s*)?-?\d+(?:,\d{3})*(?:\.\d+)?%?", answer, flags=re.IGNORECASE):
            token = match.group(0).strip()
            number_text = token.upper().replace("GHS", "").replace(",", "").replace("%", "").strip()
            if not number_text:
                continue
            try:
                value = float(number_text)
            except ValueError:
                continue
            if value >= 1900 and value <= 2100 and not token.upper().startswith("GHS"):
                continue
            if AIManagerService._numeric_value_supported(value, allowed_values):
                continue
            unsupported.append(token)

        return {
            "verified": len(unsupported) == 0,
            "unsupported_numbers": unsupported,
        }

    @staticmethod
    def _collect_numeric_evidence(value: Any) -> List[float]:
        results: List[float] = []
        if isinstance(value, bool) or value is None:
            return results
        if isinstance(value, (int, float, Decimal)):
            results.append(float(value))
            return results
        if isinstance(value, dict):
            for child in value.values():
                results.extend(AIManagerService._collect_numeric_evidence(child))
        elif isinstance(value, list):
            for child in value:
                results.extend(AIManagerService._collect_numeric_evidence(child))
        return results

    @staticmethod
    def _numeric_value_supported(value: float, allowed_values: List[float]) -> bool:
        for allowed in allowed_values:
            if abs(value - allowed) <= max(0.01, abs(allowed) * 0.001):
                return True
        return False

    @staticmethod
    def _window_start(period_days: int) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=period_days)

    @staticmethod
    def _ceo_system_prompt(
        *,
        organization_id: int,
        branch_id: Optional[int],
        window_label: str,
        trust_warning: Optional[str],
    ) -> str:
        scope = f"Branch {branch_id}" if branch_id is not None else "all branches"
        prompt = (
            f"You are a business intelligence assistant for a pharmacy group "
            f"({scope}, reporting window: {window_label}). "
            "You have access to real-time business data through the provided tools. "
            "Call the relevant tool(s) to answer the question, then reason over "
            "the results to give a concise, actionable answer in plain business language. "
            "Never fabricate figures — only state what the tool results contain. "
            "Always state the reporting window and branch scope explicitly in your answer. "
            "Do not reference internal database table names, column names, or IDs. "
            "Do not provide clinical advice, patient records, prescription overrides, "
            "controlled-drug guidance, or stock mutations."
        )
        if trust_warning:
            prompt += f"\n\nDATA QUALITY ALERT: {trust_warning} — include this caveat in your answer."
        return prompt

    @staticmethod
    def _make_tool_dispatcher(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        reporting_window: Dict[str, Any],
        prefetched: Dict[str, Any],
    ) -> Callable[[str, Dict[str, Any]], Any]:
        """Return a dispatcher that serves pre-fetched data for the default period and
        executes fresh DB queries when the LLM requests today/yesterday."""
        period_days = int(reporting_window["period_days"])
        _CACHE_MAP = {
            "get_sales_summary": "sales_summary",
            "get_branch_sales": "branch_sales",
            "get_product_sales": "product_sales",
            "get_inventory_summary": "inventory_summary",
            "get_sync_health": "sync_health",
            "get_stock_risk": "stock_risk",
            "get_stock_velocity": "stock_velocity",
            "get_dead_stock": "dead_stock",
            "get_revenue_comparison": "revenue_comparison",
            "get_reconciliation": "reconciliation",
            "get_customer_analytics": "customer_analytics",
        }

        def _resolve_window(period: str):
            now = datetime.now(timezone.utc)
            today_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)
            if period == "today":
                return today_start, now
            if period == "yesterday":
                yesterday = today_start - timedelta(days=1)
                return yesterday, today_start
            return reporting_window["start_at"], reporting_window["end_at"]

        def _dispatch(tool_name: str, arguments: Dict[str, Any]) -> Any:
            period = arguments.get("period", "period")
            limit = int(arguments.get("limit", 10))

            if period == "period":
                cache_key = _CACHE_MAP.get(tool_name)
                if cache_key and cache_key in prefetched:
                    return prefetched[cache_key]

            start_at, end_at = _resolve_window(period)

            if tool_name == "get_sales_summary":
                return AIManagerService._sales_summary(
                    db, organization_id=organization_id, branch_id=branch_id,
                    start_at=start_at, end_at=end_at,
                )
            if tool_name == "get_branch_sales":
                return AIManagerService._branch_sales(
                    db, organization_id=organization_id, branch_id=branch_id,
                    start_at=start_at, end_at=end_at,
                )
            if tool_name == "get_product_sales":
                return AIManagerService._product_sales(
                    db, organization_id=organization_id, branch_id=branch_id,
                    start_at=start_at, end_at=end_at, limit=limit,
                )
            if tool_name == "get_inventory_summary":
                return AIManagerService._inventory_summary(
                    db, organization_id=organization_id, branch_id=branch_id,
                    start_at=start_at, end_at=end_at,
                )
            if tool_name == "get_sync_health":
                return AIManagerService._sync_health(
                    db, organization_id=organization_id, branch_id=branch_id,
                )
            if tool_name == "get_stock_risk":
                expiry_warning_days = int(arguments.get("expiry_warning_days", 90))
                return AIManagerService._stock_risk_summary(
                    db, organization_id=organization_id, branch_id=branch_id,
                    expiry_warning_days=expiry_warning_days,
                )
            if tool_name == "get_stock_velocity":
                return CloudStockVelocityService.stock_velocity(
                    db, organization_id=organization_id, branch_id=branch_id,
                    period_days=period_days, limit=limit, include_stable=False,
                )
            if tool_name == "get_dead_stock":
                return CloudDeadStockService.dead_stock(
                    db, organization_id=organization_id, branch_id=branch_id,
                    period_days=period_days, limit=limit,
                )
            if tool_name == "get_revenue_comparison":
                return CloudSalesTrendService.revenue_comparison(
                    db, organization_id=organization_id, branch_id=branch_id,
                    period_days=period_days, limit=10,
                )
            if tool_name == "get_reconciliation":
                return CloudReconciliationService.reconcile(
                    db, organization_id=organization_id, branch_id=branch_id,
                    limit=limit,
                )
            if tool_name == "get_customer_analytics":
                return CustomerAnalyticsService.summary(
                    db, organization_id=organization_id, branch_id=branch_id,
                    period_days=period_days,
                )
            return {"error": f"Unknown tool: {tool_name}"}

        return _dispatch

    @staticmethod
    def _reporting_window(message: str, period_days: int) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        today_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)
        if any(keyword in message for keyword in ["today", "this day"]):
            return {
                "label": "today",
                "start_at": today_start,
                "end_at": now,
                "period_days": 1,
            }
        if "yesterday" in message:
            yesterday = today_start - timedelta(days=1)
            return {
                "label": "yesterday",
                "start_at": yesterday,
                "end_at": today_start,
                "period_days": 1,
            }
        return {
            "label": f"the last {period_days} day(s)",
            "start_at": AIManagerService._window_start(period_days),
            "end_at": now,
            "period_days": period_days,
        }

    @staticmethod
    def _sales_summary(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        start_at: datetime,
        end_at: datetime,
    ) -> Dict[str, Any]:
        sale_time = func.coalesce(CloudSaleFact.occurred_at, CloudSaleFact.created_at)
        query = db.query(
            func.count(CloudSaleFact.id).label("sales_count"),
            func.coalesce(func.sum(CloudSaleFact.total_amount), 0).label("total_revenue"),
            func.coalesce(func.sum(CloudSaleFact.item_count), 0).label("total_items"),
        ).filter(
            CloudSaleFact.organization_id == organization_id,
            sale_time >= start_at,
            sale_time < end_at,
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
        start_at: datetime,
        end_at: datetime,
    ) -> List[Dict[str, Any]]:
        sale_time = func.coalesce(CloudSaleFact.occurred_at, CloudSaleFact.created_at)
        query = db.query(
            CloudSaleFact.branch_id,
            func.count(CloudSaleFact.id).label("sales_count"),
            func.coalesce(func.sum(CloudSaleFact.total_amount), 0).label("total_revenue"),
            func.coalesce(func.sum(CloudSaleFact.item_count), 0).label("total_items"),
        ).filter(
            CloudSaleFact.organization_id == organization_id,
            sale_time >= start_at,
            sale_time < end_at,
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
        start_at: datetime,
        end_at: datetime,
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
            movement_time >= start_at,
            movement_time < end_at,
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
    def _product_sales(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        start_at: datetime,
        end_at: datetime,
        limit: int,
    ) -> List[Dict[str, Any]]:
        movement_time = func.coalesce(
            CloudInventoryMovementFact.occurred_at,
            CloudInventoryMovementFact.created_at,
        )
        query = (
            db.query(
                CloudInventoryMovementFact.branch_id,
                CloudInventoryMovementFact.local_product_id,
                CloudProductSnapshot.name.label("product_name"),
                CloudProductSnapshot.sku.label("sku"),
                func.coalesce(func.sum(-CloudInventoryMovementFact.quantity_delta), 0).label("units_sold"),
            )
            .outerjoin(
                CloudProductSnapshot,
                (CloudProductSnapshot.organization_id == CloudInventoryMovementFact.organization_id)
                & (CloudProductSnapshot.branch_id == CloudInventoryMovementFact.branch_id)
                & (CloudProductSnapshot.local_product_id == CloudInventoryMovementFact.local_product_id),
            )
            .filter(
                CloudInventoryMovementFact.organization_id == organization_id,
                CloudInventoryMovementFact.event_type == "sale_created",
                CloudInventoryMovementFact.quantity_delta < 0,
                CloudInventoryMovementFact.local_product_id.is_not(None),
                movement_time >= start_at,
                movement_time < end_at,
            )
        )
        if branch_id is not None:
            query = query.filter(CloudInventoryMovementFact.branch_id == branch_id)

        rows = (
            query.group_by(
                CloudInventoryMovementFact.branch_id,
                CloudInventoryMovementFact.local_product_id,
                CloudProductSnapshot.name,
                CloudProductSnapshot.sku,
            )
            .order_by(func.sum(-CloudInventoryMovementFact.quantity_delta).desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "branch_id": row.branch_id,
                "product_id": row.local_product_id,
                "product_name": row.product_name or f"Product {row.local_product_id}",
                "sku": row.sku,
                "units_sold": int(row.units_sold or 0),
            }
            for row in rows
        ]

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
        window_label: str,
        product_sales: List[Dict[str, Any]],
        branch_id: Optional[int],
        customer_analytics: Optional[Dict[str, Any]] = None,
    ) -> str:
        scope = f"branch {branch_id}" if branch_id is not None else "all permitted branches"
        top_branch = max(branch_sales, key=lambda row: row["total_revenue"], default=None)

        if (
            any(keyword in message for keyword in ["drug", "drugs", "product", "products", "item", "items"])
            and any(keyword in message for keyword in ["sell", "sold", "sale", "sales"])
        ):
            if not product_sales:
                return f"For {scope}, no products were sold {window_label} based on projected sale movement facts."
            product_text = "; ".join(
                f"{item['product_name']} ({item['units_sold']} unit(s))"
                for item in product_sales[:5]
            )
            total_units = sum(item["units_sold"] for item in product_sales)
            return (
                f"For {scope}, products sold {window_label} total {total_units} unit(s). "
                f"Top sold products: {product_text}."
            )

        if any(keyword in message for keyword in ["sale", "sales", "revenue", "income", "total"]):
            return (
                f"For {scope}, projected sales for {window_label} total "
                f"GHS {sales_summary['total_revenue']:.2f} from {sales_summary['sales_count']} sale(s) and "
                f"{sales_summary['total_items']} item(s)."
            )

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
                f"For {scope}, the top stock velocity priorities over {window_label} are: "
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
                return f"For {scope}, no branch sales have been projected for {window_label}."
            branch_label = top_branch.get("branch_name") or f"Branch {top_branch['branch_id']}"
            return (
                f"For {window_label}, {branch_label} is the strongest projected branch by revenue "
                f"with GHS {top_branch['total_revenue']:.2f} from {top_branch['sales_count']} sale(s) and "
                f"{top_branch['total_items']} item(s)."
            )

        if any(keyword in message for keyword in ["stock", "inventory", "movement"]):
            return (
                f"For {scope} over {window_label}, inventory movement shows "
                f"{inventory_summary['movement_count']} movement row(s), "
                f"+{inventory_summary['total_positive_quantity']} received/positive quantity, "
                f"{inventory_summary['total_negative_quantity']} negative quantity, and "
                f"{inventory_summary['net_quantity_delta']} net quantity movement."
            )

        if any(keyword in message for keyword in [
            "customer", "customers", "retention", "churn", "churned",
            "at risk", "at-risk", "repeat", "follow up", "follow-up", "followup", "consent",
        ]):
            ca = customer_analytics or {}
            if ca.get("error"):
                return (
                    "Customer analytics are not available in this deployment mode — "
                    "customers are only registered in online_pos mode."
                )
            total = ca.get("total_customers", 0)
            new   = ca.get("new_customers_in_period", 0)
            repeat_rate = ca.get("repeat_rate_pct", 0.0)
            at_risk = ca.get("at_risk_customers", 0)
            churned = ca.get("churned_customers", 0)
            top = (ca.get("top_customers") or [{}])[0]
            top_text = (
                f" Top customer by spend: {top.get('full_name', 'N/A')} "
                f"(GHS {top.get('total_spend', 0):.2f}, {top.get('purchase_count', 0)} purchase(s))."
            ) if top.get("full_name") else ""
            consent = ca.get("consent_stats", {})
            fu = ca.get("follow_up_stats", {})
            return (
                f"For {scope} over {window_label}: {total} registered customer(s), "
                f"{new} new this period, {repeat_rate:.1f}% repeat-purchase rate, "
                f"{at_risk} at-risk (no purchase in 30–89 days), {churned} churned (90+ days).{top_text} "
                f"SMS consent granted: {consent.get('sms_granted', 0)} "
                f"({consent.get('sms_rate_pct', 0):.1f}%). "
                f"Follow-ups: {fu.get('sent', 0)} sent, {fu.get('pending', 0)} pending, {fu.get('failed', 0)} failed."
            )

        return (
            f"For {scope} over {window_label}, projected sales total "
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
