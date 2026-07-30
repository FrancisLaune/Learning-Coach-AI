"""Unified student guidance façade for LCAI-0020."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, Protocol

from application.dto.student_guidance import (
    AIAvailability,
    AIAvailabilityMode,
    GuidanceSource,
    HomeworkGuidanceContext,
    HomeworkGuidanceResponse,
    HomeworkSummaryItem,
    MasteryBand,
    MasterySnapshotItem,
    ResultExplanationContext,
    RevisionGuidanceContext,
    RevisionPriority,
    StudentDashboardSnapshot,
    StudentHomeContext,
    WelcomeGuidance,
)
from domain.unified_experience.models import AssignmentStatus
from domain.virtual_teacher.models import ConversationRequest, PedagogicalContext
from infrastructure.repositories.virtual_teacher import DuckDBVirtualTeacherRepository
from services.auth.roles import AuthRole, normalize_auth_role
from services.learning_session.experience import LearnerExperienceService, MasteryView, StudentDashboard
from services.pedagogical_intelligence.dashboard_service import PedagogicalDashboardService
from services.pedagogical_intelligence.recommendation_service import PedagogicalRecommendationService
from services.student_guidance.availability import resolve_ai_availability
from services.student_guidance.deterministic import (
    build_ai_welcome,
    build_deterministic_welcome,
    explain_result,
    homework_before,
    homework_during,
    revision_guidance,
)
from services.student_guidance.mastery_bands import band_label, classify_mastery_band
from services.unified_experience import DeterministicCoachService, HomeworkService
from services.virtual_teacher.ai_conversation_orchestrator import AIConversationOrchestrator
from services.virtual_teacher.llm_service import build_llm_service


class HomeworkOwnership(Protocol):
    def list_for_learner(self, learner_id: int) -> tuple[Any, ...]: ...

    def _owned(self, learner_id: int, homework_id: int) -> Any: ...


class StudentGuidanceService:
    def __init__(
        self,
        *,
        experience: LearnerExperienceService,
        homework: HomeworkService,
        pi_dashboard: PedagogicalDashboardService | None = None,
        vt_repository: DuckDBVirtualTeacherRepository | None = None,
        orchestrator: AIConversationOrchestrator | None = None,
        coach: DeterministicCoachService | None = None,
    ) -> None:
        self.experience = experience
        self.homework = homework
        self.pi_dashboard = pi_dashboard
        self.vt_repository = vt_repository or DuckDBVirtualTeacherRepository()
        self.orchestrator = orchestrator or AIConversationOrchestrator(llm=build_llm_service())
        self.coach = coach or DeterministicCoachService()
        self.recommendations = PedagogicalRecommendationService()

    def _authorize_student(self, actor: dict[str, Any], learner_id: int) -> AIAvailability:
        if normalize_auth_role(actor.get("role")) is AuthRole.STUDENT:
            student_learner_id = actor.get("resolved_learner_id", learner_id)
            if student_learner_id is None or int(student_learner_id) != int(learner_id):
                raise PermissionError("CROSS_LEARNER_ACCESS_DENIED")
        return resolve_ai_availability(learner_id=learner_id, repository=self.vt_repository)

    def build_home_context(self, learner_id: int) -> StudentHomeContext:
        dashboard = self.experience.dashboard(learner_id)
        return self._context_from_dashboard(learner_id, dashboard)

    def find_homework_id_for_session(self, learner_id: int, session_id: int) -> int | None:
        for item in self.homework.list_for_learner(learner_id):
            if item.session_id is not None and int(item.session_id) == int(session_id):
                return int(item.homework_id)
        return None

    def explain_session_result(
        self,
        actor: dict[str, Any],
        learner_id: int,
        session_id: int,
    ) -> ResultExplanationContext | None:
        homework_id = self.find_homework_id_for_session(learner_id, session_id)
        if homework_id is None:
            summary = self.experience.session_summary(learner_id, session_id)
            coach_items = self.coach.advice(self.experience.dashboard(learner_id).mastery)
            return ResultExplanationContext(
                homework_id=0,
                subject_label="Séance",
                score_summary=f"Séance terminée — score {summary.session.score:.0f} %.",
                strengths=summary.strengths or ("Participation enregistrée",),
                weaknesses=summary.weaknesses or ("Points à consolider",),
                deterministic_recommendation=summary.recommendation or (
                    coach_items[0].expected_benefit if coach_items else "Revoir les activités difficiles."
                ),
            )
        return self.explain_homework_result(actor, learner_id, homework_id)

    def build_home_guidance(self, actor: dict[str, Any], learner_id: int) -> StudentDashboardSnapshot:
        availability = self._authorize_student(actor, learner_id)
        context = self.build_home_context(learner_id)
        welcome = self._welcome_for_context(context, availability)
        return self._snapshot(context, welcome, availability)

    def build_dashboard_snapshot(self, actor: dict[str, Any], learner_id: int) -> StudentDashboardSnapshot:
        return self.build_home_guidance(actor, learner_id)

    def prepare_homework_guidance(
        self,
        actor: dict[str, Any],
        learner_id: int,
        homework_id: int,
    ) -> HomeworkGuidanceContext:
        self._authorize_student(actor, learner_id)
        item = self.homework._owned(learner_id, homework_id)
        return HomeworkGuidanceContext(
            homework_id=int(item.homework_id),
            subject_label=str(item.subject_label),
            objective=f"Réaliser {item.exercise_count} exercice(s) en {item.subject_label}",
            estimated_minutes=item.target_duration_minutes,
            exercise_count=int(item.exercise_count),
            status=str(item.status.value),
            advice_before=homework_before(str(item.subject_label), int(item.exercise_count), item.target_duration_minutes),
        )

    def guide_current_exercise(
        self,
        actor: dict[str, Any],
        learner_id: int,
        session_id: int,
        exercise_id: int,
        help_level: int,
    ) -> HomeworkGuidanceResponse:
        availability = self._authorize_student(actor, learner_id)
        _ = session_id, exercise_id
        response = homework_during(help_level)
        if availability.mode is AIAvailabilityMode.ACTIVE:
            try:
                ai = self._generate_short_guidance(
                    learner_id=learner_id,
                    user_message=f"L'élève demande de l'aide niveau {help_level} sur un exercice en cours.",
                    subject_label="devoir",
                )
                return HomeworkGuidanceResponse(
                    source=GuidanceSource.AI,
                    phase="DURING",
                    message=ai,
                    help_level=help_level,
                    suggested_actions=response.suggested_actions,
                )
            except Exception:
                pass
        degraded = availability.mode is AIAvailabilityMode.UNAVAILABLE
        fallback = homework_during(help_level)
        return HomeworkGuidanceResponse(
            source=GuidanceSource.DETERMINISTIC,
            phase=fallback.phase,
            message=fallback.message,
            help_level=fallback.help_level,
            suggested_actions=fallback.suggested_actions,
            degraded_notice=fallback.degraded_notice if degraded else "",
        )

    def explain_homework_result(
        self,
        actor: dict[str, Any],
        learner_id: int,
        homework_id: int,
    ) -> ResultExplanationContext:
        availability = self._authorize_student(actor, learner_id)
        item = self.homework._owned(learner_id, homework_id)
        dashboard = self.experience.dashboard(learner_id)
        coach_items = self.coach.advice(dashboard.mastery)
        strengths = tuple(item.title for item in coach_items if "Progression" in item.title or "solide" in item.title.lower())[:3]
        weaknesses = tuple(item.title for item in coach_items if "Priorité" in item.title)[:3]
        recommendation = coach_items[0].expected_benefit if coach_items else "Revoir les exercices difficiles avec une séance courte."
        context = ResultExplanationContext(
            homework_id=int(item.homework_id),
            subject_label=str(item.subject_label),
            score_summary=f"Devoir {item.subject_label} — statut {item.status.value}.",
            strengths=strengths or ("Participation enregistrée",),
            weaknesses=weaknesses or ("Consolider les notions abordées",),
            deterministic_recommendation=str(recommendation),
        )
        if availability.mode is AIAvailabilityMode.ACTIVE:
            try:
                narrative = self._generate_short_guidance(
                    learner_id=learner_id,
                    user_message=explain_result(context),
                    subject_label=str(item.subject_label),
                )
                context = ResultExplanationContext(
                    homework_id=context.homework_id,
                    subject_label=context.subject_label,
                    score_summary=narrative,
                    strengths=context.strengths,
                    weaknesses=context.weaknesses,
                    deterministic_recommendation=context.deterministic_recommendation,
                )
            except Exception:
                pass
        return context

    def recommend_revision(self, actor: dict[str, Any], learner_id: int) -> RevisionGuidanceContext:
        availability = self._authorize_student(actor, learner_id)
        context = self.build_home_context(learner_id)
        priority = context.revision_priorities[0] if context.revision_priorities else RevisionPriority(
            subject_label="Général",
            skill_label="Première activité",
            reason="Aucune donnée suffisante — lance un diagnostic court.",
            priority=1,
            estimated_minutes=10,
            action_label="Ouvrir une révision",
        )
        message = (
            f"Je te propose de travailler {priority.skill_label} en {priority.subject_label}. "
            f"Raison : {priority.reason}. Durée estimée : {priority.estimated_minutes} min."
        )
        if availability.mode is AIAvailabilityMode.ACTIVE:
            try:
                message = self._generate_short_guidance(
                    learner_id=learner_id,
                    user_message=f"Propose une révision : {message}",
                    subject_label=priority.subject_label,
                )
                return revision_guidance(priority, source=GuidanceSource.AI, message=message, degraded=False)
            except Exception:
                pass
        return revision_guidance(
            priority,
            source=GuidanceSource.DETERMINISTIC,
            message=message,
            degraded=availability.mode is AIAvailabilityMode.UNAVAILABLE,
        )

    def _context_from_dashboard(self, learner_id: int, dashboard: StudentDashboard) -> StudentHomeContext:
        mastery = tuple(self._mastery_item(item) for item in dashboard.mastery)
        fragile = tuple(item for item in mastery if item.band in {MasteryBand.FRAGILE, MasteryBand.TO_REVISE})
        strong = tuple(item for item in mastery if item.band in {MasteryBand.VERY_HIGH, MasteryBand.HIGH})
        homework_items = self.homework.list_for_learner(learner_id)
        now = datetime.now(UTC)
        summaries = tuple(self._homework_summary(item) for item in homework_items)
        overdue = tuple(
            item
            for item in summaries
            if item.due_at is not None
            and item.due_at < now
            and item.status not in {AssignmentStatus.COMPLETED.value, AssignmentStatus.CANCELLED.value}
        )
        todo = tuple(
            item
            for item in summaries
            if item.status in {AssignmentStatus.READY.value, AssignmentStatus.IN_PROGRESS.value, AssignmentStatus.PAUSED.value}
        )
        recent = tuple(
            item for item in summaries if item.status == AssignmentStatus.COMPLETED.value
        )[:3]
        priorities = self._revision_priorities(mastery, todo)
        recent_score = dashboard.metrics[0].value if dashboard.metrics else None
        success_metric = next((metric.value for metric in dashboard.metrics if "réussite" in metric.label.lower()), None)
        return StudentHomeContext(
            learner_id=learner_id,
            display_name=dashboard.display_name,
            homework_todo=todo,
            homework_overdue=overdue,
            homework_recent=recent,
            mastery=mastery,
            fragile_skills=fragile,
            strong_skills=strong,
            revision_priorities=priorities,
            recent_score=recent_score,
            success_rate=success_metric,
            objective=dashboard.objective,
            next_revision=dashboard.next_revision,
        )

    def _mastery_item(self, item: MasteryView) -> MasterySnapshotItem:
        band = classify_mastery_band(score=float(item.score), level=str(item.level), trend=str(item.trend))
        return MasterySnapshotItem(
            skill_id=int(item.skill_id),
            label=str(item.label),
            score=float(item.score),
            level=str(item.level),
            trend=str(item.trend),
            band=band,
            band_label=band_label(band),
        )

    @staticmethod
    def _homework_summary(item: Any) -> HomeworkSummaryItem:
        return HomeworkSummaryItem(
            homework_id=int(item.homework_id),
            subject_label=str(item.subject_label),
            status=str(item.status.value),
            due_at=item.due_at,
            exercise_count=int(item.exercise_count),
            target_duration_minutes=item.target_duration_minutes,
        )

    def _revision_priorities(
        self,
        mastery: tuple[MasterySnapshotItem, ...],
        todo: tuple[HomeworkSummaryItem, ...],
    ) -> tuple[RevisionPriority, ...]:
        priorities: list[RevisionPriority] = []
        if todo:
            hw = todo[0]
            priorities.append(
                RevisionPriority(
                    subject_label=hw.subject_label,
                    skill_label=f"Devoir {hw.subject_label}",
                    reason="Devoir planifié ou en cours",
                    priority=1,
                    estimated_minutes=hw.target_duration_minutes or 20,
                    action_label="Ouvrir le devoir",
                    homework_id=hw.homework_id,
                )
            )
        for item in mastery:
            if item.band not in {MasteryBand.FRAGILE, MasteryBand.TO_REVISE}:
                continue
            priorities.append(
                RevisionPriority(
                    subject_label="Compétence",
                    skill_label=item.label,
                    reason=f"Maîtrise {item.score:.0f} % — {item.band_label}",
                    priority=2 if item.band is MasteryBand.TO_REVISE else 3,
                    estimated_minutes=15,
                    action_label="Lancer une révision",
                    skill_id=item.skill_id,
                )
            )
        priorities.sort(key=lambda row: row.priority)
        return tuple(priorities[:5])

    def _welcome_for_context(self, context: StudentHomeContext, availability: AIAvailability) -> WelcomeGuidance:
        if availability.mode is AIAvailabilityMode.ACTIVE:
            try:
                facts = (
                    f"Élève {context.display_name}. Objectif: {context.objective}. "
                    f"Devoirs à faire: {len(context.homework_todo)}. "
                    f"Devoirs en retard: {len(context.homework_overdue)}. "
                    f"Compétence fragile: {context.fragile_skills[0].label if context.fragile_skills else 'aucune'}."
                )
                message = self._generate_short_guidance(
                    learner_id=context.learner_id,
                    user_message=f"Accueil élève. Faits: {facts}. Propose une priorité et deux actions courtes en français.",
                    subject_label="accueil",
                    display_name=context.display_name,
                )
                return build_ai_welcome(context, message)
            except Exception:
                pass
        degraded = availability.mode is AIAvailabilityMode.UNAVAILABLE
        return build_deterministic_welcome(context, degraded=degraded)

    def _generate_short_guidance(
        self,
        *,
        learner_id: int,
        user_message: str,
        subject_label: str,
        display_name: str = "Élève",
    ) -> str:
        preferences = self.vt_repository.ensure_preferences(learner_id)
        context = PedagogicalContext(
            learner_id=learner_id,
            learner_display_name=display_name,
            grade_label=None,
            subject_label=subject_label,
        )
        request = ConversationRequest(
            learner_id=learner_id,
            actor_type="STUDENT",
            actor_ref=str(learner_id),
            session_id=None,
            user_message=user_message,
            context=context,
        )
        response = self.orchestrator.generate_answer(request=request, preferences=preferences, history=())
        return str(response.message)

    def _snapshot(
        self,
        context: StudentHomeContext,
        welcome: WelcomeGuidance,
        availability: AIAvailability,
    ) -> StudentDashboardSnapshot:
        grouped: dict[str, list[MasterySnapshotItem]] = defaultdict(list)
        for item in context.mastery:
            grouped[item.band.value].append(item)
        return StudentDashboardSnapshot(
            context=context,
            welcome=welcome,
            availability=availability,
            mastery_by_band={key: tuple(values) for key, values in grouped.items()},
            recommendations=context.revision_priorities,
        )
