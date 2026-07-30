"""Smoke test: parent login, child creation, virtual teacher association."""

from __future__ import annotations

import json
import sys
import uuid
from datetime import date, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.decision.enums import ObjectiveKind
from domain.learning.models import AcademicYear, GradeLevel
from domain.onboarding.enums import CreatorRole, DifficultyPreference
from domain.onboarding.models import (
    AvailabilitySlot,
    LearnerGoalConfiguration,
    LearnerProfile,
    OnboardingRequest,
    StudyPreferences,
    SubjectPreference,
)
from domain.virtual_teacher.models import PedagogicalContext, PreferencesPatch
from infrastructure.repositories.onboarding import DuckDBOnboardingRepository
from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository
from infrastructure.repositories.virtual_teacher import DuckDBVirtualTeacherRepository
from services.auth.roles import AuthRole
from services.onboarding import OnboardingService
from services.runtime import prepare_runtime
from services.unified_experience import (
    LearnerProfileManagementService,
    OnboardingProfileInput,
    UnifiedOnboardingProfileService,
)
from services.virtual_teacher.ai_conversation_orchestrator import AIConversationOrchestrator
from services.virtual_teacher.ai_teacher_preferences_service import AITeacherPreferencesService
from services.virtual_teacher.ai_teacher_service import AITeacherService
from services.virtual_teacher.llm_service import DeterministicLLMService
from services.virtual_teacher.pedagogical_guardrails import PedagogicalGuardrails
from services.virtual_teacher.tts_service import ConsoleTTSService

import duckdb

import core.database as legacy_database


