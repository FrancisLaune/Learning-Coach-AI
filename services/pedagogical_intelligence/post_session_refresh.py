"""Post-session pedagogical refresh pipeline for LCAI-0019."""

from __future__ import annotations

import logging
from time import monotonic

from application.dto.pedagogical_intelligence import PostSessionRefreshResult
from domain.pedagogical_intelligence.paths import path_for_source_grade
from infrastructure.repositories.pedagogical_intelligence import DuckDBPedagogicalIntelligenceRepository
from services.pedagogical_intelligence.dashboard_service import PedagogicalDashboardService

logger = logging.getLogger(__name__)


class PostSessionPedagogicalRefreshService:
    REFRESH_VERSION = "pi-v1"

    def __init__(
        self,
        repository: DuckDBPedagogicalIntelligenceRepository,
        dashboard: PedagogicalDashboardService,
    ) -> None:
        self.repository = repository
        self.dashboard = dashboard

    def refresh(
        self,
        *,
        learner_id: int,
        session_id: int,
        pathway_code: str | None = None,
        correlation_id: str | None = None,
    ) -> PostSessionRefreshResult:
        started = monotonic()
        correlation = correlation_id or f"session:{session_id}"
        context = self.repository.learner_context(learner_id)
        path = path_for_source_grade(context["current_grade_code"] or "")
        resolved_pathway = pathway_code or (path.code if path else "UNKNOWN")
        existing = self.repository.load_refresh_run(
            learner_id=learner_id,
            session_id=session_id,
            pathway_code=resolved_pathway,
            refresh_version=self.REFRESH_VERSION,
        )
        if existing is not None:
            return PostSessionRefreshResult(
                learner_id=learner_id,
                session_id=session_id,
                pathway_code=resolved_pathway,
                status=str(existing["status"]),
                readiness_score=float(existing.get("readiness_score", 0.0)),
                recommendation_count=int(existing.get("recommendation_count", 0)),
                cache_version=self.REFRESH_VERSION,
                correlation_id=correlation,
                already_processed=True,
            )
        session = self.repository.load_session_summary(session_id)
        if session is None:
            raise ValueError("Session introuvable.")
        if str(session["status"]).upper() not in {"COMPLETED", "PAUSED"} and float(session["completion_rate"]) < 100:
            raise ValueError("La session n'est pas terminée.")

        dto = self.dashboard.load(learner_id, cache_version=None)
        snapshot = {
            "readiness_score": dto.readiness_score,
            "readiness_status": dto.readiness_status,
            "recommendation_count": len(dto.recommendations),
            "pathway_code": resolved_pathway,
        }
        self.repository.persist_refresh_run(
            learner_id=learner_id,
            session_id=session_id,
            pathway_code=resolved_pathway,
            refresh_version=self.REFRESH_VERSION,
            status="COMPLETED",
            correlation_id=correlation,
            snapshot=snapshot,
        )
        logger.info(
            "pedagogical_intelligence.session.refresh_completed",
            extra={
                "student_id": learner_id,
                "session_id": session_id,
                "pathway_code": resolved_pathway,
                "duration_ms": round((monotonic() - started) * 1000),
                "status": "COMPLETED",
            },
        )
        return PostSessionRefreshResult(
            learner_id=learner_id,
            session_id=session_id,
            pathway_code=resolved_pathway,
            status="COMPLETED",
            readiness_score=dto.readiness_score,
            recommendation_count=len(dto.recommendations),
            cache_version=self.REFRESH_VERSION,
            correlation_id=correlation,
            already_processed=False,
        )
