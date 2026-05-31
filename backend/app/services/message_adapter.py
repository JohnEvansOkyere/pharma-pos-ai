"""
SMS / WhatsApp delivery adapter.

This module defines the interface and a stub implementation for sending
customer messages (receipts and health follow-ups).

Architecture
────────────
``MessageAdapter`` is the abstract base. Concrete implementations plug in a
real SMS or WhatsApp provider without touching any business logic.

Current implementations:
  - ``StubAdapter``  — logs messages, always returns success. Default until a
                       provider is configured.

To add a real provider (e.g. Africa's Talking, Twilio, Hubtel):
  1. Create a new class in this file that extends ``MessageAdapter``.
  2. Add the provider name to ``PROVIDER`` in the environment:
       SMS_PROVIDER=africas_talking
  3. Add the required credentials as environment variables.
  4. Update ``get_adapter()`` to instantiate the correct class.

Configuration (all optional — StubAdapter is used if not set)
─────────────────────────────────────────────────────────────
  SMS_PROVIDER=stub               # stub | africas_talking | twilio | hubtel
  SMS_SENDER_ID=PharmaPOS         # Sender name shown on handset
  SMS_API_KEY=<key>               # Provider API key
  SMS_USERNAME=<username>         # Provider username (Africa's Talking)
  SMS_FROM_NUMBER=<E.164>         # Twilio / Hubtel sender number

Compliance notes (Ghana)
────────────────────────
  - Customer consent (sms_consent / whatsapp_consent) must be GRANTED before
    sending any marketing or follow-up message.
  - The caller (follow-up scheduler, receipt dispatcher) is responsible for
    checking consent before calling send().
  - Opt-out replies ("STOP", "UNSUBSCRIBE") should update the customer record
    via a webhook — not yet implemented; requires provider webhook integration.
"""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DeliveryResult:
    """Result of a single message send attempt."""
    success: bool
    provider_message_id: str | None = None
    error: str | None = None


class MessageAdapter(ABC):
    """Abstract base for SMS/WhatsApp delivery providers."""

    @abstractmethod
    def send(self, *, to: str, message: str, channel: str = "sms") -> DeliveryResult:
        """Send a message.

        Args:
            to: Recipient phone number in E.164 format or local format.
            message: Plain-text message body (max 160 chars for SMS).
            channel: ``"sms"`` or ``"whatsapp"``.

        Returns:
            DeliveryResult with success flag and optional provider reference.
        """
        ...

    def send_receipt(self, *, to: str, invoice_number: str, items_summary: str,
                     total: str, pharmacy_name: str, channel: str = "sms") -> DeliveryResult:
        """Compose and send a digital receipt.

        Default implementation builds the message text and delegates to send().
        Override if the provider supports rich templates.
        """
        msg = (
            f"Receipt {invoice_number}\n"
            f"{pharmacy_name}\n"
            f"{items_summary}\n"
            f"Total: {total}\n"
            f"Thank you for your purchase."
        )
        # Truncate to 160 chars for SMS single-message delivery
        if channel == "sms" and len(msg) > 160:
            msg = msg[:157] + "..."
        return self.send(to=to, message=msg, channel=channel)

    def send_follow_up(self, *, to: str, customer_name: str, pharmacy_name: str,
                       days_since_purchase: int, channel: str = "sms") -> DeliveryResult:
        """Compose and send a health follow-up message.

        Override with a richer template or localised text as needed.
        """
        msg = (
            f"Hello {customer_name}, this is {pharmacy_name}. "
            f"It has been {days_since_purchase} day(s) since your last visit. "
            f"We hope you are feeling better. "
            f"Please contact us if you need any assistance. Reply STOP to opt out."
        )
        if channel == "sms" and len(msg) > 160:
            msg = msg[:157] + "..."
        return self.send(to=to, message=msg, channel=channel)


class StubAdapter(MessageAdapter):
    """Development / staging stub — logs messages, never actually sends.

    Use this until a real provider is configured. Safe to run in production
    during the transition period — messages will appear in the application
    log and the follow-up record will be marked as ``sent`` so the scheduler
    does not retry indefinitely.
    """

    def send(self, *, to: str, message: str, channel: str = "sms") -> DeliveryResult:
        logger.info(
            "[SMS STUB] channel=%s to=%s message=%r",
            channel, to, message[:80] + ("…" if len(message) > 80 else ""),
        )
        # Return a fake provider ID so the follow-up record has something to store
        return DeliveryResult(success=True, provider_message_id=f"STUB-{channel}-{to}")


def get_adapter() -> MessageAdapter:
    """Return the configured message adapter.

    Reads ``SMS_PROVIDER`` from settings (overridable via .env).
    Falls back to StubAdapter if the provider is unknown or misconfigured.
    """
    from app.core.config import settings as _settings  # late import to avoid circular

    provider = (_settings.SMS_PROVIDER or os.getenv("SMS_PROVIDER", "stub")).strip().lower()

    if provider == "stub" or not provider:
        return StubAdapter()

    # ── Africa's Talking ──────────────────────────────────────────────────────
    if provider == "africas_talking":
        try:
            import africastalking  # type: ignore
            api_key  = _settings.SMS_API_KEY or os.environ["SMS_API_KEY"]
            username = _settings.SMS_USERNAME or os.environ["SMS_USERNAME"]
            africastalking.initialize(username=username, api_key=api_key)
            from app.services._africas_talking_adapter import AfricasTalkingAdapter
            return AfricasTalkingAdapter()
        except ImportError:
            logger.error(
                "africastalking package not installed. "
                "Run: pip install africastalking   Falling back to StubAdapter."
            )
            return StubAdapter()
        except KeyError as exc:
            logger.error(
                "Africa's Talking env var missing: %s. Falling back to StubAdapter.", exc
            )
            return StubAdapter()

    # ── Hubtel (Ghana) ────────────────────────────────────────────────────────
    if provider == "hubtel":
        try:
            from app.services._hubtel_adapter import HubtelAdapter  # type: ignore
            return HubtelAdapter(
                client_id=_settings.SMS_CLIENT_ID or os.environ["SMS_CLIENT_ID"],
                client_secret=_settings.SMS_CLIENT_SECRET or os.environ["SMS_CLIENT_SECRET"],
                from_number=_settings.SMS_FROM_NUMBER or os.environ["SMS_FROM_NUMBER"],
                sender_id=_settings.SMS_SENDER_ID,
            )
        except (ImportError, KeyError) as exc:
            logger.error("Hubtel adapter error: %s. Falling back to StubAdapter.", exc)
            return StubAdapter()

    logger.warning(
        "Unknown SMS_PROVIDER=%r — falling back to StubAdapter.", provider
    )
    return StubAdapter()
