"""Dashboard assembly for LCAI-0019 using learning intelligence evidence."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from time import monotonic

from application.dto.pedagogical_intelligence import (
    LearningPlanDTO,
    PedagogicalDashboardDTO,
    RecommendationDTO,
    SkillInsightDTO,
)
from domain.learning_intelligence.models import EvidenceWindow
from domain.pedagogical_intelligence.paths import path_for_source_grade
from infrastructure.repositories.pedagogical_intelligence import DuckDBPedagogicalIntelligenceRepository
from services.learning_intelligence import LearningIntelligenceService
from services.pedagogical_intelligence.readiness_service import ReadinessService
from services.pedagogical_intelligence.recommendation_service import PedagogicalRecommendationService

logger = logging.getLogger(__name__)


class PedagogicalDashboardService:
    REFRESH_VERSION = "pi-dashboard-v1"

    def __init__(
        self,
        repository: DuckDBPedagogicalIntelligenceRepository,
        intelligence: LearningIntelligenceService | None = None,
    ) -> None:
        self.repository = repository
        self.intelligence = intelligence
        self.recommendations = PedagogicalRecommendationService()
        self.readiness = ReadinessService()

    def load(self, learner_id: int, *, cache_version: str | None = None) -> PedagogicalDashboardDTO:
        started = monotonic()
        now = datetime.now(UTC)
        context = self.repository.learner_context(learner_id)
        from domain.pedagogical_intelligence.paths import path_for_source_grade

        path = path_for_source_grade(context["current_grade_code"] or "")
        pathway_code = path.code if path else "UNKNOWN"
        transition = self.repository.transition_readiness(learner_id, path.target_grade_code) if path else None
        readiness_band = "NOT_READY"
        readiness_score = 0.0
        coverage = 0.0
        confidence = 0.0
        if transition is not None:
            mastery_norm = min(1.0, float(transition["score"]) / 100 if float(transition["score"]) > 1 else float(transition["score"]))
            critical = 1.0 - min(1.0, len(transition["blocking_skill_ids"]) / max(1, len(transition["acquired_skill_ids"]) + len(transition["blocking_skill_ids"])))
            computed = self.readiness.compute(
                mastery_score=mastery_norm,
                coverage_score=float(transition["coverage"]),
                confidence_score=float(transition["confidence"]),
                critical_score=critical,
                stability_score=0.7,
            )
            readiness_band = computed.band
            readiness_score = computed.score
            coverage = computed.coverage
            confidence = computed.confidence
        mastery_rows = self.repository.mastery_summary(learner_id, limit=20)
        planner = self.repository.planner_highlights(learner_id)
        from domain.pedagogical_intelligence.models import ReadinessSnapshot

        readiness_snapshot = None
        if path is not None:
            readiness_snapshot = ReadinessSnapshot(
                path.code,
                path.source_grade_code,
                path.target_grade_code,
                readiness_score * 100,
                coverage,
                confidence,
                readiness_band,
                len(transition["acquired_skill_ids"]) if transition else 0,
                len(transition["fragile_skill_ids"]) if transition else 0,
                len(transition["blocking_skill_ids"]) if transition else 0,
                (),
            )
        strong, fragile, critical = self._skill_insights(mastery_rows, readiness_snapshot)
        reco_rows = self.recommendations.build(
            readiness=readiness_snapshot,
            mastery=mastery_rows,
            diagnostic_status=str(context["diagnostic_status"]),
        )
        plan = LearningPlanDTO(
            highlights=tuple(item.label for item in planner),
            session_count=len(planner),
            horizon_days=7,
        )
        progression_7d, progression_30d = self._progression(learner_id, now)
        sources = self._sources(str(context["diagnostic_status"]), mastery_rows, planner)
        message = self._student_message(readiness_snapshot, reco_rows)
        dto = PedagogicalDashboardDTO(
            student_id=str(learner_id),
            pathway_code=pathway_code,
            readiness_status=readiness_band,
            readiness_score=readiness_score,
            coverage_score=coverage,
            confidence_score=confidence,
            strong_skills=strong,
            fragile_skills=fragile,
            critical_gaps=critical,
            recommendations=reco_rows,
            current_plan=plan if plan.session_count else None,
            progression_7d=progression_7d,
            progression_30d=progression_30d,
            last_computed_at=now,
            data_sources=sources,
            pedagogical_message=message,
        )
        logger.info(
            "pedagogical_intelligence.dashboard.loaded",
            extra={
                "student_id": learner_id,
                "pathway_code": pathway_code,
                "duration_ms": round((monotonic() - started) * 1000),
                "cache_hit": bool(cache_version),
                "result_status": "OK",
            },
        )
        return dto

    def _progression(self, learner_id: int, now: datetime) -> tuple[float | None, float | None]:
        if self.intelligence is None:
            return None, None
        window_7 = EvidenceWindow(now - timedelta(days=7), now, "7d")
        window_30 = EvidenceWindow(now - timedelta(days=30), now, "30d")
        overview_7 = self.intelligence.overview(learner_id, window_7, now)
        overview_30 = self.intelligence.overview(learner_id, window_30, now)
        return float(overview_7.evidence_count), float(overview_30.evidence_count)

    @staticmethod
    def _skill_insights(mastery_rows, readiness) -> tuple[tuple[SkillInsightDTO, ...], tuple[SkillInsightDTO, ...], tuple[SkillInsightDTO, ...]]:
        strong: list[SkillInsightDTO] = []
        fragile: list[SkillInsightDTO] = []
        critical: list[SkillInsightDTO] = []
        blocking = set()
        if readiness is not None:
            blocking = set()
        for row in sorted(mastery_rows, key=lambda item: -item.score):
            insight = SkillInsightDTO(
                skill_id=str(row.skill_id),
                skill_code=str(row.skill_id),
                label=row.label,
                mastery_score=row.score / 100 if row.score > 1 else row.score,
                confidence_score=0.7 if row.score >= 70 else 0.4,
                status=row.level,
                priority=max(1, int(100 - row.score)),
                reason=f"Tendance {row.trend}",
            )
            if row.score >= 75:
                strong.append(insight)
            elif row.score >= 55:
                fragile.append(insight)
            else:
                critical.append(insight)
        return tuple(strong[:5]), tuple(fragile[:5]), tuple(critical[:5])

    @staticmethod
    def _sources(diagnostic_status: str, mastery_rows, planner) -> tuple[str, ...]:
        sources: list[str] = []
        if diagnostic_status == "COMPLETED":
            sources.append("diagnostic")
        if mastery_rows:
            sources.append("historique")
        if planner:
            sources.append("sessions")
        if not sources:
            sources.append("profil")
        return tuple(sources)

    @staticmethod
    def _student_message(readiness, recommendations: tuple[RecommendationDTO, ...]) -> str:
        if recommendations and recommendations[0].recommendation_type == "TAKE_DIAGNOSTIC":
            return "Commence par le diagnostic adaptatif pour personnaliser ton parcours."
        if readiness is None:
            return "Ton parcours se construit au fil des activités."
        if readiness.band == "READY":
            return "Tu es prêt·e : continue avec une séance de consolidation."
        if readiness.band == "ALMOST_READY":
            return "Encore un effort : concentre-toi sur les compétences fragiles."
        return "Priorise les compétences bloquantes avec des séances courtes."
