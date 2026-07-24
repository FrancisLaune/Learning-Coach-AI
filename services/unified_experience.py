"""Application services composing existing deterministic V2 capabilities."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol

from domain.onboarding.models import OnboardingRequest, OnboardingResult
from domain.unified_experience.models import (
    AssignmentStatus,
    CoachAdvice,
    HomeworkAssignment,
    HomeworkRequest,
    LearnerManagementProfile,
    ProgrammeChange,
)


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
    def create_homework(self, request: HomeworkRequest, content_ids: tuple[int, ...]) -> HomeworkAssignment: ...
    def create_homework_proposal(self, homework_id: int) -> int: ...
    def link_homework_session(self, homework_id: int, session_id: int) -> None: ...
    def list_homework(self, learner_id: int) -> tuple[HomeworkAssignment, ...]: ...
    def update_homework_status(
        self, homework_id: int, learner_id: int, current: AssignmentStatus, target: AssignmentStatus
    ) -> HomeworkAssignment: ...
    def parent_authorized(self, parent_ref: str, learner_id: int) -> bool: ...
    def learner_management_profile(self, learner_id: int) -> LearnerManagementProfile: ...
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
    def __init__(self, repository: UnifiedExperienceRepository) -> None:
        self.repository = repository

    def create(self, request: HomeworkRequest) -> HomeworkAssignment:
        content_ids = self.repository.select_approved_content(request)
        if not content_ids:
            raise ValueError("Aucun contenu Approved ne correspond à cette sélection.")
        return self.repository.create_homework(request, content_ids)

    def assign_as_parent(self, parent_ref: str, request: HomeworkRequest) -> HomeworkAssignment:
        if request.assigned_by_type != "PARENT" or request.assigned_by_ref != parent_ref:
            raise PermissionError("PARENT_ASSIGNMENT_CONTEXT_INVALID")
        if not self.repository.parent_authorized(parent_ref, request.learner_id):
            raise PermissionError("PARENT_ACCESS_DENIED")
        return self.create(request)

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
        if profile.email is not None and ("@" not in profile.email or "." not in profile.email.rsplit("@", 1)[-1]):
            raise ValueError("L'adresse e-mail de l'élève n'est pas valide.")
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
            profile.email.strip().lower() if profile.email else None,
        )


class LearnerProfileManagementService:
    def __init__(self, repository: UnifiedExperienceRepository) -> None:
        self.repository = repository

    def get(self, parent_ref: str, learner_id: int) -> LearnerManagementProfile:
        self._authorize(parent_ref, learner_id)
        return self.repository.learner_management_profile(learner_id)

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
        if not profile.email:
            raise ValueError("L'adresse e-mail de l'élève est obligatoire.")
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

    def reset_diagnostic(self, parent_ref: str, learner_id: int) -> None:
        self._authorize(parent_ref, learner_id)
        self.repository.reset_diagnostic(parent_ref, learner_id)

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
