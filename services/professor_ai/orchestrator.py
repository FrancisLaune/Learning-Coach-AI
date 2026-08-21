"""Professor AI Core orchestrator — thin façade over existing engines (LCAI-0022A / 0022D).

The orchestrator decides *what* to do next; deterministic engines execute.
It must not invent scores, auto-approve content, or bypass repositories.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from application.dto.student_guidance import StudentDashboardSnapshot
from domain.unified_experience.models import HomeworkGenerationResult, HomeworkRequest
from services.professor_ai.decision_log import new_correlation_id
from services.professor_ai.models import (
    DecisionTraceEntry,
    HomeworkCompositionResult,
    ProfessorOperatingMode,
    SessionClosureResult,
    SessionOpenResult,
    SessionPlan,
)
from services.student_guidance.availability import resolve_ai_availability

ENGINE = "professor-ai-orchestrator-v1"


class GuidanceFacade(Protocol):
    def build_home_guidance(self, actor: dict[str, Any], learner_id: int) -> StudentDashboardSnapshot: ...

    def explain_session_result(self, actor: dict[str, Any], learner_id: int, session_id: int) -> Any: ...


class PedagogicalOverviewFacade(Protocol):
    def overview(self, learner_id: int) -> Any: ...

    def refresh_after_session(
        self,
        *,
        learner_id: int,
        session_id: int,
        pathway_code: str | None = None,
        correlation_id: str | None = None,
    ) -> Any: ...


class HomeworkFacade(Protocol):
    def create(self, request: HomeworkRequest) -> Any: ...

    def create_with_diagnostics(self, request: HomeworkRequest) -> HomeworkGenerationResult: ...


class HomeworkSessionFacade(Protocol):
    def open_for_learner(self, learner_id: int, homework_id: int, now: datetime) -> Any: ...


class PreferenceReader(Protocol):
    def ensure_preferences(self, learner_id: int) -> Any: ...


class DecisionLogFacade(Protocol):
    def record_trace(
        self,
        *,
        learner_id: int,
        mode: ProfessorOperatingMode,
        entries: tuple[DecisionTraceEntry, ...] | list[DecisionTraceEntry],
        correlation_id: str | None = None,
        homework_id: int | None = None,
        session_id: int | None = None,
        context: dict[str, object] | None = None,
    ) -> Any: ...


class ProfessorAIOrchestrator:
    """Chains Accueil → Diagnostic overview → Devoir → Ouverture séance → Synthèse."""

    def __init__(
        self,
        *,
        guidance: GuidanceFacade,
        pedagogical: PedagogicalOverviewFacade | None = None,
        homework: HomeworkFacade,
        homework_sessions: HomeworkSessionFacade | None = None,
        preferences: PreferenceReader | None = None,
        decision_log: DecisionLogFacade | None = None,
        availability_resolver=resolve_ai_availability,
    ) -> None:
        self.guidance = guidance
        self.pedagogical = pedagogical
        self.homework = homework
        self.homework_sessions = homework_sessions
        self.preferences = preferences
        self.decision_log = decision_log
        self._availability = availability_resolver

    def resolve_mode(
        self, learner_id: int, *, requested: ProfessorOperatingMode | None = None
    ) -> ProfessorOperatingMode:
        if requested is not None:
            if requested is ProfessorOperatingMode.PROFESSOR and not self._professor_allowed(learner_id):
                return ProfessorOperatingMode.MANUAL
            if requested is ProfessorOperatingMode.COMPANION and not self._professor_allowed(learner_id):
                return ProfessorOperatingMode.MANUAL
            return requested
        if not self._professor_allowed(learner_id):
            return ProfessorOperatingMode.MANUAL
        if self.preferences is not None:
            prefs = self.preferences.ensure_preferences(learner_id)
            from services.professor_ai.banner import parse_operating_mode

            return parse_operating_mode(getattr(prefs, "operating_mode", None))
        return ProfessorOperatingMode.PROFESSOR

    def plan_session(
        self,
        actor: dict[str, Any],
        learner_id: int,
        *,
        mode: ProfessorOperatingMode | None = None,
        now: datetime | None = None,
    ) -> SessionPlan:
        resolved = self.resolve_mode(learner_id, requested=mode)
        availability = self._availability(learner_id=learner_id)
        dashboard = self.guidance.build_home_guidance(actor, learner_id)
        correlation_id = new_correlation_id("plan")
        objective = str(getattr(dashboard.context, "objective", "") or "")
        trace = [
            DecisionTraceEntry(
                "ACCUEIL",
                "Message d'accueil et contexte élève chargés.",
                ENGINE,
                objective=objective or None,
            ),
        ]
        grade_label = "—"
        diagnostic_status = "UNKNOWN"
        recommendations: tuple[str, ...] = ()
        strengths: tuple[str, ...] = ()
        weaknesses: tuple[str, ...] = ()
        if self.pedagogical is not None and resolved is not ProfessorOperatingMode.MANUAL:
            overview = self.pedagogical.overview(learner_id)
            grade_label = str(getattr(overview, "current_grade_label", "—"))
            diagnostic_status = str(getattr(overview, "diagnostic_status", "UNKNOWN"))
            recommendations = tuple(getattr(overview, "recommendations", ()) or ())
            strengths = tuple(getattr(overview, "strengths", ()) or ())
            weaknesses = tuple(getattr(overview, "weaknesses", ()) or ())
            trace.append(
                DecisionTraceEntry(
                    "DIAGNOSTIC",
                    f"Vue pédagogique chargée (statut={diagnostic_status}).",
                    ENGINE,
                    objective=objective or None,
                    candidates=tuple(str(item) for item in recommendations[:8]),
                    exclusions=(),
                    deficit=tuple(
                        (key, value)
                        for key, value in (
                            ("strengths", ",".join(strengths[:5])),
                            ("weaknesses", ",".join(weaknesses[:5])),
                        )
                        if value
                    ),
                )
            )
        else:
            trace.append(
                DecisionTraceEntry(
                    "DIAGNOSTIC",
                    "Diagnostic pédagogique non consulté (mode manuel ou service indisponible).",
                    ENGINE,
                    objective=objective or None,
                )
            )
        entries = tuple(trace)
        self._persist(
            learner_id=learner_id,
            mode=resolved,
            entries=entries,
            correlation_id=correlation_id,
            context={"action": "plan_session", "diagnostic_status": diagnostic_status},
        )
        return SessionPlan(
            learner_id=learner_id,
            mode=resolved,
            welcome=dashboard.welcome,
            availability=availability,
            dashboard=dashboard,
            grade_label=grade_label,
            diagnostic_status=diagnostic_status,
            recommendations=recommendations,
            strengths=strengths,
            weaknesses=weaknesses,
            decision_trace=entries,
            planned_at=now or datetime.now(tz=UTC),
            correlation_id=correlation_id,
        )

    def compose_homework(
        self,
        request: HomeworkRequest,
        *,
        mode: ProfessorOperatingMode | None = None,
        with_diagnostics: bool = True,
    ) -> HomeworkCompositionResult:
        resolved = self.resolve_mode(request.learner_id, requested=mode)
        if resolved is ProfessorOperatingMode.COMPANION:
            raise PermissionError(
                "Le mode Compagnon ne peut pas créer ni modifier un devoir. Passez en mode Professeur IA ou Manuel."
            )
        correlation_id = new_correlation_id("hw")
        objective = f"devoir subject={request.subject_id} count={request.exercise_count}"
        trace = [
            DecisionTraceEntry(
                "PLANIFICATION",
                f"Constitution du devoir (mode={resolved.value}, exercices={request.exercise_count}).",
                ENGINE,
                objective=objective,
                candidates=tuple(f"skill:{skill_id}" for skill_id in request.skill_ids[:20]),
            )
        ]
        generation: HomeworkGenerationResult | None = None
        if with_diagnostics:
            generation = self.homework.create_with_diagnostics(request)
            homework = generation.homework
            deficit = (
                ("requested", str(generation.requested_count)),
                ("catalog", str(generation.catalog_count)),
                ("ai_requested", str(generation.ai_requested_count)),
                ("ai_accepted", str(generation.ai_accepted_count)),
                ("final", str(generation.final_count)),
                ("degraded", str(generation.degraded_mode)),
            )
            if generation.degradation_reason:
                deficit = (*deficit, ("degradation_reason", generation.degradation_reason))
            shortfall = max(0, generation.requested_count - generation.catalog_count)
            exclusions = (f"catalog_shortfall:{shortfall}",) if shortfall else ()
            candidates = tuple(f"content:{cid}" for cid in homework.selected_content_ids[:40])
            if generation.runtime_exercise_ids:
                candidates = candidates + tuple(f"runtime:{rid}" for rid in generation.runtime_exercise_ids[:40])
            trace.append(
                DecisionTraceEntry(
                    "CREATION_DEVOIR",
                    (
                        f"Devoir {homework.homework_id} créé "
                        f"(catalogue={generation.catalog_count}, générés={generation.ai_accepted_count})."
                    ),
                    ENGINE,
                    objective=objective,
                    candidates=candidates,
                    exclusions=exclusions,
                    deficit=deficit,
                )
            )
        else:
            homework = self.homework.create(request)
            candidates = tuple(f"content:{cid}" for cid in homework.selected_content_ids[:40])
            trace.append(
                DecisionTraceEntry(
                    "CREATION_DEVOIR",
                    f"Devoir {homework.homework_id} créé depuis le catalogue.",
                    ENGINE,
                    objective=objective,
                    candidates=candidates,
                )
            )
        entries = tuple(trace)
        self._persist(
            learner_id=request.learner_id,
            mode=resolved,
            entries=entries,
            correlation_id=correlation_id,
            homework_id=homework.homework_id,
            context={"action": "compose_homework", "subject_id": request.subject_id},
        )
        return HomeworkCompositionResult(
            mode=resolved,
            homework=homework,
            generation=generation,
            decision_trace=entries,
            correlation_id=correlation_id,
        )

    def open_session(
        self,
        learner_id: int,
        homework_id: int,
        *,
        mode: ProfessorOperatingMode | None = None,
        now: datetime | None = None,
    ) -> SessionOpenResult:
        resolved = self.resolve_mode(learner_id, requested=mode)
        if self.homework_sessions is None:
            raise RuntimeError("Le service d'ouverture de séance devoir est indisponible.")
        correlation_id = new_correlation_id("open")
        opened = self.homework_sessions.open_for_learner(learner_id, homework_id, now or datetime.now(tz=UTC))
        if opened.session_id is None:
            raise ValueError("HOMEWORK_SESSION_NOT_MATERIALIZED")
        entries = (
            DecisionTraceEntry(
                "OUVERTURE_SEANCE",
                f"Séance {opened.session_id} ouverte pour le devoir {homework_id}.",
                ENGINE,
                objective=f"homework:{homework_id}",
                candidates=(f"homework:{homework_id}", f"session:{opened.session_id}"),
            ),
        )
        self._persist(
            learner_id=learner_id,
            mode=resolved,
            entries=entries,
            correlation_id=correlation_id,
            homework_id=homework_id,
            session_id=int(opened.session_id),
            context={"action": "open_session"},
        )
        return SessionOpenResult(
            mode=resolved,
            homework=opened,
            session_id=int(opened.session_id),
            decision_trace=entries,
            correlation_id=correlation_id,
        )

    def close_session_cycle(
        self,
        actor: dict[str, Any],
        learner_id: int,
        session_id: int,
        *,
        mode: ProfessorOperatingMode | None = None,
        refresh: bool = True,
    ) -> SessionClosureResult:
        resolved = self.resolve_mode(learner_id, requested=mode)
        correlation_id = new_correlation_id("close")
        explanation = self.guidance.explain_session_result(actor, learner_id, session_id)
        refresh_triggered = False
        trace = [
            DecisionTraceEntry(
                "ANALYSE",
                "Explication de séance demandée via guidance élève.",
                ENGINE,
                objective=f"session:{session_id}",
                candidates=(f"session:{session_id}",),
            )
        ]
        if refresh and self.pedagogical is not None and resolved is not ProfessorOperatingMode.MANUAL:
            self.pedagogical.refresh_after_session(
                learner_id=learner_id,
                session_id=session_id,
                correlation_id=f"professor-ai:{session_id}",
            )
            refresh_triggered = True
            trace.append(
                DecisionTraceEntry(
                    "PREPARATION_PROCHAINE",
                    "Rafraîchissement pédagogique post-séance déclenché.",
                    ENGINE,
                    objective=f"session:{session_id}",
                    exclusions=("direct_score_mutation",),
                    deficit=(("refresh", "true"),),
                )
            )
        entries = tuple(trace)
        self._persist(
            learner_id=learner_id,
            mode=resolved,
            entries=entries,
            correlation_id=correlation_id,
            session_id=session_id,
            context={"action": "close_session_cycle", "refresh_triggered": refresh_triggered},
        )
        return SessionClosureResult(
            mode=resolved,
            learner_id=learner_id,
            session_id=session_id,
            explanation_available=explanation is not None,
            refresh_triggered=refresh_triggered,
            decision_trace=entries,
            correlation_id=correlation_id,
        )

    def _persist(
        self,
        *,
        learner_id: int,
        mode: ProfessorOperatingMode,
        entries: tuple[DecisionTraceEntry, ...],
        correlation_id: str,
        homework_id: int | None = None,
        session_id: int | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        if self.decision_log is None:
            return
        self.decision_log.record_trace(
            learner_id=learner_id,
            mode=mode,
            entries=entries,
            correlation_id=correlation_id,
            homework_id=homework_id,
            session_id=session_id,
            context=context,
        )

    def _professor_allowed(self, learner_id: int) -> bool:
        """Professeur/Compagnon only when platform AI is on and learner feature is enabled."""
        from application.dto.student_guidance import AIAvailabilityMode

        availability = self._availability(learner_id=learner_id)
        if availability.mode is AIAvailabilityMode.INACTIVE:
            return False
        if self.preferences is not None:
            prefs = self.preferences.ensure_preferences(learner_id)
            return bool(getattr(prefs, "feature_enabled", False))
        return bool(availability.learner_feature_enabled)
