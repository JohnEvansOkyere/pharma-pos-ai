"""
Delivery channels for saved AI weekly manager reports.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import smtplib
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai_report import AIWeeklyManagerReport, AIWeeklyReportDelivery, AIWeeklyReportDeliverySetting
from app.services.audit_service import AuditService


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
        performed_by_user_id: Optional[int] = None,
    ) -> List[AIWeeklyReportDelivery]:
        requested_channels = channels or [AIReportDeliveryService.EMAIL, AIReportDeliveryService.TELEGRAM]
        delivery_setting = AIReportDeliveryService.get_effective_setting(db, report)
        deliveries: List[AIWeeklyReportDelivery] = []

        if AIReportDeliveryService.EMAIL in requested_channels:
            deliveries.extend(
                AIReportDeliveryService._deliver_email(
                    db,
                    report,
                    delivery_setting,
                    performed_by_user_id=performed_by_user_id,
                )
            )
        if AIReportDeliveryService.TELEGRAM in requested_channels:
            deliveries.extend(
                AIReportDeliveryService._deliver_telegram(
                    db,
                    report,
                    delivery_setting,
                    performed_by_user_id=performed_by_user_id,
                )
            )

        return deliveries

    @staticmethod
    def get_effective_setting(db: Session, report: AIWeeklyManagerReport) -> Optional[AIWeeklyReportDeliverySetting]:
        if report.branch_id is not None:
            branch_setting = (
                db.query(AIWeeklyReportDeliverySetting)
                .filter(
                    AIWeeklyReportDeliverySetting.organization_id == report.organization_id,
                    AIWeeklyReportDeliverySetting.report_scope_key == f"branch:{report.branch_id}",
                    AIWeeklyReportDeliverySetting.is_active.is_(True),
                )
                .first()
            )
            if branch_setting is not None:
                return branch_setting

        return (
            db.query(AIWeeklyReportDeliverySetting)
            .filter(
                AIWeeklyReportDeliverySetting.organization_id == report.organization_id,
                AIWeeklyReportDeliverySetting.report_scope_key == "organization",
                AIWeeklyReportDeliverySetting.is_active.is_(True),
            )
            .first()
        )

    @staticmethod
    def _deliver_email(
        db: Session,
        report: AIWeeklyManagerReport,
        delivery_setting: Optional[AIWeeklyReportDeliverySetting],
        *,
        performed_by_user_id: Optional[int],
    ) -> List[AIWeeklyReportDelivery]:
        if delivery_setting is None:
            return [
                AIReportDeliveryService._record(
                    db,
                    report,
                    channel=AIReportDeliveryService.EMAIL,
                    recipient="tenant-email-recipients",
                    status=AIReportDeliveryService.SKIPPED,
                    error_message="No active tenant delivery setting exists for this report scope.",
                    performed_by_user_id=performed_by_user_id,
                )
            ]

        recipients = [
            recipient.strip()
            for recipient in (delivery_setting.email_recipients or [])
            if isinstance(recipient, str) and recipient.strip()
        ]
        if not delivery_setting.email_enabled:
            return [
                AIReportDeliveryService._record(
                    db,
                    report,
                    channel=AIReportDeliveryService.EMAIL,
                    recipient="tenant-email-recipients",
                    status=AIReportDeliveryService.SKIPPED,
                    error_message="Email weekly report delivery is disabled for this tenant scope.",
                    performed_by_user_id=performed_by_user_id,
                )
            ]
        if not recipients:
            return [
                AIReportDeliveryService._record(
                    db,
                    report,
                    channel=AIReportDeliveryService.EMAIL,
                    recipient="tenant-email-recipients",
                    status=AIReportDeliveryService.SKIPPED,
                    error_message="No tenant email recipients configured for this report scope.",
                    performed_by_user_id=performed_by_user_id,
                )
            ]
        if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
            return [
                AIReportDeliveryService._record(
                    db,
                    report,
                    channel=AIReportDeliveryService.EMAIL,
                    recipient="tenant-email-recipients",
                    status=AIReportDeliveryService.FAILED,
                    error_message="SMTP_HOST and SMTP_FROM_EMAIL are required for email delivery.",
                    performed_by_user_id=performed_by_user_id,
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
                        performed_by_user_id=performed_by_user_id,
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
                        retryable=True,
                        performed_by_user_id=performed_by_user_id,
                    )
                )
        return deliveries

    @staticmethod
    def _deliver_telegram(
        db: Session,
        report: AIWeeklyManagerReport,
        delivery_setting: Optional[AIWeeklyReportDeliverySetting],
        *,
        performed_by_user_id: Optional[int],
    ) -> List[AIWeeklyReportDelivery]:
        if delivery_setting is None:
            return [
                AIReportDeliveryService._record(
                    db,
                    report,
                    channel=AIReportDeliveryService.TELEGRAM,
                    recipient="tenant-telegram-chats",
                    status=AIReportDeliveryService.SKIPPED,
                    error_message="No active tenant delivery setting exists for this report scope.",
                    performed_by_user_id=performed_by_user_id,
                )
            ]

        chat_ids = [
            chat_id.strip()
            for chat_id in (delivery_setting.telegram_chat_ids or [])
            if isinstance(chat_id, str) and chat_id.strip()
        ]
        if not delivery_setting.telegram_enabled:
            return [
                AIReportDeliveryService._record(
                    db,
                    report,
                    channel=AIReportDeliveryService.TELEGRAM,
                    recipient="tenant-telegram-chats",
                    status=AIReportDeliveryService.SKIPPED,
                    error_message="Telegram weekly report delivery is disabled for this tenant scope.",
                    performed_by_user_id=performed_by_user_id,
                )
            ]
        if not chat_ids:
            return [
                AIReportDeliveryService._record(
                    db,
                    report,
                    channel=AIReportDeliveryService.TELEGRAM,
                    recipient="tenant-telegram-chats",
                    status=AIReportDeliveryService.SKIPPED,
                    error_message="No tenant Telegram chat IDs configured for this report scope.",
                    performed_by_user_id=performed_by_user_id,
                )
            ]
        if not settings.TELEGRAM_BOT_TOKEN:
            return [
                AIReportDeliveryService._record(
                    db,
                    report,
                    channel=AIReportDeliveryService.TELEGRAM,
                    recipient="tenant-telegram-chats",
                    status=AIReportDeliveryService.FAILED,
                    error_message="TELEGRAM_BOT_TOKEN is required for Telegram delivery.",
                    performed_by_user_id=performed_by_user_id,
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
                        performed_by_user_id=performed_by_user_id,
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
                        retryable=True,
                        performed_by_user_id=performed_by_user_id,
                    )
                )
        return deliveries

    @staticmethod
    def retry_due(
        db: Session,
        *,
        limit: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> List[AIWeeklyReportDelivery]:
        """Retry failed delivery records that are explicitly marked retryable and due."""
        effective_now = now or datetime.now(timezone.utc)
        batch_size = limit or settings.AI_WEEKLY_REPORT_DELIVERY_RETRY_BATCH_SIZE
        deliveries = (
            db.query(AIWeeklyReportDelivery)
            .filter(
                AIWeeklyReportDelivery.status == AIReportDeliveryService.FAILED,
                AIWeeklyReportDelivery.retryable.is_(True),
                AIWeeklyReportDelivery.next_retry_at.isnot(None),
                AIWeeklyReportDelivery.next_retry_at <= effective_now,
                AIWeeklyReportDelivery.attempt_count < AIWeeklyReportDelivery.max_attempts,
            )
            .order_by(AIWeeklyReportDelivery.next_retry_at.asc(), AIWeeklyReportDelivery.id.asc())
            .limit(batch_size)
            .all()
        )
        return [
            AIReportDeliveryService.retry_delivery(db, delivery, now=effective_now)
            for delivery in deliveries
        ]

    @staticmethod
    def retry_delivery(
        db: Session,
        delivery: AIWeeklyReportDelivery,
        *,
        now: Optional[datetime] = None,
    ) -> AIWeeklyReportDelivery:
        """Retry one failed delivery record in place."""
        effective_now = now or datetime.now(timezone.utc)
        report = db.query(AIWeeklyManagerReport).filter(AIWeeklyManagerReport.id == delivery.report_id).first()
        delivery.last_attempted_at = effective_now

        if report is None:
            delivery.status = AIReportDeliveryService.FAILED
            delivery.retryable = False
            delivery.next_retry_at = None
            delivery.error_message = "Weekly manager report no longer exists."
            db.commit()
            db.refresh(delivery)
            return delivery

        if delivery.attempt_count >= delivery.max_attempts:
            delivery.retryable = False
            delivery.next_retry_at = None
            db.commit()
            db.refresh(delivery)
            return delivery

        delivery.attempt_count += 1
        try:
            if delivery.channel == AIReportDeliveryService.EMAIL:
                AIReportDeliveryService._send_email(recipient=delivery.recipient, report=report)
                provider_response = None
            elif delivery.channel == AIReportDeliveryService.TELEGRAM:
                provider_response = AIReportDeliveryService._send_telegram(chat_id=delivery.recipient, report=report)
            else:
                delivery.status = AIReportDeliveryService.FAILED
                delivery.retryable = False
                delivery.next_retry_at = None
                delivery.error_message = f"Unsupported delivery channel: {delivery.channel}"
                AIReportDeliveryService._audit_retry(db, report, delivery)
                db.commit()
                db.refresh(delivery)
                return delivery

            delivery.status = AIReportDeliveryService.SENT
            delivery.retryable = False
            delivery.next_retry_at = None
            delivery.error_message = None
            delivery.provider_response = provider_response
            delivery.sent_at = effective_now
        except Exception as exc:
            delivery.status = AIReportDeliveryService.FAILED
            delivery.error_message = str(exc)
            if delivery.attempt_count >= delivery.max_attempts:
                delivery.retryable = False
                delivery.next_retry_at = None
            else:
                delivery.retryable = True
                delivery.next_retry_at = AIReportDeliveryService._next_retry_at(effective_now, delivery.attempt_count)

        AIReportDeliveryService._audit_retry(db, report, delivery)
        db.commit()
        db.refresh(delivery)
        return delivery

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
        retryable: bool = False,
        performed_by_user_id: Optional[int] = None,
    ) -> AIWeeklyReportDelivery:
        now = datetime.now(timezone.utc)
        max_attempts = AIReportDeliveryService._max_attempts()
        should_retry = status == AIReportDeliveryService.FAILED and retryable and max_attempts > 1
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
            retryable=should_retry,
            last_attempted_at=now,
            next_retry_at=AIReportDeliveryService._next_retry_at(now, 1) if should_retry else None,
            max_attempts=max_attempts,
            sent_at=sent_at,
        )
        db.add(delivery)
        db.flush()
        AuditService.log(
            db,
            action="create_ai_weekly_report_delivery",
            user_id=performed_by_user_id,
            organization_id=report.organization_id,
            branch_id=report.branch_id,
            entity_type="ai_weekly_report_delivery",
            entity_id=delivery.id,
            description=f"Recorded {channel} weekly AI report delivery as {status}",
            extra_data={
                "report_id": report.id,
                "channel": channel,
                "recipient": recipient,
                "status": status,
                "retryable": should_retry,
                "attempt_count": delivery.attempt_count,
                "max_attempts": delivery.max_attempts,
                "error_message": error_message,
            },
        )
        db.commit()
        db.refresh(delivery)
        return delivery

    @staticmethod
    def _audit_retry(
        db: Session,
        report: AIWeeklyManagerReport,
        delivery: AIWeeklyReportDelivery,
    ) -> None:
        AuditService.log(
            db,
            action="retry_ai_weekly_report_delivery",
            user_id=None,
            organization_id=report.organization_id,
            branch_id=report.branch_id,
            entity_type="ai_weekly_report_delivery",
            entity_id=delivery.id,
            description=f"Retried {delivery.channel} weekly AI report delivery as {delivery.status}",
            extra_data={
                "report_id": report.id,
                "channel": delivery.channel,
                "recipient": delivery.recipient,
                "status": delivery.status,
                "retryable": delivery.retryable,
                "attempt_count": delivery.attempt_count,
                "max_attempts": delivery.max_attempts,
                "next_retry_at": delivery.next_retry_at.isoformat() if delivery.next_retry_at else None,
                "error_message": delivery.error_message,
            },
        )

    @staticmethod
    def _max_attempts() -> int:
        return max(1, settings.AI_WEEKLY_REPORT_DELIVERY_MAX_ATTEMPTS)

    @staticmethod
    def _next_retry_at(now: datetime, attempt_count: int) -> datetime:
        base_delay = max(1, settings.AI_WEEKLY_REPORT_DELIVERY_RETRY_BASE_DELAY_MINUTES)
        max_delay = max(base_delay, settings.AI_WEEKLY_REPORT_DELIVERY_RETRY_MAX_DELAY_MINUTES)
        delay_minutes = min(max_delay, base_delay * (2 ** max(0, attempt_count - 1)))
        return now + timedelta(minutes=delay_minutes)

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
