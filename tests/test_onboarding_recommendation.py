from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

import pytest

from domain.decision.enums import ActivityKind, ObjectiveKind
from domain.learning.models import AcademicYear, GradeLevel, MasteryState
from domain.onboarding.enums import CreatorRole, DifficultyPreference
from domain.onboarding.models import (
    AvailabilitySlot,
    LearnerGoalConfiguration,
    LearnerProfile,
    OnboardingRequest,
    StudyPreferences,
    SubjectPreference,
)
from domain.onboarding.validators import validate_onboarding
from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.decision import DuckDBDecisionRepository
from infrastructure.repositories.learning import DuckDBLearningRepository
from infrastructure.repositories.onboarding import DuckDBOnboardingRepository
from infrastructure.repositories.recommendation import DuckDBRecommendationRepository
from migrations.runner import apply_migrations
from services.onboarding import OnboardingService
from services.recommendation import ContentCandidateService, PersonalizedSessionService
from services.recommendation.models import ApprovedContent

NOW = datetime(2027, 6, 1, 10, tzinfo=UTC)
FOURTH = GradeLevel("FR-4E", 4, "Quatrième")
THIRD = GradeLevel("FR-3E", 3, "Troisième")


def request(
    objective: ObjectiveKind = ObjectiveKind.REVISION,
    target: GradeLevel | None = None,
    target_date: date | None = date(2027, 9, 1),
    subjects: tuple[int, ...] = (1, 2),
    available: bool = True,
) -> OnboardingRequest:
    return OnboardingRequest(
        "onboard-1",
        LearnerProfile("profile-1", "Alex", CreatorRole.PARENT),
        AcademicYear(2026, 2027),
        FOURTH,
        LearnerGoalConfiguration(
            objective, target, "BREVET" if objective is ObjectiveKind.PREPARATION_BREVET else None, target_date
        ),
        tuple(SubjectPreference(s, priority=True) for s in subjects),
        StudyPreferences(
            30, (AvailabilitySlot(0, 30, time(17)),) if available else (), difficulty=DifficultyPreference.STANDARD
        ),
        CreatorRole.PARENT,
    )


@pytest.mark.parametrize(
    ("objective", "target", "valid"),
    [
        (ObjectiveKind.REVISION, None, True),
        (ObjectiveKind.CATCH_UP, None, True),
        (ObjectiveKind.PREPARATION_NEXT_GRADE, THIRD, True),
        (ObjectiveKind.PREPARATION_NEXT_GRADE, None, False),
        (ObjectiveKind.PREPARATION_BREVET, None, True),
        (ObjectiveKind.PREPARATION_BAC, None, False),
    ],
)
def test_goal_matrix(objective: ObjectiveKind, target: GradeLevel | None, valid: bool) -> None:
    result = validate_onboarding(request(objective, target), {1, 2}, today=date(2027, 1, 1))
    assert result.valid is valid
    if objective is ObjectiveKind.PREPARATION_BREVET:
        assert any(i.code == "ANTICIPATION_GOAL" for i in result.issues)


def test_validation_errors_and_warning() -> None:
    result = validate_onboarding(
        request(target_date=date(2020, 1, 1), subjects=(999,), available=False), {1, 2}, today=date(2027, 1, 1)
    )
    assert {i.code for i in result.issues} >= {"TARGET_DATE_IN_PAST", "UNKNOWN_SUBJECT", "NO_AVAILABILITY"}


def content(
    status: str = "approved",
    grade: str = "FR-4E",
    subject: int = 1,
    minutes: int = 20,
    difficulty: int = 3,
    markers: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    content_id: int = 1,
) -> ApprovedContent:
    return ApprovedContent(
        content_id,
        100 + content_id,
        f"Content {content_id}",
        subject,
        101,
        10001,
        None,
        1,
        grade,
        difficulty,
        minutes,
        ActivityKind.LEARNING,
        (),
        tags,
        status,
        status != "archived",
        ("revision", "preparation_next_grade", "preparation_brevet"),
        (),
        markers,
    )


