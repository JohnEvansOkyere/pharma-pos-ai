"""
Server-side LLM provider adapter for the AI manager assistant.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from app.core.config import settings


class AIProviderUnavailable(Exception):
    """Raised when a configured provider cannot be used."""


class AIManagerLLMProvider:
    """Minimal HTTP adapter for OpenAI, Claude, and Groq text responses."""

    OPENAI_URL = "https://api.openai.com/v1/chat/completions"
    CLAUDE_URL = "https://api.anthropic.com/v1/messages"
    GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
    ANTHROPIC_VERSION = "2023-06-01"

    @staticmethod
    def configured_provider() -> str:
        return settings.AI_MANAGER_PROVIDER.strip().lower()

    @staticmethod
    def configured_model() -> Optional[str]:
        return settings.AI_MANAGER_MODEL.strip() if settings.AI_MANAGER_MODEL else None

    @staticmethod
    def is_external_provider_configured(provider: Optional[str] = None, model: Optional[str] = None) -> bool:
        provider = provider or AIManagerLLMProvider.configured_provider()
        model = model or AIManagerLLMProvider.configured_model()
        if provider == "openai":
            return bool(settings.OPENAI_API_KEY and model)
        if provider == "claude":
            return bool(settings.ANTHROPIC_API_KEY and model)
        if provider == "groq":
            return bool(settings.GROQ_API_KEY and model)
        return False

    @staticmethod
    def generate_answer(
        *,
        prompt: str,
        deterministic_answer: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        has_provider_override = provider is not None
        provider = (provider or AIManagerLLMProvider.configured_provider()).strip().lower()
        if model is not None:
            model = model.strip() or None
        elif has_provider_override:
            model = None
        else:
            model = AIManagerLLMProvider.configured_model()

        if provider == "deterministic":
            return {
                "answer": deterministic_answer,
                "provider": provider,
                "model": model,
                "fallback_used": False,
            }

        if not AIManagerLLMProvider.is_external_provider_configured(provider, model):
            return {
                "answer": deterministic_answer,
                "provider": provider,
                "model": model,
                "fallback_used": True,
            }

        try:
            if provider == "openai":
                answer = AIManagerLLMProvider._openai(prompt=prompt, model=model or "")
            elif provider == "claude":
                answer = AIManagerLLMProvider._claude(prompt=prompt, model=model or "")
            elif provider == "groq":
                answer = AIManagerLLMProvider._groq(prompt=prompt, model=model or "")
            else:
                raise AIProviderUnavailable(f"Unsupported AI provider: {provider}")
        except Exception:
            return {
                "answer": deterministic_answer,
                "provider": provider,
                "model": model,
                "fallback_used": True,
            }

        return {
            "answer": answer or deterministic_answer,
            "provider": provider,
            "model": model,
            "fallback_used": not bool(answer),
        }

    @staticmethod
    def _chat_completion(url: str, *, api_key: str, model: str, prompt: str) -> str:
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": AIManagerLLMProvider._system_instructions(),
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": settings.AI_MANAGER_MAX_TOKENS,
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=settings.AI_MANAGER_TIMEOUT_SECONDS) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    @staticmethod
    def _openai(*, prompt: str, model: str) -> str:
        return AIManagerLLMProvider._chat_completion(
            AIManagerLLMProvider.OPENAI_URL,
            api_key=settings.OPENAI_API_KEY or "",
            model=model,
            prompt=prompt,
        )

    @staticmethod
    def _groq(*, prompt: str, model: str) -> str:
        return AIManagerLLMProvider._chat_completion(
            AIManagerLLMProvider.GROQ_URL,
            api_key=settings.GROQ_API_KEY or "",
            model=model,
            prompt=prompt,
        )

    @staticmethod
    def _claude(*, prompt: str, model: str) -> str:
        payload = {
            "model": model,
            "max_tokens": settings.AI_MANAGER_MAX_TOKENS,
            "temperature": 0.2,
            "system": AIManagerLLMProvider._system_instructions(),
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY or "",
            "anthropic-version": AIManagerLLMProvider.ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=settings.AI_MANAGER_TIMEOUT_SECONDS) as client:
            response = client.post(AIManagerLLMProvider.CLAUDE_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        for part in data.get("content", []):
            if part.get("type") == "text" and part.get("text"):
                return part["text"].strip()
        return ""

    @staticmethod
    def _system_instructions() -> str:
        return (
            "You are a read-only pharmacy business manager assistant. Use only the supplied "
            "aggregate reporting data. Do not claim access to patient records, mutate stock, "
            "approve dispensing, override pharmacy rules, provide clinical advice, or provide "
            "controlled-drug guidance. Keep answers concise, operational, and explicit about "
            "the reporting window and branch scope."
        )
