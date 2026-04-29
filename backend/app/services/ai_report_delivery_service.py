"""
Delivery channels for saved AI weekly manager reports.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.message import EmailMessage
import smtplib
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai_report import AIWeeklyManagerReport, AIWeeklyReportDelivery


class AIReportDeliveryService:
    """Send saved manager reports through explicitly configured channels."""

    EMAIL = "email"
    TELEGRAM = "telegram"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"

    @staticmethod
    def deliver(
        db: Session,
        report: AIWeeklyManagerReport,
        *,
        channels: Optional[List[str]] = None,
    ) -> List[AIWeeklyReportDelivery]:
        requested_channels = channels or [AIReportDeliveryService.EMAIL, AIReportDeliveryService.TELEGRAM]
        deliveries: List[AIWeeklyReportDelivery] = []

        if AIReportDeliveryService.EMAIL in requested_channels:
            deliveries.extend(AIReportDeliveryService._deliver_email(db, report))
        if AIReportDeliveryService.TELEGRAM in requested_channels:
            deliveries.extend(AIReportDeliveryService._deliver_telegram(db, report))

        return deliveries

    @staticmethod
    def _deliver_email(db: Session, report: AIWeeklyManagerReport) -> List[AIWeeklyReportDelivery]:
        recipients = [recipient.strip() for recipient in settings.AI_WEEKLY_REPORT_EMAIL_RECIPIENTS if recipient.strip()]
        if not settings.AI_WEEKLY_REPORT_EMAIL_ENABLED:
            return [
                AIReportDeliveryService._record(
                    db,
                    report,
                    channel=AIReportDeliveryService.EMAIL,
                    recipient="configured-email-recipients",
                    status=AIReportDeliveryService.SKIPPED,
                    error_message="Email weekly report delivery is disabled.",
                )
            ]
        if not recipients:
            return [
                AIReportDeliveryService._record(
                    db,
                    report,
                    channel=AIReportDeliveryService.EMAIL,
                    recipient="configured-email-recipients",
                    status=AIReportDeliveryService.SKIPPED,
                    error_message="No weekly report email recipients configured.",
                )
            ]
        if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
            return [
                AIReportDeliveryService._record(
                    db,
                    report,
                    channel=AIReportDeliveryService.EMAIL,
                    recipient="configured-email-recipients",
                    status=AIReportDeliveryService.FAILED,
                    error_message="SMTP_HOST and SMTP_FROM_EMAIL are required for email delivery.",
                )
            ]

        deliveries: List[AIWeeklyReportDelivery] = []
        for recipient in recipients:
            try:
                AIReportDeliveryService._send_email(recipient=recipient, report=report)
                deliveries.append(
                    AIReportDeliveryService._record(
                        db,
                        report,
                        channel=AIReportDeliveryService.EMAIL,
                        recipient=recipient,
                        status=AIReportDeliveryService.SENT,
                        sent_at=datetime.now(timezone.utc),
                    )
                )
            except Exception as exc:
                deliveries.append(
                    AIReportDeliveryService._record(
                        db,
                        report,
                        channel=AIReportDeliveryService.EMAIL,
                        recipient=recipient,
                        status=AIReportDeliveryService.FAILED,
                        error_message=str(exc),
                    )
                )
        return deliveries

    @staticmethod
    def _deliver_telegram(db: Session, report: AIWeeklyManagerReport) -> List[AIWeeklyReportDelivery]:
        chat_ids = [chat_id.strip() for chat_id in settings.AI_WEEKLY_REPORT_TELEGRAM_CHAT_IDS if chat_id.strip()]
        if not settings.AI_WEEKLY_REPORT_TELEGRAM_ENABLED:
            return [
                AIReportDeliveryService._record(
                    db,
                    report,
                    channel=AIReportDeliveryService.TELEGRAM,
                    recipient="configured-telegram-chats",
                    status=AIReportDeliveryService.SKIPPED,
                    error_message="Telegram weekly report delivery is disabled.",
                )
            ]
        if not chat_ids:
            return [
                AIReportDeliveryService._record(
                    db,
                    report,
                    channel=AIReportDeliveryService.TELEGRAM,
                    recipient="configured-telegram-chats",
                    status=AIReportDeliveryService.SKIPPED,
                    error_message="No weekly report Telegram chat IDs configured.",
                )
            ]
        if not settings.TELEGRAM_BOT_TOKEN:
            return [
                AIReportDeliveryService._record(
                    db,
                    report,
                    channel=AIReportDeliveryService.TELEGRAM,
                    recipient="configured-telegram-chats",
                    status=AIReportDeliveryService.FAILED,
                    error_message="TELEGRAM_BOT_TOKEN is required for Telegram delivery.",
                )
            ]

        deliveries: List[AIWeeklyReportDelivery] = []
        for chat_id in chat_ids:
            try:
                response_payload = AIReportDeliveryService._send_telegram(chat_id=chat_id, report=report)
                deliveries.append(
                    AIReportDeliveryService._record(
                        db,
                        report,
                        channel=AIReportDeliveryService.TELEGRAM,
                        recipient=chat_id,
                        status=AIReportDeliveryService.SENT,
                        provider_response=response_payload,
                        sent_at=datetime.now(timezone.utc),
                    )
                )
            except Exception as exc:
                deliveries.append(
                    AIReportDeliveryService._record(
                        db,
                        report,
                        channel=AIReportDeliveryService.TELEGRAM,
                        recipient=chat_id,
                        status=AIReportDeliveryService.FAILED,
                        error_message=str(exc),
                    )
                )
        return deliveries

    @staticmethod
    def _send_email(*, recipient: str, report: AIWeeklyManagerReport) -> None:
        message = EmailMessage()
        message["Subject"] = report.title
        message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        message["To"] = recipient
        message.set_content(AIReportDeliveryService._email_body(report))

        if settings.SMTP_USE_SSL:
            with smtplib.SMTP_SSL(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=settings.AI_WEEKLY_REPORT_DELIVERY_TIMEOUT_SECONDS,
            ) as smtp:
                AIReportDeliveryService._authenticate_smtp(smtp)
                smtp.send_message(message)
            return

        with smtplib.SMTP(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=settings.AI_WEEKLY_REPORT_DELIVERY_TIMEOUT_SECONDS,
        ) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            AIReportDeliveryService._authenticate_smtp(smtp)
            smtp.send_message(message)

    @staticmethod
    def _authenticate_smtp(smtp: smtplib.SMTP) -> None:
        if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)

    @staticmethod
    def _send_telegram(*, chat_id: str, report: AIWeeklyManagerReport) -> Dict[str, Any]:
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": AIReportDeliveryService._telegram_body(report),
            "disable_web_page_preview": True,
        }
        with httpx.Client(timeout=settings.AI_WEEKLY_REPORT_DELIVERY_TIMEOUT_SECONDS) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _record(
        db: Session,
        report: AIWeeklyManagerReport,
        *,
        channel: str,
        recipient: str,
        status: str,
        error_message: Optional[str] = None,
        provider_response: Optional[Dict[str, Any]] = None,
        sent_at: Optional[datetime] = None,
    ) -> AIWeeklyReportDelivery:
        delivery = AIWeeklyReportDelivery(
            report_id=report.id,
            organization_id=report.organization_id,
            branch_id=report.branch_id,
            channel=channel,
            recipient=recipient,
            status=status,
            attempt_count=1,
            error_message=error_message,
            provider_response=provider_response,
            sent_at=sent_at,
        )
        db.add(delivery)
        db.commit()
        db.refresh(delivery)
        return delivery

    @staticmethod
    def _email_body(report: AIWeeklyManagerReport) -> str:
        return (
            f"{report.title}\n\n"
            f"{report.executive_summary}\n\n"
            f"{AIReportDeliveryService._action_plan_text(report)}\n\n"
            "Safety and data limits:\n"
            "- Read-only report. It does not mutate stock, sales, users, or sync records.\n"
            "- Uses approved cloud reporting projections only.\n"
            "- Does not provide clinical advice or controlled-drug dispensing approval.\n"
        )

    @staticmethod
    def _telegram_body(report: AIWeeklyManagerReport) -> str:
        body = (
            f"{report.title}\n\n"
            f"{report.executive_summary}\n\n"
            f"{AIReportDeliveryService._action_plan_text(report)}"
        )
        return body[:3900]

    @staticmethod
    def _action_plan_text(report: AIWeeklyManagerReport) -> str:
        action_plan = report.sections.get("coming_week_action_plan", {})
        risk_counts = action_plan.get("risk_counts", {})
        priorities = action_plan.get("priorities", [])
        priority_lines = "\n".join(f"- {priority}" for priority in priorities[:6]) or "- No priorities recorded."
        return (
            "Coming week risk summary:\n"
            f"- Out of stock: {risk_counts.get('out_of_stock_count', 0)}\n"
            f"- Low stock: {risk_counts.get('low_stock_count', 0)}\n"
            f"- Expired batches: {risk_counts.get('expired_batch_count', 0)}\n"
            f"- Near-expiry batches: {risk_counts.get('near_expiry_batch_count', 0)}\n"
            f"- Expiry value at risk: GHS {risk_counts.get('value_at_risk', 0):.2f}\n\n"
            "Manager priorities:\n"
            f"{priority_lines}"
        )
