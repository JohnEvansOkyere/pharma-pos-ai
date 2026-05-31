"""
Customer retention service.

Responsibilities:
  1. Create follow-up records when a sale is linked to a customer.
  2. Dispatch digital receipts immediately after a sale completes.
  3. Send scheduled health follow-up messages (called by scheduler).
  4. Mark follow-ups as sent / failed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.customer import ConsentStatus, Customer, CustomerFollowUp, FollowUpStatus
from app.models.sale import Sale
from app.services.message_adapter import get_adapter

logger = logging.getLogger(__name__)

# Default days after purchase before sending a follow-up
DEFAULT_FOLLOW_UP_DAYS = 3
MAX_FOLLOW_UP_ATTEMPTS = 3


def _can_send(customer: Customer, channel: str) -> bool:
    """Return True if the customer has granted consent for the given channel."""
    if channel == "sms":
        return customer.sms_consent == ConsentStatus.GRANTED
    if channel == "whatsapp":
        return customer.whatsapp_consent == ConsentStatus.GRANTED
    return False


def schedule_follow_up(
    db: Session,
    *,
    customer: Customer,
    sale: Sale,
    follow_up_days: int = DEFAULT_FOLLOW_UP_DAYS,
) -> Optional[CustomerFollowUp]:
    """Create a CustomerFollowUp record for a just-completed sale.

    If the customer has not granted consent on their preferred channel,
    the follow-up is created with status=SKIPPED so there is an audit trail.
    """
    channel = customer.preferred_channel or "sms"
    can_send = _can_send(customer, channel)
    status = FollowUpStatus.PENDING if can_send else FollowUpStatus.SKIPPED

    scheduled_at = datetime.now(timezone.utc) + timedelta(days=follow_up_days)

    follow_up = CustomerFollowUp(
        organization_id=customer.organization_id,
        branch_id=customer.branch_id,
        customer_id=customer.id,
        sale_id=sale.id,
        channel=channel,
        scheduled_at=scheduled_at,
        status=status,
    )
    db.add(follow_up)
    return follow_up


def dispatch_receipt(
    db: Session,
    *,
    customer: Customer,
    sale: Sale,
    pharmacy_name: str = "PharmaPOS",
) -> bool:
    """Send a digital receipt immediately after sale completion.

    Returns True if the message was dispatched (or stubbed), False if
    consent was not granted or if the send failed.
    """
    channel = customer.preferred_channel or "sms"
    if not _can_send(customer, channel):
        logger.info(
            "Receipt not sent for sale %s — customer %s has no %s consent",
            sale.invoice_number, customer.id, channel,
        )
        return False

    adapter = get_adapter()
    items_summary = _summarize_items(sale)

    try:
        result = adapter.send_receipt(
            to=customer.phone,
            invoice_number=sale.invoice_number,
            items_summary=items_summary,
            total=f"GH\u20b5 {sale.total_amount:.2f}",
            pharmacy_name=pharmacy_name,
            channel=channel,
        )
        if result.success:
            sale.receipt_sent = True
            logger.info(
                "Receipt sent for sale %s via %s (msg_id=%s)",
                sale.invoice_number, channel, result.provider_message_id,
            )
            return True
        else:
            logger.warning(
                "Receipt send failed for sale %s: %s", sale.invoice_number, result.error
            )
            return False
    except Exception as exc:
        logger.error("Receipt dispatch error for sale %s: %s", sale.invoice_number, exc)
        return False


def _summarize_items(sale: Sale) -> str:
    """Build a compact items summary string for a receipt message."""
    if not sale.items:
        return "(no items)"
    parts = []
    for item in sale.items[:4]:  # cap at 4 items to keep SMS short
        parts.append(f"{item.product_name} x{item.quantity}")
    if len(sale.items) > 4:
        parts.append(f"(+{len(sale.items) - 4} more)")
    return ", ".join(parts)


def process_pending_follow_ups(db: Session, *, pharmacy_name: str = "PharmaPOS") -> dict:
    """Send all due follow-up messages. Called by the scheduler every hour.

    Returns a dict with counts: { sent, skipped, failed, total_processed }.
    """
    now = datetime.now(timezone.utc)
    pending = (
        db.query(CustomerFollowUp)
        .filter(
            CustomerFollowUp.status == FollowUpStatus.PENDING,
            CustomerFollowUp.scheduled_at <= now,
        )
        .all()
    )

    sent = skipped = failed = 0
    adapter = get_adapter()

    for follow_up in pending:
        customer = db.get(Customer, follow_up.customer_id)
        if not customer or not customer.is_active:
            follow_up.status = FollowUpStatus.SKIPPED
            skipped += 1
            continue

        if not _can_send(customer, follow_up.channel):
            follow_up.status = FollowUpStatus.SKIPPED
            skipped += 1
            continue

        sale = db.get(Sale, follow_up.sale_id)
        days_since = (now - sale.created_at.replace(tzinfo=timezone.utc)).days if sale else 3

        try:
            result = adapter.send_follow_up(
                to=customer.phone,
                customer_name=customer.full_name.split()[0],  # first name only
                pharmacy_name=pharmacy_name,
                days_since_purchase=days_since,
                channel=follow_up.channel,
            )
            follow_up.attempts += 1
            follow_up.sent_at = now

            if result.success:
                follow_up.status = FollowUpStatus.SENT
                follow_up.provider_message_id = result.provider_message_id
                sent += 1
            else:
                follow_up.last_error = result.error
                if follow_up.attempts >= MAX_FOLLOW_UP_ATTEMPTS:
                    follow_up.status = FollowUpStatus.FAILED
                    failed += 1
                # else stays PENDING for next run
        except Exception as exc:
            follow_up.attempts += 1
            follow_up.last_error = str(exc)
            if follow_up.attempts >= MAX_FOLLOW_UP_ATTEMPTS:
                follow_up.status = FollowUpStatus.FAILED
                failed += 1
            logger.error("Follow-up %s dispatch error: %s", follow_up.id, exc)

    db.commit()
    logger.info(
        "Follow-up run: %d sent, %d skipped, %d failed (of %d pending)",
        sent, skipped, failed, len(pending),
    )
    return {"sent": sent, "skipped": skipped, "failed": failed, "total_processed": len(pending)}
