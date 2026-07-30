"""Resolve Professeur IA availability for LCAI-0020."""

from __future__ import annotations

from application.dto.student_guidance import AIAvailability, AIAvailabilityMode
from infrastructure.config.openai_settings import load_openai_api_key
from infrastructure.repositories.virtual_teacher import DuckDBVirtualTeacherRepository
from services.platform_runtime import default_flags


def resolve_ai_availability(
    *,
    learner_id: int,
    repository: DuckDBVirtualTeacherRepository | None = None,
) -> AIAvailability:
    flags = default_flags()
    platform_enabled = bool(flags.enabled("ai_tutor.enabled"))
    prefs_repo = repository or DuckDBVirtualTeacherRepository()
    preferences = prefs_repo.ensure_preferences(learner_id)
    learner_feature_enabled = bool(preferences.feature_enabled)
    provider_configured = bool(load_openai_api_key())

    if not platform_enabled:
        return AIAvailability(
            mode=AIAvailabilityMode.INACTIVE,
            platform_enabled=False,
            learner_feature_enabled=learner_feature_enabled,
            provider_configured=provider_configured,
            reason="Professeur IA désactivé par configuration plateforme.",
        )
    if not learner_feature_enabled:
        return AIAvailability(
            mode=AIAvailabilityMode.INACTIVE,
            platform_enabled=True,
            learner_feature_enabled=False,
            provider_configured=provider_configured,
            reason="Professeur IA non activé pour cet élève.",
        )
    if not provider_configured:
        return AIAvailability(
            mode=AIAvailabilityMode.UNAVAILABLE,
            platform_enabled=True,
            learner_feature_enabled=True,
            provider_configured=False,
            reason="Fournisseur IA non configuré — mode déterministe actif.",
        )
    return AIAvailability(
        mode=AIAvailabilityMode.ACTIVE,
        platform_enabled=True,
        learner_feature_enabled=True,
        provider_configured=True,
        reason="",
    )
