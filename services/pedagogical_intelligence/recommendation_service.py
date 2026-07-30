"""Deterministic pedagogical recommendations for LCAI-0019."""

from __future__ import annotations

from application.dto.pedagogical_intelligence import RecommendationDTO
from domain.pedagogical_intelligence.models import MasterySummaryItem, ReadinessSnapshot


class PedagogicalRecommendationService:
    DECISION_VERSION = "pi-reco-v1"

    def build(
        self,
        *,
        readiness: ReadinessSnapshot | None,
        mastery: tuple[MasterySummaryItem, ...],
        diagnostic_status: str,
    ) -> tuple[RecommendationDTO, ...]:
        existing_keys: set[str] = set()
        items: list[RecommendationDTO] = []
        if diagnostic_status not in {"COMPLETED", "PLANNED"} and readiness is not None:
            self._add(
                items,
                existing_keys,
                RecommendationDTO(
                    "TAKE_DIAGNOSTIC",
                    100,
                    "Initialiser le profil pédagogique avec un diagnostic adaptatif.",
                    "—",
                    "—",
                    "diagnostic_activity",
                    20,
                    None,
                    "ACTIVE",
                    self.DECISION_VERSION,
                ),
            )
        if readiness is not None and readiness.band == "NOT_READY":
            for index, row in enumerate(mastery[:3]):
                if row.score >= 55:
                    continue
                self._add(
                    items,
                    existing_keys,
                    RecommendationDTO(
                        "REMEDIATE_CRITICAL_SKILL",
                        90 - index,
                        "Compétence bloquante pour la préparation au niveau suivant.",
                        row.label,
                        "—",
                        "exercise",
                        15,
                        None,
                        "ACTIVE",
                        self.DECISION_VERSION,
                    ),
                    skill_id=str(row.skill_id),
                )
        for index, row in enumerate([item for item in mastery if 55 <= item.score < 75][:2]):
            self._add(
                items,
                existing_keys,
                RecommendationDTO(
                    "CONSOLIDATE_FRAGILE_SKILL",
                    70 - index,
                    "Consolider une compétence fragile avant d'accélérer.",
                    row.label,
                    "—",
                    "exercise",
                    12,
                    None,
                    "ACTIVE",
                    self.DECISION_VERSION,
                ),
                skill_id=str(row.skill_id),
            )
        for index, row in enumerate([item for item in mastery if item.score >= 80][:1]):
            self._add(
                items,
                existing_keys,
                RecommendationDTO(
                    "CONFIRM_ACQUIRED_SKILL",
                    40 - index,
                    "Confirmer une compétence solide avec une activité courte.",
                    row.label,
                    "—",
                    "exercise",
                    10,
                    None,
                    "ACTIVE",
                    self.DECISION_VERSION,
                ),
                skill_id=str(row.skill_id),
            )
        if readiness is not None and readiness.band == "READY":
            self._add(
                items,
                existing_keys,
                RecommendationDTO(
                    "ADVANCE_TO_NEXT_CHAPTER",
                    30,
                    "Profil prêt : avancer vers le chapitre suivant du parcours.",
                    "—",
                    "—",
                    "exercise",
                    20,
                    None,
                    "ACTIVE",
                    self.DECISION_VERSION,
                ),
            )
        if not items:
            self._add(
                items,
                existing_keys,
                RecommendationDTO(
                    "REST_OR_LIGHT_SESSION",
                    10,
                    "Commencer par une séance courte pour collecter des preuves d'apprentissage.",
                    "—",
                    "—",
                    "exercise",
                    10,
                    None,
                    "ACTIVE",
                    self.DECISION_VERSION,
                ),
            )
        return tuple(sorted(items, key=lambda item: -item.priority))

    @staticmethod
    def _add(
        items: list[RecommendationDTO],
        existing: set[str],
        recommendation: RecommendationDTO,
        *,
        skill_id: str = "—",
    ) -> None:
        key = f"{recommendation.recommendation_type}:{skill_id}"
        if key in existing:
            return
        existing.add(key)
        items.append(recommendation)
