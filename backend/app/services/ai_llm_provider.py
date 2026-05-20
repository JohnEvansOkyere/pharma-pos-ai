"""
Server-side LLM provider adapter for the AI manager assistant.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

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
    DEFAULT_MODELS = {
        "openai": "gpt-4o-mini",
        "claude": "claude-3-5-haiku-latest",
        "groq": "llama-3.3-70b-versatile",
    }
    MAX_TOOL_ITERATIONS: int = 5

    @staticmethod
    def configured_provider() -> str:
        return settings.AI_MANAGER_PROVIDER.strip().lower()

    @staticmethod
    def configured_model(provider: Optional[str] = None) -> Optional[str]:
        if provider and provider.strip().lower() == "deterministic":
            return None
        if settings.AI_MANAGER_MODEL:
            return settings.AI_MANAGER_MODEL.strip()
        if provider:
            return AIManagerLLMProvider.DEFAULT_MODELS.get(provider.strip().lower())
        return None

    @staticmethod
    def is_external_provider_configured(provider: Optional[str] = None, model: Optional[str] = None) -> bool:
        provider = provider or AIManagerLLMProvider.configured_provider()
        model = model or AIManagerLLMProvider.configured_model(provider)
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
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        has_provider_override = provider is not None
        provider = (provider or AIManagerLLMProvider.configured_provider()).strip().lower()
        if model is not None:
            model = model.strip() or None
        else:
            model = AIManagerLLMProvider.configured_model(provider)

        history = conversation_history or []

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
                answer = AIManagerLLMProvider._openai(prompt=prompt, model=model or "", history=history)
            elif provider == "claude":
                answer = AIManagerLLMProvider._claude(prompt=prompt, model=model or "", history=history)
            elif provider == "groq":
                answer = AIManagerLLMProvider._groq(prompt=prompt, model=model or "", history=history)
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
    def generate_answer_with_tools(
        *,
        message: str,
        system_prompt: str,
        tools: List[Dict[str, Any]],
        tool_dispatcher: Callable[[str, Dict[str, Any]], Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        fallback_summary: str,
    ) -> Dict[str, Any]:
        """Tool-use entry point. The LLM calls registered tools to fetch business data."""
        provider = (provider or AIManagerLLMProvider.configured_provider()).strip().lower()
        if model is not None:
            model = model.strip() or None
        else:
            model = AIManagerLLMProvider.configured_model(provider)

        if provider == "deterministic" or not AIManagerLLMProvider.is_external_provider_configured(provider, model):
            return {
                "answer": fallback_summary,
                "provider": provider,
                "model": model,
                "fallback_used": True,
                "tool_trace": [],
            }

        history = conversation_history or []
        try:
            if provider in ("openai", "groq"):
                url = AIManagerLLMProvider.OPENAI_URL if provider == "openai" else AIManagerLLMProvider.GROQ_URL
                api_key = (settings.OPENAI_API_KEY if provider == "openai" else settings.GROQ_API_KEY) or ""
                answer, tool_trace = AIManagerLLMProvider._openai_tool_loop(
                    message=message,
                    system_prompt=system_prompt,
                    tools=tools,
                    tool_dispatcher=tool_dispatcher,
                    history=history,
                    model=model or "",
                    url=url,
                    api_key=api_key,
                )
            elif provider == "claude":
                answer, tool_trace = AIManagerLLMProvider._claude_tool_loop(
                    message=message,
                    system_prompt=system_prompt,
                    tools=AIManagerLLMProvider._to_anthropic_tools(tools),
                    tool_dispatcher=tool_dispatcher,
                    history=history,
                    model=model or "",
                )
            else:
                raise AIProviderUnavailable(f"Unsupported provider: {provider}")
        except Exception:
            return {
                "answer": fallback_summary,
                "provider": provider,
                "model": model,
                "fallback_used": True,
                "tool_trace": [],
            }

        return {
            "answer": answer or fallback_summary,
            "provider": provider,
            "model": model,
            "fallback_used": not bool(answer),
            "tool_trace": tool_trace,
        }

    @staticmethod
    def _openai_tool_loop(
        *,
        message: str,
        system_prompt: str,
        tools: List[Dict[str, Any]],
        tool_dispatcher: Callable[[str, Dict[str, Any]], Any],
        history: List[Dict[str, str]],
        model: str,
        url: str,
        api_key: str,
    ) -> tuple[str, List[Dict[str, Any]]]:
        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        messages.extend({"role": m["role"], "content": m["content"]} for m in history)
        messages.append({"role": "user", "content": message})
        tool_trace: List[Dict[str, Any]] = []
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        for _ in range(AIManagerLLMProvider.MAX_TOOL_ITERATIONS):
            payload = {
                "model": model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "max_tokens": settings.AI_MANAGER_MAX_TOKENS,
                "temperature": 0.2,
            }
            with httpx.Client(timeout=settings.AI_MANAGER_TIMEOUT_SECONDS) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
            choice = data["choices"][0]
            assistant_message = choice["message"]
            messages.append(assistant_message)
            if choice.get("finish_reason") != "tool_calls":
                return (assistant_message.get("content") or "").strip(), tool_trace
            for tc in assistant_message.get("tool_calls", []):
                name = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"] or "{}")
                result = tool_dispatcher(name, args)
                tool_trace.append({"tool": name, "arguments": args, "result": result})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result, default=str),
                })
        return "", tool_trace

    @staticmethod
    def _claude_tool_loop(
        *,
        message: str,
        system_prompt: str,
        tools: List[Dict[str, Any]],
        tool_dispatcher: Callable[[str, Dict[str, Any]], Any],
        history: List[Dict[str, str]],
        model: str,
    ) -> tuple[str, List[Dict[str, Any]]]:
        messages: List[Dict[str, Any]] = [{"role": m["role"], "content": m["content"]} for m in history]
        messages.append({"role": "user", "content": message})
        tool_trace: List[Dict[str, Any]] = []
        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY or "",
            "anthropic-version": AIManagerLLMProvider.ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }
        for _ in range(AIManagerLLMProvider.MAX_TOOL_ITERATIONS):
            payload = {
                "model": model,
                "system": system_prompt,
                "messages": messages,
                "tools": tools,
                "max_tokens": settings.AI_MANAGER_MAX_TOKENS,
                "temperature": 0.2,
            }
            with httpx.Client(timeout=settings.AI_MANAGER_TIMEOUT_SECONDS) as client:
                response = client.post(AIManagerLLMProvider.CLAUDE_URL, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
            content_blocks = data.get("content", [])
            messages.append({"role": "assistant", "content": content_blocks})
            if data.get("stop_reason") != "tool_use":
                for block in content_blocks:
                    if block.get("type") == "text" and block.get("text"):
                        return block["text"].strip(), tool_trace
                return "", tool_trace
            tool_results = []
            for block in content_blocks:
                if block.get("type") != "tool_use":
                    continue
                result = tool_dispatcher(block["name"], block.get("input", {}))
                tool_trace.append({"tool": block["name"], "arguments": block.get("input", {}), "result": result})
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": json.dumps(result, default=str),
                })
            messages.append({"role": "user", "content": tool_results})
        return "", tool_trace

    @staticmethod
    def _to_anthropic_tools(openai_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert OpenAI function-calling format to Anthropic tool-use format."""
        result = []
        for tool in openai_tools:
            fn = tool.get("function", tool)
            result.append({
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            })
        return result

    @staticmethod
    def _chat_completion(url: str, *, api_key: str, model: str, prompt: str, history: List[Dict[str, str]]) -> str:
        messages = [{"role": "system", "content": AIManagerLLMProvider._system_instructions()}]
        messages.extend({"role": m["role"], "content": m["content"]} for m in history)
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": model,
            "messages": messages,
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
    def _openai(*, prompt: str, model: str, history: List[Dict[str, str]]) -> str:
        return AIManagerLLMProvider._chat_completion(
            AIManagerLLMProvider.OPENAI_URL,
            api_key=settings.OPENAI_API_KEY or "",
            model=model,
            prompt=prompt,
            history=history,
        )

    @staticmethod
    def _groq(*, prompt: str, model: str, history: List[Dict[str, str]]) -> str:
        return AIManagerLLMProvider._chat_completion(
            AIManagerLLMProvider.GROQ_URL,
            api_key=settings.GROQ_API_KEY or "",
            model=model,
            prompt=prompt,
            history=history,
        )

    @staticmethod
    def _claude(*, prompt: str, model: str, history: List[Dict[str, str]]) -> str:
        messages = [{"role": m["role"], "content": m["content"]} for m in history]
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": model,
            "max_tokens": settings.AI_MANAGER_MAX_TOKENS,
            "temperature": 0.2,
            "system": AIManagerLLMProvider._system_instructions(),
            "messages": messages,
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
