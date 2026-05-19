"""
Telegram Bot API adapter for outbound messages and webhook management.
"""
from __future__ import annotations

from typing import Any, Dict, List

import httpx

from app.core.config import settings


class TelegramService:
    """Thin HTTP adapter for the Telegram Bot API."""

    SEVERITY_EMOJI: Dict[str, str] = {
        "critical": "\U0001f534",  # 🔴
        "high": "\U0001f7e0",      # 🟠
        "medium": "\U0001f7e1",    # 🟡
        "low": "⚪",           # ⚪
    }

    @staticmethod
    def is_configured() -> bool:
        return bool(settings.TELEGRAM_BOT_TOKEN)

    @staticmethod
    def send_message(chat_id: str, text: str, *, parse_mode: str = "HTML") -> Dict[str, Any]:
        if not settings.TELEGRAM_BOT_TOKEN:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured.")
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text[:4096],
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        with httpx.Client(timeout=15) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def format_alert(*, severity: str, title: str, summary: str, action_hint: str = "") -> str:
        emoji = TelegramService.SEVERITY_EMOJI.get(severity, "⚪")
        lines = [f"{emoji} <b>{title}</b>", summary]
        if action_hint:
            lines.append(f"<i>Action: {action_hint}</i>")
        return "\n".join(lines)

    @staticmethod
    def format_briefing(findings: List[Dict[str, Any]], *, date_label: str, scope_label: str) -> str:
        header = f"\U0001f4ca <b>Daily Briefing — {date_label}</b>\n<i>{scope_label}</i>"
        if not findings:
            return header + "\n\nNo significant findings today. All metrics look stable."
        lines = [header, ""]
        for finding in findings[:8]:
            emoji = TelegramService.SEVERITY_EMOJI.get(finding.get("severity", "low"), "⚪")
            title = finding.get("title", "")
            summary = finding.get("summary", "")[:140]
            lines.append(f"{emoji} <b>{title}</b>")
            lines.append(summary)
            lines.append("")
        lines.append("<i>Reply with any question about your pharmacy data.</i>")
        return "\n".join(lines)[:4096]
