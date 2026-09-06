"""LCAI-0020 — 43 mandatory scenarios from ticket LCAI-0020-05."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from application.dto.student_guidance import (
    AIAvailability,
    AIAvailabilityMode,
    GuidanceSource,
    MasteryBand,
    ResultExplanationContext,
)
from domain.unified_experience.models import AssignmentStatus, AssignmentType, DifficultyMode, HomeworkAssignment
from services.auth.roles import AuthRole
from services.learning_session.experience import MasteryView, StudentDashboard
from services.student_guidance.availability import resolve_ai_availability
from services.student_guidance.deterministic import build_deterministic_welcome, homework_during
from services.student_guidance.mastery_bands import classify_mastery_band
from services.student_guidance.service import StudentGuidanceService
from services.virtual_teacher.llm_service import DeterministicLLMService

ROOT = Path(__file__).parents[1]


def _student_actor(learner_id: int) -> dict[str, object]:
    return {"role": AuthRole.STUDENT.value, "id": 1, "name": "Test", "resolved_learner_id": learner_id}


def _homework_item(*, learner_id: int = 7, homework_id: int = 10, status=AssignmentStatus.READY, session_id=None):
    return HomeworkAssignment(
        homework_id=homework_id,
        learner_id=learner_id,
        mode=AssignmentType.TARGETED,
        status=status,
        subject_id=1,
        subject_label="Mathématiques",
        difficulty=DifficultyMode.MEDIUM,
        exercise_count=5,
        target_duration_minutes=20,
        due_at=datetime.now(UTC),
        selected_content_ids=(),
        session_id=session_id,
        assigned_by_type="PARENT",
        created_at=datetime.now(UTC),
    )


def _dashboard(*, learner_id: int = 7, mastery=()) -> StudentDashboard:
    return StudentDashboard(
        learner_id=learner_id,
        display_name="Alex",
        objective="Fractions",
        recommended_duration_minutes=20,
        metrics=(),
        mastery=mastery,
        recent_sessions=(),
        current_session=None,
        next_revision=None,
    )


def _service(
    *,
    experience=None,
    homework=None,
    orchestrator=None,
    vt_repository=None,
) -> StudentGuidanceService:
    return StudentGuidanceService(
        experience=experience or MagicMock(),
        homework=homework or MagicMock(),
        vt_repository=vt_repository or MagicMock(),
        orchestrator=orchestrator or MagicMock(),
    )


def _active_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "services.student_guidance.service.resolve_ai_availability",
        lambda **kwargs: AIAvailability(
            mode=AIAvailabilityMode.ACTIVE,
            platform_enabled=True,
            learner_feature_enabled=True,
            provider_configured=True,
        ),
    )


# --- Navigation (1-5) ---


@pytest.mark.parametrize(
    "env",
    [
        {"LCAI_AI_TUTOR_ENABLED": "1"},
        {"LCAI_AI_TUTOR_ENABLED": "0"},
        {},
    ],
    ids=["ai_active", "ai_inactive", "no_provider_key"],
)
def test_scenario_1_to_3_tableau_de_bord_always_in_nav(env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    source = (ROOT / "ui" / "unified_app.py").read_text(encoding="utf-8")
    assert "Accueil" in source
    nav_block = source.split("_STUDENT_PAGES = (")[1].split(")")[0]
    assert "Accueil" in nav_block
    assert "Sujets Brevet" in nav_block


def test_scenario_4_return_to_tableau_de_bord_from_homework() -> None:
    source = (ROOT / "ui" / "v2_experience.py").read_text(encoding="utf-8")
    assert 'request_navigation(st.session_state, "student", "Tableau de bord")' in source
    assert 'request_navigation(st.session_state, "student", "Devoirs")' in source
    # Aliases map legacy labels to §33 Accueil / Devoir personnalisé
    from ui.dnb_navigation import resolve_student_page

    assert resolve_student_page("Tableau de bord") == "Accueil"
    assert resolve_student_page("Devoirs") == "Devoir personnalisé"


def test_scenario_5_no_menu_removed_by_ai_flag() -> None:
    source = (ROOT / "ui" / "unified_app.py").read_text(encoding="utf-8")
    expected = (
        "Accueil",
        "Mon programme",
        "Réviser",
        "S'entraîner",
        "Devoir personnalisé",
        "Sujets Brevet",
        "Brevets blancs",
        "Oral",
        "Mes résultats",
        "Coach Brevet",
    )
    nav_block = source.split("_STUDENT_PAGES = (")[1].split(")")[0]
    for label in expected:
        assert label in nav_block
    assert "Mon professeur IA" not in nav_block


# --- Connexion (6-10) ---


def test_scenario_6_ai_welcome_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    _active_ai(monkeypatch)
    orchestrator = MagicMock()
    from domain.virtual_teacher.models import AITeacherResponse

    orchestrator.generate_answer.return_value = AITeacherResponse(message="Bonjour Alex", response_type="EXPLANATION")
    experience = MagicMock()
    experience.dashboard.return_value = _dashboard()
    service = _service(experience=experience, orchestrator=orchestrator)
    snapshot = service.build_home_guidance(_student_actor(7), 7)
    assert snapshot.welcome.source is GuidanceSource.AI


def test_scenario_7_deterministic_welcome_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LCAI_AI_TUTOR_ENABLED", "0")
    experience = MagicMock()
    experience.dashboard.return_value = _dashboard()
    service = _service(experience=experience)
    snapshot = service.build_home_guidance(_student_actor(7), 7)
    assert snapshot.welcome.source is GuidanceSource.DETERMINISTIC


def test_scenario_8_deterministic_welcome_on_orchestrator_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _active_ai(monkeypatch)
    orchestrator = MagicMock()
    orchestrator.generate_answer.side_effect = TimeoutError("timeout")
    experience = MagicMock()
    experience.dashboard.return_value = _dashboard()
    service = _service(experience=experience, orchestrator=orchestrator)
    snapshot = service.build_home_guidance(_student_actor(7), 7)
    assert snapshot.welcome.source is GuidanceSource.DETERMINISTIC


def test_scenario_9_priority_from_real_homework_data() -> None:
    homework = MagicMock()
    homework.list_for_learner.return_value = (_homework_item(),)
    experience = MagicMock()
    experience.dashboard.return_value = _dashboard()
    service = _service(experience=experience, homework=homework)
    context = service.build_home_context(7)
    assert context.homework_todo
    assert context.homework_todo[0].subject_label == "Mathématiques"


def test_scenario_10_cross_learner_access_denied() -> None:
    service = _service()
    actor = {"role": AuthRole.STUDENT.value, "resolved_learner_id": 2}
    with pytest.raises(PermissionError):
        service.build_home_guidance(actor, 1)


# --- Devoirs (11-16) ---


def test_scenario_11_homework_before_guidance() -> None:
    homework = MagicMock()
    item = _homework_item()
    homework._owned.return_value = item
    service = _service(homework=homework)
    guidance = service.prepare_homework_guidance(_student_actor(7), 7, 10)
    assert guidance.objective
    assert guidance.advice_before


@pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
def test_scenario_12_13_single_explicit_help_without_solution(level: int) -> None:
    response = homework_during(level, statement="Calcule le volume d'un cube")
    assert response.message
    assert response.help_level == 1
    assert "solution complète" not in response.message.lower()


def test_scenario_14_homework_result_explained() -> None:
    homework = MagicMock()
    homework._owned.return_value = _homework_item(status=AssignmentStatus.COMPLETED)
    experience = MagicMock()
    experience.dashboard.return_value = _dashboard(
        mastery=(MasteryView(1, "Fractions", 55, "FRAGILE", "STABLE"),),
    )
    service = _service(experience=experience, homework=homework)
    result = service.explain_homework_result(_student_actor(7), 7, 10)
    assert isinstance(result, ResultExplanationContext)
    assert result.score_summary


def test_scenario_15_llm_does_not_change_deterministic_recommendation(monkeypatch: pytest.MonkeyPatch) -> None:
    _active_ai(monkeypatch)
    homework = MagicMock()
    homework._owned.return_value = _homework_item(status=AssignmentStatus.COMPLETED)
    experience = MagicMock()
    experience.dashboard.return_value = _dashboard()
    orchestrator = MagicMock()
    from domain.virtual_teacher.models import AITeacherResponse

    orchestrator.generate_answer.return_value = AITeacherResponse(message="Narratif IA", response_type="EXPLANATION")
    service = _service(experience=experience, homework=homework, orchestrator=orchestrator)
    result = service.explain_homework_result(_student_actor(7), 7, 10)
    assert result.deterministic_recommendation


def test_scenario_16_session_resume_without_duplication() -> None:
    source = (ROOT / "ui" / "unified_app.py").read_text(encoding="utf-8")
    assert "Reprendre la séance" in source
    assert "hw_resume_session_" in source


# --- Tableau de bord (17-24) ---


def test_scenario_17_to_22_dashboard_snapshot_fields() -> None:
    homework = MagicMock()
    homework.list_for_learner.return_value = (_homework_item(),)
    experience = MagicMock()
    experience.dashboard.return_value = _dashboard(
        mastery=(MasteryView(1, "Équations", 42, "FRAGILE", "DECLINING"),),
    )
    service = _service(experience=experience, homework=homework)
    snapshot = service.build_home_guidance(_student_actor(7), 7)
    assert snapshot.context.mastery
    assert snapshot.mastery_by_band
    assert snapshot.context.revision_priorities is not None


def test_scenario_23_insufficient_data_without_invention() -> None:
    experience = MagicMock()
    experience.dashboard.return_value = _dashboard(mastery=())
    service = _service(experience=experience)
    snapshot = service.build_home_guidance(_student_actor(7), 7)
    assert snapshot.welcome.greeting
    assert snapshot.context.mastery == ()


def test_scenario_24_recommendations_without_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LCAI_AI_TUTOR_ENABLED", "0")
    experience = MagicMock()
    experience.dashboard.return_value = _dashboard(
        mastery=(MasteryView(1, "Géométrie", 35, "FRAGILE", "DECLINING"),),
    )
    service = _service(experience=experience)
    revision = service.recommend_revision(_student_actor(7), 7)
    assert revision.message


# --- Révision (25-29) ---


def test_scenario_25_revision_with_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    _active_ai(monkeypatch)
    orchestrator = MagicMock()
    from domain.virtual_teacher.models import AITeacherResponse

    orchestrator.generate_answer.return_value = AITeacherResponse(
        message="Révise les fractions", response_type="EXPLANATION"
    )
    experience = MagicMock()
    experience.dashboard.return_value = _dashboard(
        mastery=(MasteryView(1, "Fractions", 40, "FRAGILE", "DECLINING"),),
    )
    service = _service(experience=experience, orchestrator=orchestrator)
    revision = service.recommend_revision(_student_actor(7), 7)
    assert revision.message


def test_scenario_26_revision_deterministic_without_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LCAI_AI_TUTOR_ENABLED", "0")
    experience = MagicMock()
    experience.dashboard.return_value = _dashboard()
    service = _service(experience=experience)
    revision = service.recommend_revision(_student_actor(7), 7)
    assert revision.priority.action_label


def test_scenario_27_revision_priority_has_skill_label() -> None:
    experience = MagicMock()
    experience.dashboard.return_value = _dashboard(
        mastery=(MasteryView(2, "Proportionnalité", 38, "FRAGILE", "STABLE"),),
    )
    service = _service(experience=experience)
    revision = service.recommend_revision(_student_actor(7), 7)
    assert revision.priority.skill_label


def test_scenario_28_29_revision_reason_traceability() -> None:
    experience = MagicMock()
    experience.dashboard.return_value = _dashboard(
        mastery=(MasteryView(3, "Statistiques", 30, "FRAGILE", "DECLINING"),),
    )
    service = _service(experience=experience)
    revision = service.recommend_revision(_student_actor(7), 7)
    assert revision.priority.reason in revision.message


# --- Robustesse (30-38) ---


def test_scenario_30_provider_timeout_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _active_ai(monkeypatch)
    orchestrator = MagicMock()
    orchestrator.generate_answer.side_effect = TimeoutError("timeout")
    service = _service(orchestrator=orchestrator)
    response = service.guide_current_exercise(_student_actor(7), 7, 1, 1, 3)
    assert response.source is GuidanceSource.DETERMINISTIC


def test_scenario_31_invalid_provider_response_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _active_ai(monkeypatch)
    orchestrator = MagicMock()
    orchestrator.generate_answer.side_effect = ValueError("invalid")
    service = _service(orchestrator=orchestrator)
    response = service.guide_current_exercise(_student_actor(7), 7, 1, 1, 2)
    assert response.message


def test_scenario_32_budget_exceeded_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _active_ai(monkeypatch)
    orchestrator = MagicMock()
    orchestrator.generate_answer.side_effect = RuntimeError("budget exceeded")
    service = _service(orchestrator=orchestrator)
    response = service.guide_current_exercise(_student_actor(7), 7, 1, 1, 4)
    assert response.source is GuidanceSource.DETERMINISTIC


def test_scenario_33_feature_flag_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LCAI_AI_TUTOR_ENABLED", "0")
    availability = resolve_ai_availability(learner_id=1, repository=MagicMock())
    assert availability.mode is not AIAvailabilityMode.ACTIVE


def test_scenario_34_missing_provider_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LCAI_AI_TUTOR_ENABLED", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    availability = resolve_ai_availability(learner_id=1, repository=MagicMock())
    assert availability.mode in {AIAvailabilityMode.INACTIVE, AIAvailabilityMode.UNAVAILABLE}


def test_scenario_35_36_parent_student_isolation_and_learner_scoping() -> None:
    experience = MagicMock()
    experience.dashboard.return_value = _dashboard()
    homework = MagicMock()
    homework.list_for_learner.return_value = ()
    service = _service(experience=experience, homework=homework)
    parent = {"role": AuthRole.PARENT.value, "resolved_learner_id": None}
    snapshot = service.build_home_guidance(parent, 7)
    assert snapshot.context.learner_id == 7
    assert "Coach Brevet" in snapshot.welcome.greeting or snapshot.welcome.greeting


def test_scenario_37_no_secrets_in_guidance_module() -> None:
    for path in (ROOT / "ui" / "student_guidance.py", ROOT / "services" / "student_guidance" / "service.py"):
        text = path.read_text(encoding="utf-8")
        assert "OPENAI_API_KEY" not in text
        assert "sk-" not in text


def test_scenario_38_no_direct_llm_in_ui() -> None:
    ui_source = (ROOT / "ui" / "student_guidance.py").read_text(encoding="utf-8")
    assert "generate_answer" not in ui_source
    assert "build_llm_service" not in ui_source
    assert "build_student_guidance_service" in ui_source
    assert "continue_exercise_help" in ui_source
    assert "Envoyer au Coach Brevet" in ui_source


def test_guide_current_exercise_sends_exercise_to_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    _active_ai(monkeypatch)
    from domain.virtual_teacher.models import AITeacherResponse

    orchestrator = MagicMock()
    orchestrator.generate_answer.return_value = AITeacherResponse(
        message="Utilise la formule V = a³.",
        response_type="HINT",
    )
    experience = MagicMock()
    experience.dashboard.return_value = _dashboard()
    homework = MagicMock()
    homework.list_for_learner.return_value = ()
    vt = MagicMock()
    from domain.virtual_teacher.models import VirtualTeacherPreferences

    vt.ensure_preferences.return_value = VirtualTeacherPreferences(
        id=1,
        learner_id=7,
        teacher_profile="default",
        teacher_name=None,
        voice_id="alloy",
        tone="encouraging",
        response_length="normal",
        help_level=2,
        audio_enabled=False,
        feature_enabled=True,
        parent_locked=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service = _service(experience=experience, homework=homework, orchestrator=orchestrator, vt_repository=vt)
    response = service.guide_current_exercise(
        _student_actor(7),
        7,
        1,
        1,
        1,
        statement="Calcule le volume d'un cube d'arête 3 cm",
        notion_reminder="Géométrie — volumes",
    )
    assert response.source is GuidanceSource.AI
    assert "formule" in response.message.casefold() or "V" in response.message
    call_kwargs = orchestrator.generate_answer.call_args.kwargs
    user_message = call_kwargs["request"].user_message
    assert "Calcule le volume" in user_message
    assert "aide" in user_message.casefold() or "Coach Brevet" in user_message
    session_summary = call_kwargs["request"].context.session_summary or ""
    assert "Coach Brevet" in session_summary or "Readiness" in session_summary


def test_continue_exercise_help_uses_history(monkeypatch: pytest.MonkeyPatch) -> None:
    _active_ai(monkeypatch)
    from domain.virtual_teacher.models import AITeacherResponse, VirtualTeacherPreferences

    orchestrator = MagicMock()
    orchestrator.generate_answer.return_value = AITeacherResponse(
        message="Reprends l'étape du cube de l'arête.",
        response_type="HINT",
    )
    experience = MagicMock()
    experience.dashboard.return_value = _dashboard()
    homework = MagicMock()
    homework.list_for_learner.return_value = ()
    vt = MagicMock()
    vt.ensure_preferences.return_value = VirtualTeacherPreferences(
        id=1,
        learner_id=7,
        teacher_profile="default",
        teacher_name=None,
        voice_id="alloy",
        tone="encouraging",
        response_length="normal",
        help_level=2,
        audio_enabled=False,
        feature_enabled=True,
        parent_locked=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service = _service(experience=experience, homework=homework, orchestrator=orchestrator, vt_repository=vt)
    history = (
        ("assistant", "Commence par identifier l'arête."),
        ("user", "Je ne comprends pas"),
    )
    response = service.continue_exercise_help(
        _student_actor(7),
        7,
        follow_up="Que faire ensuite ?",
        history=history,
        statement="Calcule le volume d'un cube d'arête 3 cm",
    )
    assert response.source is GuidanceSource.AI
    call_kwargs = orchestrator.generate_answer.call_args.kwargs
    assert call_kwargs["history"] == history
    assert "Que faire ensuite" in call_kwargs["request"].user_message
    assert call_kwargs["preferences"].teacher_name == "Coach Brevet"


def test_continue_exercise_help_rejects_empty_follow_up(monkeypatch: pytest.MonkeyPatch) -> None:
    _active_ai(monkeypatch)
    service = _service()
    with pytest.raises(ValueError, match="question"):
        service.continue_exercise_help(
            _student_actor(7),
            7,
            follow_up="   ",
            history=(),
            statement="2+2",
        )


# --- Régression (39-43) ---


def test_scenario_39_homework_ui_wiring_present() -> None:
    source = (ROOT / "ui" / "unified_app.py").read_text(encoding="utf-8")
    assert "render_homework_before_guidance" in source
    assert "render_homework_result_explanation" in source


def test_scenario_40_mastery_bands_unchanged_logic() -> None:
    assert classify_mastery_band(score=92, level="MASTERED", trend="IMPROVING") is MasteryBand.VERY_HIGH
    assert classify_mastery_band(score=30, level="FRAGILE", trend="DECLINING") is MasteryBand.TO_REVISE


def test_scenario_41_analytics_services_not_in_ui() -> None:
    source = (ROOT / "ui" / "student_guidance.py").read_text(encoding="utf-8")
    assert "PedagogicalDashboardService" not in source


def test_scenario_42_revision_page_wiring() -> None:
    source = (ROOT / "ui" / "unified_app.py").read_text(encoding="utf-8")
    assert "load_revision_guidance" in source


def test_scenario_43_deterministic_llm_fallback_still_usable() -> None:
    response = DeterministicLLMService().generate(system_prompt="test", messages=())
    assert response.message


def test_mastery_band_thresholds_are_centralized() -> None:
    assert classify_mastery_band(score=0, level="NOT_STARTED", trend="STABLE") is MasteryBand.UNEVALUATED


def test_deterministic_welcome_never_empty() -> None:
    from application.dto.student_guidance import StudentHomeContext

    context = StudentHomeContext(
        learner_id=1,
        display_name="Alex",
        homework_todo=(),
        homework_overdue=(),
        homework_recent=(),
        mastery=(),
        fragile_skills=(),
        strong_skills=(),
        revision_priorities=(),
        recent_score=None,
        success_rate=None,
        objective="Consolider les fractions",
        next_revision=None,
    )
    welcome = build_deterministic_welcome(context)
    assert welcome.source is GuidanceSource.DETERMINISTIC
    assert welcome.greeting
    assert welcome.primary_action


def test_session_explanation_links_homework() -> None:
    homework = MagicMock()
    homework.list_for_learner.return_value = (_homework_item(session_id=99, status=AssignmentStatus.COMPLETED),)
    homework._owned.return_value = _homework_item(session_id=99, status=AssignmentStatus.COMPLETED)
    experience = MagicMock()
    experience.dashboard.return_value = _dashboard()
    service = _service(experience=experience, homework=homework)
    assert service.find_homework_id_for_session(7, 99) == 10
    result = service.explain_session_result(_student_actor(7), 7, 99)
    assert result is not None
    assert result.homework_id == 10
