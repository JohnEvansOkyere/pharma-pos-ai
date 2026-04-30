"""
Tenant-level policy for external AI provider use.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai_report import AIExternalProviderSetting


class AIProviderPolicyService:
    """Resolve and manage external AI provider policy for a tenant."""

    ALLOWED_PROVIDERS = {"openai", "claude", "groq"}

    @staticmethod
    def default_consent_text() -> str:
        return (
            "The pharmacy administrator enabled external AI processing for aggregate "
            "business reporting. Prompts must not include patient-identifiable, "
            "prescription-sensitive, or controlled-drug dispensing details."
        )

    @staticmethod
    def get_setting(db: Session, *, organization_id: int) -> Optional[AIExternalProviderSetting]:
        return (
            db.query(AIExternalProviderSetting)
            .filter(AIExternalProviderSetting.organization_id == organization_id)
            .first()
        )

    @staticmethod
    def get_or_default(db: Session, *, organization_id: int) -> Dict[str, object]:
        setting = AIProviderPolicyService.get_setting(db, organization_id=organization_id)
        if setting is None:
            return {
                "id": None,
                "organization_id": organization_id,
                "external_ai_enabled": False,
                "allowed_providers": [],
                "preferred_provider": None,
                "preferred_model": None,
                "consent_text": None,
                "consented_by_user_id": None,
                "consented_at": None,
                "updated_by_user_id": None,
                "created_at": None,
                "updated_at": None,
            }
        return AIProviderPolicyService.to_dict(setting)

    @staticmethod
    def upsert(
        db: Session,
        *,
        organization_id: int,
        external_ai_enabled: bool,
        allowed_providers: List[str],
        preferred_provider: Optional[str],
        preferred_model: Optional[str],
        consent_text: Optional[str],
        current_user_id: int,
    ) -> AIExternalProviderSetting:
        normalized_allowed = AIProviderPolicyService.normalize_providers(allowed_providers)
        normalized_provider = preferred_provider.strip().lower() if preferred_provider else None
        normalized_model = preferred_model.strip() if preferred_model else None

        if external_ai_enabled:
            if not normalized_provider:
                raise ValueError("preferred_provider is required when external AI is enabled")
            if normalized_provider not in normalized_allowed:
                raise ValueError("preferred_provider must be included in allowed_providers")
            if not normalized_model:
                raise ValueError("preferred_model is required when external AI is enabled")

        setting = AIProviderPolicyService.get_setting(db, organization_id=organization_id)
        if setting is None:
            setting = AIExternalProviderSetting(organization_id=organization_id)
            db.add(setting)

        setting.external_ai_enabled = external_ai_enabled
        setting.allowed_providers = normalized_allowed
        setting.preferred_provider = normalized_provider
        setting.preferred_model = normalized_model
        setting.consent_text = (consent_text or AIProviderPolicyService.default_consent_text()).strip() if external_ai_enabled else None
        setting.updated_by_user_id = current_user_id
        if external_ai_enabled:
            setting.consented_by_user_id = current_user_id
            setting.consented_at = datetime.now(timezone.utc)
        else:
            setting.consented_by_user_id = None
            setting.consented_at = None

        db.commit()
        db.refresh(setting)
        return setting

    @staticmethod
    def resolve_provider(db: Session, *, organization_id: int) -> Dict[str, object]:
        setting = AIProviderPolicyService.get_setting(db, organization_id=organization_id)
        if setting is None or not setting.external_ai_enabled:
            return {
                "provider": "deterministic",
                "model": None,
                "external_ai_enabled": False,
                "fallback_reason": "external_ai_disabled",
            }

        allowed = AIProviderPolicyService.normalize_providers(setting.allowed_providers or [])
        provider = (setting.preferred_provider or settings.AI_MANAGER_PROVIDER or "").strip().lower()
        model = (setting.preferred_model or settings.AI_MANAGER_MODEL or "").strip() or None

        if provider not in allowed:
            return {
                "provider": "deterministic",
                "model": None,
                "external_ai_enabled": False,
                "fallback_reason": "provider_not_allowed",
            }

        if provider not in AIProviderPolicyService.ALLOWED_PROVIDERS:
            return {
                "provider": "deterministic",
                "model": None,
                "external_ai_enabled": False,
                "fallback_reason": "unsupported_provider",
            }

        return {
            "provider": provider,
            "model": model,
            "external_ai_enabled": True,
            "fallback_reason": None,
        }

    @staticmethod
    def normalize_providers(providers: List[str]) -> List[str]:
        normalized: List[str] = []
        for provider in providers or []:
            value = provider.strip().lower() if isinstance(provider, str) else ""
            if not value:
                continue
            if value not in AIProviderPolicyService.ALLOWED_PROVIDERS:
                raise ValueError(f"Unsupported AI provider: {value}")
            if value not in normalized:
                normalized.append(value)
        return normalized

    @staticmethod
    def to_dict(setting: AIExternalProviderSetting) -> Dict[str, object]:
        return {
            "id": setting.id,
            "organization_id": setting.organization_id,
            "external_ai_enabled": setting.external_ai_enabled,
            "allowed_providers": setting.allowed_providers or [],
            "preferred_provider": setting.preferred_provider,
            "preferred_model": setting.preferred_model,
            "consent_text": setting.consent_text,
            "consented_by_user_id": setting.consented_by_user_id,
            "consented_at": setting.consented_at,
            "updated_by_user_id": setting.updated_by_user_id,
            "created_at": setting.created_at,
            "updated_at": setting.updated_at,
        }
