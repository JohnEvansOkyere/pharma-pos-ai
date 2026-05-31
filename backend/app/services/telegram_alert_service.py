"""
Proactive anomaly detection and Telegram push alerts for the CEO.
Handles: alert deduplication (4h cooldown), daily briefing dispatch,
and routing incoming CEO messages into the AI manager.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai_report import AIWeeklyReportDeliverySetting, TelegramAlertLog
from app.services.ai_briefing_service import AIBriefingService
from app.services.telegram_service import TelegramService

logger = logging.getLogger(__name__)


class TelegramAlertService:
    """Detect business anomalies and push Telegram alerts with deduplication."""

    @staticmethod
    def push_alerts_all_orgs(db: Session) -> int:
        """Run anomaly detection for every org with Telegram configured. Returns alert count."""
        if not TelegramService.is_configured():
            return 0

        settings_rows = (
            db.query(AIWeeklyReportDeliverySetting)
            .filter(
                AIWeeklyReportDeliverySetting.telegram_enabled.is_(True),
                AIWeeklyReportDeliverySetting.is_active.is_(True),
            )
            .all()
        )

        alert_count = 0
        seen_org_ids: set = set()
        for setting in settings_rows:
            org_id = setting.organization_id
            if org_id in seen_org_ids:
                continue
            seen_org_ids.add(org_id)
            chat_ids = [c for c in (setting.telegram_chat_ids or []) if c]
            if not chat_ids:
                continue
            try:
                sent = TelegramAlertService._push_org_alerts(db, org_id=org_id, chat_ids=chat_ids)
                alert_count += sent
            except Exception:
                logger.exception("Error pushing alerts for org %s", org_id)

        return alert_count

    @staticmethod
    def _push_org_alerts(db: Session, *, org_id: int, chat_ids: List[str]) -> int:
        cooldown = timedelta(hours=settings.TELEGRAM_ALERT_COOLDOWN_HOURS)
        now = datetime.now(timezone.utc)

        briefing = AIBriefingService.briefing(
            db,
            organization_id=org_id,
            branch_id=None,
            period_days=7,
            max_findings=20,
        )
        findings: List[Dict[str, Any]] = briefing.get("findings", [])

        sent = 0
        for finding in findings:
            if finding.get("severity") not in ("critical", "high"):
                continue

            alert_key = f"{finding['type']}:{finding.get('branch_id', 0)}"
            log_row = (
                db.query(TelegramAlertLog)
                .filter(
                    TelegramAlertLog.organization_id == org_id,
                    TelegramAlertLog.alert_key == alert_key,
                )
                .first()
            )

            if log_row and (now - log_row.last_sent_at.replace(tzinfo=timezone.utc)) < cooldown:
                continue

            text = TelegramService.format_alert(
                severity=finding["severity"],
                title=finding["title"],
                summary=finding["summary"],
                action_hint=finding.get("action_hint", ""),
            )

            for chat_id in chat_ids:
                try:
                    TelegramService.send_message(chat_id, text)
                    sent += 1
                except Exception:
                    logger.exception("Failed to send Telegram alert to chat %s", chat_id)

            if log_row:
                log_row.last_sent_at = now
            else:
                db.add(TelegramAlertLog(
                    organization_id=org_id,
                    alert_key=alert_key,
                    last_sent_at=now,
                ))
            db.commit()

        return sent

    @staticmethod
    def send_daily_briefing_all_orgs(db: Session) -> int:
        """Send daily morning briefing to all orgs with Telegram configured."""
        if not TelegramService.is_configured():
            return 0

        settings_rows = (
            db.query(AIWeeklyReportDeliverySetting)
            .filter(
                AIWeeklyReportDeliverySetting.telegram_enabled.is_(True),
                AIWeeklyReportDeliverySetting.is_active.is_(True),
            )
            .all()
        )

        sent_count = 0
        seen_org_ids: set = set()
        for setting in settings_rows:
            org_id = setting.organization_id
            if org_id in seen_org_ids:
                continue
            seen_org_ids.add(org_id)
            chat_ids = [c for c in (setting.telegram_chat_ids or []) if c]
            if not chat_ids:
                continue

            try:
                briefing = AIBriefingService.briefing(
                    db,
                    organization_id=org_id,
                    branch_id=None,
                    period_days=settings.AI_DAILY_BRIEFING_PERIOD_DAYS,
                    max_findings=8,
                )
                now = datetime.now(timezone.utc)
                date_label = now.strftime("%A, %d %b %Y")
                text = TelegramService.format_briefing(
                    briefing.get("findings", []),
                    date_label=date_label,
                    scope_label="All branches",
                )

                # Append customer retention summary when online_pos mode is active
                from app.core.config import settings as _s
                from app.core.app_mode import is_online_pos_mode
                if is_online_pos_mode(_s.APP_MODE):
                    try:
                        from app.services.customer_analytics_service import CustomerAnalyticsService
                        ca = CustomerAnalyticsService.summary(
                            db, organization_id=org_id, branch_id=None,
                            period_days=settings.AI_DAILY_BRIEFING_PERIOD_DAYS,
                        )
                        if ca.get("total_customers", 0) > 0:
                            fu = ca.get("follow_up_stats", {})
                            text += (
                                f"\n\n\U0001f465 *Customer Retention*\n"
                                f"Total: {ca['total_customers']} • "
                                f"New ({settings.AI_DAILY_BRIEFING_PERIOD_DAYS}d): {ca['new_customers_in_period']} • "
                                f"Repeat rate: {ca['repeat_rate_pct']:.1f}%\n"
                                f"At-risk: {ca['at_risk_customers']} • Churned: {ca['churned_customers']}\n"
                                f"Follow-ups — Sent: {fu.get('sent', 0)} • Pending: {fu.get('pending', 0)} • Failed: {fu.get('failed', 0)}"
                            )
                    except Exception:
                        logger.exception("Error adding customer analytics to daily briefing for org %s", org_id)

                for chat_id in chat_ids:
                    try:
                        TelegramService.send_message(chat_id, text)
                        sent_count += 1
                    except Exception:
                        logger.exception("Failed to send daily briefing to chat %s", chat_id)
            except Exception:
                logger.exception("Error building daily briefing for org %s", org_id)

        return sent_count

    @staticmethod
    def route_ceo_message(db: Session, *, chat_id: str, text: str) -> Optional[str]:
        """
        Route a CEO's Telegram message into the AI manager and return the answer.
        Looks up which org owns this chat_id from delivery settings.
        """
        from app.services.ai_manager_service import AIManagerService

        all_settings = (
            db.query(AIWeeklyReportDeliverySetting)
            .filter(AIWeeklyReportDeliverySetting.is_active.is_(True))
            .all()
        )

        org_id: Optional[int] = None
        for s in all_settings:
            if chat_id in (s.telegram_chat_ids or []):
                org_id = s.organization_id
                break

        if org_id is None:
            return (
                "Your Telegram account is not linked to a pharmacy organisation. "
                "Contact your administrator to add your chat ID to the delivery settings."
            )

        try:
            result = AIManagerService.answer(
                db,
                organization_id=org_id,
                branch_id=None,
                message=text,
                period_days=7,
            )
            return result.get("answer") or "I could not retrieve that information right now."
        except Exception:
            logger.exception("Error answering CEO Telegram message for org %s", org_id)
            return "An error occurred while processing your question. Please try again."
