"""
Telegram Bot webhook endpoint.
Receives updates from Telegram, routes CEO messages to the AI manager,
and returns 200 immediately (Telegram requires a fast response).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.core.config import settings

router = APIRouter(prefix="/telegram", tags=["telegram"])
logger = logging.getLogger(__name__)


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str = Header(default=""),
):
    """
    Receive Telegram bot updates.
    Validates the webhook secret if TELEGRAM_WEBHOOK_SECRET is configured.
    Processes CEO messages in a background task so Telegram gets an immediate 200.
    """
    if settings.TELEGRAM_WEBHOOK_SECRET:
        if x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid webhook secret.")

    try:
        update = await request.json()
    except Exception:
        return {"ok": True}

    message = update.get("message") or update.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id = str(message.get("chat", {}).get("id", "")).strip()
    text = (message.get("text") or "").strip()

    if not chat_id or not text or text.startswith("/"):
        return {"ok": True}

    background_tasks.add_task(_handle_ceo_message, chat_id=chat_id, text=text)
    return {"ok": True}


def _handle_ceo_message(*, chat_id: str, text: str) -> None:
    """Process a CEO Telegram message and send back the AI answer."""
    from app.db.base import SessionLocal
    from app.services.telegram_alert_service import TelegramAlertService
    from app.services.telegram_service import TelegramService

    db = SessionLocal()
    try:
        answer = TelegramAlertService.route_ceo_message(db, chat_id=chat_id, text=text)
        if answer:
            TelegramService.send_message(chat_id, answer)
    except Exception:
        logger.exception("Error handling Telegram message from chat %s", chat_id)
    finally:
        db.close()
