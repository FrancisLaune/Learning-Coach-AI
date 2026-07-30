"""Pedagogical intelligence platform facade for LCAI-0019."""

from __future__ import annotations

from application.dto.pedagogical_intelligence import (
    DiagnosticAnswerResultDTO,
    DiagnosticRunDTO,
    DiagnosticSummaryDTO,
    PedagogicalDashboardDTO,
    PostSessionRefreshResult,
)
from domain.pedagogical_intelligence.engine import classify_readiness_band, readiness_explanations
from domain.pedagogical_intelligence.models import PedagogicalIntelligenceOverview, ReadinessPathCode, ReadinessSnapshot
from domain.pedagogical_intelligence.paths import path_for_source_grade
from infrastructure.repositories.pedagogical_intelligence import DuckDBPedagogicalIntelligenceRepository
from services.pedagogical_intelligence.adaptive_diagnostic_service import AdaptiveDiagnosticService
from services.pedagogical_intelligence.dashboard_service import PedagogicalDashboardService
from services.pedagogical_intelligence.post_session_refresh import PostSessionPedagogicalRefreshService
from services.pedagogical_intelligence.recommendation_service import PedagogicalRecommendationService


class PedagogicalIntelligenceService:
    def __init__(
        self,
        repository: DuckDBPedagogicalIntelligenceRepository,
        diagnostic_service: AdaptiveDiagnosticService | None = None,
        dashboard_service: PedagogicalDashboardService | None = None,
        refresh_service: PostSessionPedagogicalRefreshService | None = None,
    ) -> None:
        self.repository = repository
        self.diagnostic_service = diagnostic_service
        self.dashboard_service = dashboard_service
        self.refresh_service = refresh_service
        self.recommendations = PedagogicalRecommendationService()

    def overview(self, learner_id: int) -> PedagogicalIntelligenceOverview:
        context = self.repository.learner_context(learner_id)
        grade_code = context["current_grade_code"]
        active_path = path_for_source_grade(grade_code) if grade_code else None
        readiness = self._readiness(learner_id, active_path.code if active_path else None, active_path)
        mastery = self.repository.mastery_summary(learner_id)
        reco_dtos = self.recommendations.build(
            readiness=readiness,
            mastery=mastery,
            diagnostic_status=str(context["diagnostic_status"]),
        )
        recommendations = tuple(f"{item.recommendation_type}: {item.reason}" for item in reco_dtos)
        strengths, weaknesses = self._strengths_weaknesses(mastery)
        planner = self.repository.planner_highlights(learner_id)
        active_diagnostic = self.repository.active_diagnostic_run(learner_id)
        return PedagogicalIntelligenceOverview(
            learner_id=learner_id,
            display_name=str(context["display_name"]),
            current_grade_code=grade_code or "—",
            current_grade_label=str(context["current_grade_label"] or "—"),
            diagnostic_status=str(context["diagnostic_status"]),
            active_path=active_path,
            readiness=readiness,
            mastery=mastery,
            strengths=strengths,
            weaknesses=weaknesses,
            planner_highlights=planner,
            recommendations=recommendations,
            active_diagnostic=active_diagnostic,
        )

    def dashboard(self, learner_id: int, *, cache_version: str | None = None) -> PedagogicalDashboardDTO:
        if self.dashboard_service is None:
            raise RuntimeError("Dashboard pédagogique indisponible.")
        return self.dashboard_service.load(learner_id, cache_version=cache_version)

    def refresh_after_session(
        self,
        *,
        learner_id: int,
        session_id: int,
        pathway_code: str | None = None,
        correlation_id: str | None = None,
    ) -> PostSessionRefreshResult:
        if self.refresh_service is None:
            raise RuntimeError("Refresh post-session indisponible.")
        return self.refresh_service.refresh(
            learner_id=learner_id,
            session_id=session_id,
            pathway_code=pathway_code,
            correlation_id=correlation_id,
        )

    def start_diagnostic(self, learner_id: int, path_code: ReadinessPathCode) -> DiagnosticRunDTO:
        if self.diagnostic_service is None:
            raise RuntimeError("Le diagnostic adaptatif est indisponible.")
        return self.diagnostic_service.start(learner_id, path_code)

    def submit_diagnostic_answer(
        self,
        *,
        run_id: int,
        learner_id: int,
        exercise_id: int,
        answer: object,
        elapsed_ms: int = 0,
    ) -> DiagnosticAnswerResultDTO:
        if self.diagnostic_service is None:
            raise RuntimeError("Le diagnostic adaptatif est indisponible.")
        return self.diagnostic_service.submit_answer(
            run_id=run_id,
            learner_id=learner_id,
            exercise_id=exercise_id,
            answer=answer,
            elapsed_ms=elapsed_ms,
        )

    def complete_diagnostic(self, run_id: int) -> DiagnosticSummaryDTO:
        if self.diagnostic_service is None:
            raise RuntimeError("Le diagnostic adaptatif est indisponible.")
        return self.diagnostic_service.complete(run_id=run_id)

    def _readiness(
        self,
        learner_id: int,
        path_code: ReadinessPathCode | None,
        active_path,
    ) -> ReadinessSnapshot | None:
        if active_path is None or path_code is None:
            return None
        row = self.repository.transition_readiness(learner_id, active_path.target_grade_code)
        if row is None:
            return ReadinessSnapshot(
                path_code=path_code,
                source_grade_code=active_path.source_grade_code,
                target_grade_code=active_path.target_grade_code,
                score=0.0,
                coverage=0.0,
                confidence=0.0,
                band="NOT_READY",
                acquired_count=0,
                fragile_count=0,
                blocking_count=0,
                explanations=(
                    "Aucune évaluation de préparation disponible.",
                    "Lance un diagnostic pour initialiser le profil.",
                ),
            )
        acquired = len(row["acquired_skill_ids"])
        fragile = len(row["fragile_skill_ids"])
        blocking = len(row["blocking_skill_ids"])
        band = classify_readiness_band(
            score=float(row["score"]),
            coverage=float(row["coverage"]),
            confidence=float(row["confidence"]),
        )
        explanations = readiness_explanations(
            band=band,
            acquired_count=acquired,
            fragile_count=fragile,
            blocking_count=blocking,
            target_grade_label=active_path.label,
        )
        return ReadinessSnapshot(
            path_code=path_code,
            source_grade_code=str(row["source_grade_code"]),
            target_grade_code=str(row["target_grade_code"]),
            score=float(row["score"]),
            coverage=float(row["coverage"]),
            confidence=float(row["confidence"]),
            band=band,
            acquired_count=acquired,
            fragile_count=fragile,
            blocking_count=blocking,
            explanations=explanations,
        )

    @staticmethod
    def _strengths_weaknesses(mastery) -> tuple[tuple[str, ...], tuple[str, ...]]:
        if not mastery:
            return (), ()
        sorted_items = sorted(mastery, key=lambda item: item.score, reverse=True)
        strengths = tuple(item.label for item in sorted_items[:5] if item.score >= 70)
        weaknesses = tuple(item.label for item in reversed(sorted_items) if item.score < 55)
        return strengths[:5], weaknesses[:5]