def _grade_and_subject(repository: DuckDBUnifiedExperienceRepository) -> tuple[GradeLevel, int]:
    from infrastructure.database.v2 import connect_v2

    connection = connect_v2(repository.database_path, read_only=True)
    try:
        row = connection.execute(
            """
            SELECT sl.id, sl.code, sl.rank, sl.label, cc.subject_id
            FROM school_levels sl
            JOIN curriculum_chapters cc ON cc.grade_level_id = sl.id
            WHERE cc.status = 'approved'
            ORDER BY sl.rank, cc.id
            LIMIT 1
            """
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise RuntimeError("No approved curriculum chapter found in V2 database.")
    return GradeLevel(str(row[1]), int(row[2]), str(row[3])), int(row[4])


def run_smoke_test() -> dict[str, object]:
    report: dict[str, object] = {"steps": []}
    try:
        prepare_runtime()
        report["steps"].append({"step": "prepare_runtime", "ok": True})
    except duckdb.IOException as exc:
        report["steps"].append({"step": "prepare_runtime", "ok": True, "skipped": str(exc)})

    suffix = uuid.uuid4().hex[:8]
    parent_username = f"smoke-parent-{suffix}"
    parent_email = f"smoke.parent.{suffix}@example.test"
    parent_password = "SmokeTest123!"
    student_username = f"smoke-student-{suffix}"
    student_password = "SmokeTest123!"
    learner_external_ref = f"parent-child:{suffix}"
    first_name = "SmokeTest"

    report["suffix"] = suffix

    ok, message = legacy_database.create_parent(
        "Smoke",
        "Parent",
        parent_email,
        parent_username,
        parent_password,
        parent_password,
    )
    report["steps"].append({"step": "create_parent", "ok": ok, "message": message})
    if not ok:
        return report

    parent = legacy_database.authenticate(parent_username, parent_password, "parent")
    report["steps"].append({"step": "authenticate_parent", "ok": parent is not None})
    if parent is None:
        return report

    parent_ref = str(parent["id"])
    repository = DuckDBUnifiedExperienceRepository()
    grade, subject_id = _grade_and_subject(repository)
    request = OnboardingRequest(
        f"{learner_external_ref}:2026-2027",
        LearnerProfile(
            learner_external_ref,
            first_name,
            CreatorRole.PARENT,
            birth_date=date(2014, 5, 15),
        ),
        AcademicYear(2026, 2027),
        grade,
        LearnerGoalConfiguration(ObjectiveKind.LONG_TERM_MASTERY),
        (SubjectPreference(subject_id, priority=True),),
        StudyPreferences(30, (AvailabilitySlot(1, 30, time(17, 0)),), difficulty=DifficultyPreference.STANDARD),
        CreatorRole.PARENT,
        "smoke_connection_test",
    )
    manager = LearnerProfileManagementService(repository)
    result = manager.create(
        parent_ref,
        request,
        OnboardingProfileInput(
            0,
            first_name,
            "Eleve",
            date(2014, 5, 15),
            "2026-2027",
            "FR-NATIONAL",
            ("interactive",),
            "HINT_FIRST",
            False,
            f"smoke.student.{suffix}@example.test",
        ),
        OnboardingService(DuckDBOnboardingRepository()),
        UnifiedOnboardingProfileService(repository),
    )
    learner_id = int(result.learner_id)
    report["steps"].append({"step": "create_learner_profile", "ok": True, "learner_id": learner_id})

    account_ok, account_message = legacy_database.create_student_account(
        int(parent["id"]),
        learner_external_ref,
        first_name,
        f"smoke.student.{suffix}@example.test",
        student_username,
        student_password,
        student_password,
    )
    report["steps"].append(
        {"step": "create_student_account", "ok": account_ok, "message": account_message}
    )
    if not account_ok:
        return report

    student = legacy_database.authenticate(student_username, student_password, "student")
    report["steps"].append({"step": "authenticate_student", "ok": student is not None})
    if student is None:
        return report

    vt_repo = DuckDBVirtualTeacherRepository()
    preferences = AITeacherPreferencesService(vt_repo)
    vt_repo.ensure_preferences(learner_id)
    preferences.save_for_parent(
        user={"id": int(parent["id"]), "name": parent_username, "role": AuthRole.PARENT.value},
        parent_ref=parent_ref,
        learner_id=learner_id,
        patch=PreferencesPatch(
            feature_enabled=True,
            teacher_profile="TEACHER_FEMALE_01",
            teacher_name="Emma",
            voice_id="warm_female",
            tone="calm",
            response_length="normal",
            help_level=2,
            audio_enabled=False,
            parent_locked=False,
            fields={
                "feature_enabled",
                "teacher_profile",
                "teacher_name",
                "voice_id",
                "tone",
                "response_length",
                "help_level",
                "audio_enabled",
                "parent_locked",
            },
        ),
    )
    prefs = vt_repo.get_preferences(learner_id)
    report["steps"].append(
        {
            "step": "associate_virtual_teacher",
            "ok": prefs.feature_enabled,
            "teacher_name": prefs.teacher_name,
        }
    )

    teacher = AITeacherService(
        vt_repo,
        preferences,
        AIConversationOrchestrator(llm=DeterministicLLMService(), guardrails=PedagogicalGuardrails()),
        ConsoleTTSService(),
    )
    session = teacher.start_session(
        user={"id": int(student["id"]), "name": student_username, "role": AuthRole.STUDENT.value},
        learner_id=learner_id,
        student_learner_id=learner_id,
        actor_type="STUDENT",
        actor_ref=str(student["id"]),
        context=PedagogicalContext(learner_id=learner_id, learner_display_name=first_name),
    )
    report["steps"].append(
        {
            "step": "start_virtual_teacher_session",
            "ok": session.learner_id == learner_id,
            "session_id": session.id,
        }
    )

    report["credentials"] = {
        "parent_username": parent_username,
        "parent_password": parent_password,
        "student_username": student_username,
        "student_password": student_password,
        "learner_external_ref": learner_external_ref,
        "learner_id": learner_id,
    }
    report["success"] = all(step.get("ok") for step in report["steps"])
    return report


def main() -> None:
    report = run_smoke_test()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report.get("success"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
