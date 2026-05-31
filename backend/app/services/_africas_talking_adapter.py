"""
Africa's Talking SMS adapter for PharmaPOS.

Provider: Africa's Talking (https://africastalking.com)
Coverage: Ghana (GH), Nigeria, Kenya, and 20+ African markets.
Package:  africastalking  (pip install africastalking)

Environment variables required
───────────────────────────────
  SMS_PROVIDER=africas_talking
  SMS_USERNAME=<your AT username>        # "sandbox" for testing
  SMS_API_KEY=<your AT API key>
  SMS_SENDER_ID=PharmaPOS                # alphanumeric sender ID (max 11 chars)
                                          # Must be pre-registered with AT for GH

WhatsApp (optional, future)
───────────────────────────
  Africa's Talking does not offer a native WhatsApp API yet (2025).
  Calls with channel="whatsapp" fall back to SMS unless an external
  WhatsApp Business API proxy is configured.

Usage
─────
  Set SMS_PROVIDER=africas_talking and the above env vars in your .env
  file or docker-compose environment block. get_adapter() will return
  this adapter automatically.

Sandbox mode
─────────────
  Set SMS_USERNAME=sandbox for development. The AT sandbox accepts any
  phone number and records messages in the AT dashboard without actually
  sending. Pair with SMS_API_KEY=<sandbox key from AT dashboard>.
"""
from __future__ import annotations

import logging
import os

from app.services.message_adapter import DeliveryResult, MessageAdapter

logger = logging.getLogger(__name__)

_SENDER_ID_MAX = 11  # Africa's Talking alphanumeric limit for GH


class AfricasTalkingAdapter(MessageAdapter):
    """Concrete SMS adapter backed by Africa's Talking.

    Assumes ``africastalking.initialize()`` has already been called by
    ``message_adapter.get_adapter()`` before this class is instantiated.
    """

    def __init__(self) -> None:
        import africastalking  # type: ignore
        self._sms = africastalking.SMS
        raw_sender = os.getenv("SMS_SENDER_ID", "PharmaPOS").strip()
        # Africa's Talking rejects sender IDs longer than 11 chars
        self._sender_id = raw_sender[:_SENDER_ID_MAX] if raw_sender else None

    def send(self, *, to: str, message: str, channel: str = "sms") -> DeliveryResult:
        """Send an SMS via Africa's Talking.

        WhatsApp is not natively supported — channel="whatsapp" falls back
        to SMS so the customer still receives the message.

        Args:
            to:      Recipient phone in local or E.164 format.
                     For Ghana, both ``0244XXXXXX`` and ``+233244XXXXXX`` work.
            message: Plain-text body (≤160 chars for single SMS unit).
            channel: ``"sms"`` or ``"whatsapp"`` (whatsapp falls back to sms).

        Returns:
            DeliveryResult with success=True and provider_message_id on success.
        """
        if channel == "whatsapp":
            logger.info(
                "[AT] WhatsApp not natively supported — sending SMS fallback to %s", to
            )

        # Normalise Ghana numbers to E.164 (+233XXXXXXXXX)
        normalized = _normalize_ghana_number(to)

        try:
            response = self._sms.send(
                message=message,
                recipients=[normalized],
                sender_id=self._sender_id,
            )
            # AT returns: {'SMSMessageData': {'Message': '...', 'Recipients': [...]}}
            recipients = response.get("SMSMessageData", {}).get("Recipients", [])
            if recipients:
                rec = recipients[0]
                status_code = rec.get("statusCode", 0)
                msg_id = rec.get("messageId", "")

                # AT statusCode 101 = "Sent", 102 = "Queued"
                if status_code in (101, 102):
                    logger.info("[AT] Sent to %s, messageId=%s", normalized, msg_id)
                    return DeliveryResult(success=True, provider_message_id=msg_id)
                else:
                    error_msg = rec.get("status", f"statusCode={status_code}")
                    logger.warning("[AT] Send failed for %s: %s", normalized, error_msg)
                    return DeliveryResult(success=False, error=error_msg)

            return DeliveryResult(success=False, error="No recipients in AT response")

        except Exception as exc:  # noqa: BLE001
            logger.exception("[AT] Exception sending to %s", normalized)
            return DeliveryResult(success=False, error=str(exc))


def _normalize_ghana_number(phone: str) -> str:
    """Best-effort normalisation to E.164 for Ghana numbers.

    Handles:
      0244123456     → +233244123456
      233244123456   → +233244123456
      +233244123456  → +233244123456 (pass-through)
      Other formats  → passed through unchanged (AT handles international)
    """
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+"):
        return phone
    if phone.startswith("00"):
        return "+" + phone[2:]
    if phone.startswith("233") and len(phone) == 12:
        return "+" + phone
    if phone.startswith("0") and len(phone) == 10:
        return "+233" + phone[1:]
    # Non-Ghanaian or already normalised — return as-is
    return phone
