"""Application services composing existing deterministic V2 capabilities."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol

from domain.onboarding.models import OnboardingRequest, OnboardingResult
from domain.unified_experience.models import (
    AssignmentStatus,
    AssignmentType,
    CoachAdvice,
    HomeworkAssignment,
    HomeworkContentSelection,
    HomeworkGenerationResult,
    HomeworkRequest,
    LearnerManagementProfile,
    ProgrammeChange,
)
from services.homework.ai_fallback import HomeworkAiFallbackOrchestrator
from services.homework.config import HomeworkAiCompletionSettings
from services.homework.eligibility import completion_flags_enabled, is_homework_ai_completion_eligible
from services.platform_runtime import FeatureFlagService, default_flags


class UnifiedExperienceRepository(Protocol):
    def learner_for_external_ref(self, external_ref: str) -> int | None: ...
    def onboarding_complete(self, learner_id: int) -> bool: ...
    def grade_levels(self) -> tuple[tuple[int, str, str], ...]: ...
    def reference_subjects(self) -> tuple[tuple[int, str, str], ...]: ...
    def learner_grade_id(self, learner_id: int) -> int: ...
    def subjects_for_grade(self, grade_level_id: int) -> tuple[tuple[int, str, str], ...]: ...
    def chapters(self, subject_id: int, grade_level_id: int | None = None) -> tuple[tuple[int, str], ...]: ...
    def skills(
        self,
        subject_id: int,
        chapter_ids: tuple[int, ...] = (),
        grade_level_id: int | None = None,
    ) -> tuple[tuple[int, str], ...]: ...
    def select_approved_content(self, request: HomeworkRequest) -> tuple[int, ...]: ...
    def select_approved_content_detailed(self, request: HomeworkRequest) -> HomeworkContentSelection: ...
    def count_eligible_content(
        self, request: HomeworkRequest, *, difficulty: int | None = None
    ) -> int: ...
    def create_homework(self, request: HomeworkRequest, content_ids: tuple[int, ...]) -> HomeworkAssignment: ...
    def persist_homework_runtime_exercises(
        self,
        homework_id: int,
        learner_id: int,
        exercises: tuple[object, ...],
        *,
        start_position: int = 1,
    ) -> tuple[int, ...]: ...
    def is_four_e_grade(self, grade_level_id: int | None) -> bool: ...

    def grade_code(self, grade_level_id: int | None) -> str | None: ...

    def subject_code(self, subject_id: int) -> str | None: ...
    def create_homework_proposal(self, homework_id: int) -> int: ...
    def link_homework_session(self, homework_id: int, session_id: int) -> None: ...
    def list_homework(self, learner_id: int) -> tuple[HomeworkAssignment, ...]: ...
    def rollback_homework_creation(self, homework_id: int, learner_id: int) -> None: ...
    def update_homework_status(
        self, homework_id: int, learner_id: int, current: AssignmentStatus, target: AssignmentStatus
    ) -> HomeworkAssignment: ...
    def parent_authorized(self, parent_ref: str, learner_id: int) -> bool: ...
    def list_linked_learners(self, parent_ref: str, *, archived: bool = False) -> tuple[tuple[int, str], ...]: ...
    def learner_is_archived(self, learner_id: int) -> bool: ...
    def learner_last_activity_label(self, learner_id: int) -> str | None: ...
    def archive_learner(self, parent_ref: str, learner_id: int) -> None: ...
    def restore_learner(self, parent_ref: str, learner_id: int) -> None: ...
    def learner_management_profile(
        self, learner_id: int, *, include_archived: bool = False
    ) -> LearnerManagementProfile: ...
    def link_parent(self, parent_ref: str, learner_id: int) -> None: ...
    def reset_diagnostic(self, parent_ref: str, learner_id: int) -> None: ...
    def delete_learner(self, parent_ref: str, learner_id: int) -> None: ...
    def save_experience_profile(
        self,
        learner_id: int,
        first_name: str,
        last_name: str | None,
        birth_date: date | None,
        school_year: str,
        programme_code: str,
        preferred_formats: tuple[str, ...],
        error_help_preference: str,
        diagnostic_status: str,
        email: str | None = None,
    ) -> None: ...
    def programme_changes(self, learner_id: int) -> tuple[ProgrammeChange, ...]: ...
    def decide_programme_change(
        self, proposal_id: int, parent_ref: str, decision: str, note: str | None = None
    ) -> None: ...


class MasteryAdviceItem(Protocol):
    @property
    def skill_id(self) -> int: ...
    @property
    def label(self) -> str: ...
    @property
    def score(self) -> float: ...
    @property
    def trend(self) -> str: ...


class HomeworkService:
    def __init__(
        self,
        repository: UnifiedExperienceRepository,
        *,
        feature_flags: FeatureFlagService | None = None,
        ai_fallback: HomeworkAiFallbackOrchestrator | None = None,
    ) -> None:
        self.repository = repository
        self._feature_flags = feature_flags or default_flags()
        self._ai_fallback = ai_fallback

    def preview_selection(self, request: HomeworkRequest) -> HomeworkContentSelection:
        detailed = self.repository.select_approved_content_detailed(request)
        return detailed

    def create(self, request: HomeworkRequest) -> HomeworkAssignment:
        if self._should_use_ai_fallback(request):
            return self.create_with_diagnostics(request).homework
        selection = self.repository.select_approved_content_detailed(request)
        if not selection.content_ids:
            raise ValueError(self._empty_selection_message(request))
        return self.repository.create_homework(request, selection.content_ids)

    def create_with_diagnostics(self, request: HomeworkRequest) -> HomeworkGenerationResult:
        if not self._should_use_ai_fallback(request):
            selection = self.repository.select_approved_content_detailed(request)
            if not selection.content_ids:
                raise ValueError(self._empty_selection_message(request))
            homework = self.repository.create_homework(request, selection.content_ids)
            return HomeworkGenerationResult(
                homework,
                request.exercise_count,
                len(selection.content_ids),
                0,
                0,
                len(selection.content_ids),
                len(selection.content_ids) < request.exercise_count,
                "PARTIAL_CATALOG" if len(selection.content_ids) < request.exercise_count else None,
                "",
            )
        if self._ai_fallback is None:
            raise ValueError("HOMEWORK_AI_FALLBACK_NOT_CONFIGURED")
        return self._ai_fallback.generate(request)

    def supports_ai_completion(self) -> bool:
        return self._ai_fallback is not None and completion_flags_enabled(self._feature_flags)

    def supports_ai_fallback(self) -> bool:
        return self.supports_ai_completion()

    def _should_use_ai_fallback(self, request: HomeworkRequest) -> bool:
        return is_homework_ai_completion_eligible(
            request,
            self.repository,
            flags=self._feature_flags,
            settings=HomeworkAiCompletionSettings.from_environment(),
            orchestrator_configured=self._ai_fallback is not None,
        )

    @staticmethod
    def _empty_selection_message(request: HomeworkRequest) -> str:
        subject_hint = "cette matière"
        if request.mode is AssignmentType.GLOBAL_SUBJECT:
            return (
                f"Aucun contenu approuvé n'est disponible pour {subject_hint} avec les critères sélectionnés. "
                "Choisissez une autre matière ou attendez la publication de nouveaux contenus validés."
            )
        return (
            "Aucun contenu approuvé ne correspond à cette sélection de chapitres ou compétences. "
            "Élargissez la sélection ou choisissez un devoir global."
        )

    def assign_as_parent(self, parent_ref: str, request: HomeworkRequest) -> HomeworkAssignment:
        if request.assigned_by_type != "PARENT" or request.assigned_by_ref != parent_ref:
            raise PermissionError("PARENT_ASSIGNMENT_CONTEXT_INVALID")
        if not self.repository.parent_authorized(parent_ref, request.learner_id):
            raise PermissionError("PARENT_ACCESS_DENIED")
        return self.create(request)

    def assign_as_parent_with_diagnostics(self, parent_ref: str, request: HomeworkRequest) -> HomeworkGenerationResult:
        if request.assigned_by_type != "PARENT" or request.assigned_by_ref != parent_ref:
            raise PermissionError("PARENT_ASSIGNMENT_CONTEXT_INVALID")
        if not self.repository.parent_authorized(parent_ref, request.learner_id):
            raise PermissionError("PARENT_ACCESS_DENIED")
        return self.create_with_diagnostics(request)

    def list_for_learner(self, learner_id: int) -> tuple[HomeworkAssignment, ...]:
        return self.repository.list_homework(learner_id)

    def start(self, learner_id: int, homework_id: int) -> HomeworkAssignment:
        item = self._owned(learner_id, homework_id)
        return self.repository.update_homework_status(
            homework_id, learner_id, item.status, AssignmentStatus.IN_PROGRESS
        )

    def pause(self, learner_id: int, homework_id: int) -> HomeworkAssignment:
        item = self._owned(learner_id, homework_id)
        return self.repository.update_homework_status(homework_id, learner_id, item.status, AssignmentStatus.PAUSED)

    def resume(self, learner_id: int, homework_id: int) -> HomeworkAssignment:
        item = self._owned(learner_id, homework_id)
        return self.repository.update_homework_status(
            homework_id, learner_id, item.status, AssignmentStatus.IN_PROGRESS
        )

    def _owned(self, learner_id: int, homework_id: int) -> HomeworkAssignment:
        item = next(
            (
                candidate
                for candidate in self.repository.list_homework(learner_id)
                if candidate.homework_id == homework_id
            ),
            None,
        )
        if item is None:
            raise PermissionError("HOMEWORK_ACCESS_DENIED")
        return item


class SessionCreator(Protocol):
    def create_session(self, proposal_id: int, now: datetime) -> Any: ...


class HomeworkSessionService:
    def __init__(self, repository: UnifiedExperienceRepository, sessions: SessionCreator) -> None:
        self.repository = repository
        self.sessions = sessions

    def materialize(self, learner_id: int, homework_id: int, now: datetime) -> HomeworkAssignment:
        item = next(
            (
                candidate
                for candidate in self.repository.list_homework(learner_id)
                if candidate.homework_id == homework_id
            ),
            None,
        )
        if item is None:
            raise PermissionError("HOMEWORK_ACCESS_DENIED")
        if item.session_id is not None:
            return item
        proposal_id = self.repository.create_homework_proposal(homework_id)
        session = self.sessions.create_session(proposal_id, now)
        session_id = int(session.session_id)
        self.repository.link_homework_session(homework_id, session_id)
        return next(
            candidate for candidate in self.repository.list_homework(learner_id) if candidate.homework_id == homework_id
        )

    def open_for_learner(self, learner_id: int, homework_id: int, now: datetime) -> HomeworkAssignment:
        item = self.materialize(learner_id, homework_id, now)
        if item.session_id is None:
            raise ValueError("HOMEWORK_SESSION_NOT_MATERIALIZED")
        self.sessions.ensure_running(int(item.session_id), now)
        return item


@dataclass(frozen=True, slots=True)
class OnboardingProfileInput:
    learner_id: int
    first_name: str
    last_name: str | None
    birth_date: date | None
    school_year: str
    programme_code: str
    preferred_formats: tuple[str, ...]
    error_help_preference: str
    take_diagnostic: bool
    email: str | None = None

    @property
    def age(self) -> int | None:
        if self.birth_date is None:
            return None
        today = date.today()
        return (
            today.year
            - self.birth_date.year
            - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        )


class UnifiedOnboardingProfileService:
    def __init__(self, repository: UnifiedExperienceRepository) -> None:
        self.repository = repository

    def save(self, profile: OnboardingProfileInput) -> None:
        if not profile.first_name.strip():
            raise ValueError("Le prénom est obligatoire.")
        if profile.age is not None and not 5 <= profile.age <= 30:
            raise ValueError("La date de naissance n'est pas compatible avec un profil scolaire.")
        if profile.email is not None:
            normalized_email = profile.email.strip()
            if normalized_email and ("@" not in normalized_email or "." not in normalized_email.rsplit("@", 1)[-1]):
                raise ValueError("L'adresse e-mail de l'élève n'est pas valide.")
        else:
            normalized_email = None
        self.repository.save_experience_profile(
            profile.learner_id,
            profile.first_name.strip(),
            profile.last_name.strip() if profile.last_name else None,
            profile.birth_date,
            profile.school_year,
            profile.programme_code,
            profile.preferred_formats,
            profile.error_help_preference,
            "PLANNED" if profile.take_diagnostic else "SKIPPED",
            normalized_email.lower() if normalized_email else None,
        )


class LearnerProfileManagementService:
    def __init__(self, repository: UnifiedExperienceRepository) -> None:
        self.repository = repository

    def get(self, parent_ref: str, learner_id: int, *, include_archived: bool = False) -> LearnerManagementProfile:
        self._authorize(parent_ref, learner_id)
        return self.repository.learner_management_profile(learner_id, include_archived=include_archived)

    def reset_diagnostic(self, parent_ref: str, learner_id: int) -> None:
        self._authorize(parent_ref, learner_id)
        self.repository.reset_diagnostic(parent_ref, learner_id)

    def archive(self, parent_ref: str, learner_id: int) -> None:
        self._authorize(parent_ref, learner_id)
        if self.repository.learner_is_archived(learner_id):
            return
        self.repository.archive_learner(parent_ref, learner_id)

    def restore(self, parent_ref: str, learner_id: int) -> None:
        self._authorize(parent_ref, learner_id)
        if not self.repository.learner_is_archived(learner_id):
            return
        self.repository.restore_learner(parent_ref, learner_id)

    def list_active(self, parent_ref: str) -> tuple[tuple[int, str], ...]:
        return self.repository.list_linked_learners(parent_ref, archived=False)

    def list_archived(self, parent_ref: str) -> tuple[tuple[int, str], ...]:
        return self.repository.list_linked_learners(parent_ref, archived=True)

    def create(
        self,
        parent_ref: str,
        request: OnboardingRequest,
        profile: OnboardingProfileInput,
        onboarding: OnboardingCompleter,
        profiles: ProfileWriter,
    ) -> OnboardingResult:
        if request.changed_by_role.value != "parent":
            raise ValueError("PARENT_CREATION_CONTEXT_INVALID")
        result = onboarding.complete(request)
        if profile.learner_id not in {0, result.learner_id}:
            raise ValueError("LEARNER_PROFILE_CONTEXT_INVALID")
        profiles.save(
            OnboardingProfileInput(
                result.learner_id,
                profile.first_name,
                profile.last_name,
                profile.birth_date,
                profile.school_year,
                profile.programme_code,
                profile.preferred_formats,
                profile.error_help_preference,
                profile.take_diagnostic,
                profile.email,
            )
        )
        self.repository.link_parent(parent_ref, result.learner_id)
        return result

    def update(
        self,
        parent_ref: str,
        request: OnboardingRequest,
        profile: OnboardingProfileInput,
        onboarding: OnboardingCompleter,
        profiles: ProfileWriter,
    ) -> OnboardingResult:
        learner_id = request.profile.learner_id
        if learner_id is None or learner_id != profile.learner_id:
            raise ValueError("LEARNER_PROFILE_CONTEXT_INVALID")
        self._authorize(parent_ref, learner_id)
        result = onboarding.complete(request)
        profiles.save(profile)
        return result

    def delete(self, parent_ref: str, learner_id: int, confirmation: str, understood: bool) -> None:
        profile = self.get(parent_ref, learner_id)
        if not understood:
            raise ValueError("Confirmez que vous comprenez que la suppression est définitive.")
        if confirmation.strip() != profile.first_name:
            raise ValueError("Le prénom saisi ne correspond pas.")
        self.repository.delete_learner(parent_ref, learner_id)

    def _authorize(self, parent_ref: str, learner_id: int) -> None:
        if not self.repository.parent_authorized(parent_ref, learner_id):
            raise PermissionError("PARENT_ACCESS_DENIED")


class OnboardingCompleter(Protocol):
    def complete(self, request: OnboardingRequest) -> OnboardingResult: ...


class ProfileWriter(Protocol):
    def save(self, profile: OnboardingProfileInput) -> None: ...


class ProgrammeChangeService:
    def __init__(self, repository: UnifiedExperienceRepository) -> None:
        self.repository = repository

    def list_for_parent(self, parent_ref: str, learner_id: int) -> tuple[ProgrammeChange, ...]:
        if not self.repository.parent_authorized(parent_ref, learner_id):
            raise PermissionError("PARENT_ACCESS_DENIED")
        return self.repository.programme_changes(learner_id)

    def decide(self, parent_ref: str, proposal_id: int, decision: str, note: str | None = None) -> None:
        self.repository.decide_programme_change(proposal_id, parent_ref, decision, note)


class DeterministicCoachService:
    """Turns existing mastery trends into transparent, non-generative advice."""

    def advice(self, mastery: Sequence[MasteryAdviceItem]) -> tuple[CoachAdvice, ...]:
        advice: list[CoachAdvice] = []
        for item in mastery:
            score = float(item.score)
            trend = str(item.trend)
            label = str(item.label)
            skill_id = int(item.skill_id)
            if score < 50 and trend in {"DECLINING", "STABLE"}:
                advice.append(
                    CoachAdvice(
                        f"Priorité : {label}",
                        f"La maîtrise récente est de {score:.0f} % avec une tendance {trend.lower()}.",
                        ("LOW_MASTERY", f"TREND_{trend}"),
                        (f"skill:{skill_id}",),
                        "Consolider la compétence avec une séance guidée supplémentaire.",
                        1,
                    )
                )
            elif score >= 80 and trend == "IMPROVING":
                advice.append(
                    CoachAdvice(
                        f"Progression solide : {label}",
                        f"La maîtrise atteint {score:.0f} % et continue de progresser.",
                        ("HIGH_MASTERY", "TREND_IMPROVING"),
                        (f"skill:{skill_id}",),
                        "Espacer les révisions et proposer progressivement plus de difficulté.",
                        3,
                    )
                )
        return tuple(sorted(advice, key=lambda item: (item.priority, item.title)))