@pytest.mark.parametrize("status", ["draft", "review", "archived"])
def test_non_approved_excluded(status: str) -> None:
    result = ContentCandidateService().build(make_onboarding().journey, (content(status=status),), {}, NOW)
    assert result.report.exclusions[0].reason == "NOT_APPROVED"


def test_filter_pipeline_and_inter_grade_rules() -> None:
    journey = make_onboarding(ObjectiveKind.PREPARATION_NEXT_GRADE, THIRD).journey
    contents = (
        content(grade="FR-3E", content_id=1),
        content(grade="FR-3E", markers=("introductory",), content_id=2),
        content(subject=9, content_id=3),
        content(minutes=90, content_id=4),
        content(difficulty=9, content_id=5),
        content(grade="FR-5E", tags=("remediation",), content_id=6),
    )
    result = ContentCandidateService().build(journey, contents, {}, NOW, {1, 2})
    assert {c.content_id for c in result.candidates} == {2, 6}
    assert (result.report.initial_count, result.report.retained_count, result.report.excluded_count) == (6, 2, 4)


def test_candidate_stability_and_learning_signal() -> None:
    onboarding = make_onboarding()
    state = MasteryState(1, 10001, 0.5, observations=3, confidence=0.7)
    first = ContentCandidateService().build(onboarding.journey, (content(),), {10001: state}, NOW)
    second = ContentCandidateService().build(onboarding.journey, (content(),), {10001: state}, NOW)
    assert first.candidates[0].stable_id == second.candidates[0].stable_id and first.candidates[0].mastery is state


class MemoryRepo:
    def known_subject_ids(self) -> set[int]:
        return {1, 2}

    def complete(self, request: OnboardingRequest, result: Any, events: Any) -> Any:
        return replace(result, learner_id=1, journey=replace(result.journey, learner_id=1))


def make_onboarding(objective: ObjectiveKind = ObjectiveKind.REVISION, target: GradeLevel | None = None) -> Any:
    return OnboardingService(MemoryRepo()).complete(request(objective, target), NOW)


def test_session_budget_explanation_absence_determinism() -> None:
    onboarding = make_onboarding()
    service = PersonalizedSessionService()
    contents = (content(content_id=1), content(content_id=2, minutes=15))
    first = service.generate(onboarding, contents, NOW)
    second = service.generate(onboarding, contents, NOW)
    assert (
        sum(i.duration_minutes for i in first.activities) <= 30
        and first.stable_id == second.stable_id
        and first.summary_reasons
    )
    empty = service.generate(onboarding, (), NOW)
    assert empty.absence_code == "NO_APPROVED_CONTENT" and not empty.activities


@pytest.fixture
def v2(tmp_path: Path) -> Path:
    path = tmp_path / "onboarding.duckdb"
    apply_migrations(path)
    return path


def test_persistence_and_idempotence(v2: Path) -> None:
    service = OnboardingService(DuckDBOnboardingRepository(v2))
    first = service.complete(request(), NOW)
    again = service.complete(request(), NOW)
    assert first.learner_id == again.learner_id and again.journey_version == 1
    sessions = PersonalizedSessionService(
        decision_repository=DuckDBDecisionRepository(v2),
        learning_repository=DuckDBLearningRepository(v2),
        session_repository=DuckDBRecommendationRepository(v2),
    )
    proposal = sessions.generate(first, (content(),), NOW)
    proposal2 = sessions.generate(first, (content(),), NOW)
    assert proposal.stable_id == proposal2.stable_id
    con = connect_v2(v2, read_only=True)
    try:
        assert con.execute("SELECT count(*) FROM learners").fetchone() == (1,)
        assert con.execute("SELECT count(*) FROM onboarding_sessions").fetchone() == (1,)
        assert con.execute("SELECT count(*) FROM learner_journey_versions").fetchone() == (1,)
        assert con.execute("SELECT count(*) FROM personalized_session_proposals").fetchone() == (1,)
    finally:
        con.close()
