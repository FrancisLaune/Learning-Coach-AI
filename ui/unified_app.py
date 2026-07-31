"""Unified role-aware V2 Streamlit shell for students and parents."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, time
from functools import partial

import streamlit as st

from application.experience_factory import (
    build_parent_experience_controller,
    build_student_experience_controller,
)
from domain.decision.enums import ObjectiveKind
from domain.learning.models import GradeLevel
from domain.onboarding.enums import CreatorRole, DifficultyPreference
from domain.onboarding.models import (
    AvailabilitySlot,
    LearnerGoalConfiguration,
    LearnerProfile,
    OnboardingRequest,
    OnboardingResult,
    StudyPreferences,
    SubjectPreference,
)
from domain.unified_experience.models import AssignmentStatus, AssignmentType, DifficultyMode, HomeworkRequest
from domain.virtual_teacher.models import PreferencesPatch
from infrastructure.database.legacy_gateway import (
    create_student_account,
    deactivate_student_account,
    delete_student_account,
    has_active_student_account,
    reactivate_student_account,
    reset_student_password,
    student_account_for_learner,
)
from infrastructure.repositories.decision import DuckDBDecisionRepository
from infrastructure.repositories.learning import DuckDBLearningRepository
from infrastructure.repositories.learning_session import DuckDBLearningSessionRepository
from infrastructure.repositories.onboarding import DuckDBOnboardingRepository
from infrastructure.repositories.recommendation import DuckDBRecommendationRepository
from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository
from infrastructure.repositories.virtual_teacher import DuckDBVirtualTeacherRepository
from services.academic_year import academic_year_options, default_academic_year, parse_academic_year
from services.family_data_diagnostic import FamilyDataDiagnosticService
from services.family_learner_management import FamilyLearnerManagementService
from services.learner_session import cached_learner_id_if_valid, learner_cache_key
from services.learning_session.experience import StudentDashboard
from services.learning_session.orchestration import LearningSessionService
from services.onboarding import OnboardingService, OnboardingValidationError
from services.parent_ref import parent_ref_from_user
from services.recommendation import PersonalizedSessionService
from services.content.homework_availability import HomeworkAvailabilityService
from services.homework.errors import HomeworkCompletionError
from services.unified_experience import (
    DeterministicCoachService,
    HomeworkService,
    HomeworkSessionService,
    LearnerProfileManagementService,
    OnboardingProfileInput,
    ProgrammeChangeService,
    UnifiedOnboardingProfileService,
)
from services.virtual_teacher.ai_teacher_preferences_service import AITeacherPreferencesService
from services.virtual_teacher.ai_teacher_service import AITeacherService
from ui.curriculum_state import clear_curriculum_selection, reconcile_skills, reconcile_subject_change
from ui.i18n import label
from ui.navigation import apply_navigation_request, request_navigation
from ui.parent_child_wizard import render_child_creation_wizard, reset_child_creation_wizard, submit_child_creation
from ui.parent_learner_sheet import render_parent_learner_sheet
from ui.session import logout
from ui.v2_experience import (
    parent_dashboard,
    session_screen,
    student_dashboard,
    student_history,
    student_summary,
)
from ui.virtual_teacher import (
    build_virtual_teacher_stack,
    render_parent_virtual_teacher_settings,
    render_student_virtual_teacher,
)

LoginRenderer = Callable[[], None]
LOGGER = logging.getLogger(__name__)
ERROR_HELP_LABELS = {
    "HINT_FIRST": "Donne-moi d'abord un indice",
    "EXPLAIN_METHOD": "Explique-moi la méthode",
    "SHOW_CORRECTION": "Montre immédiatement la correction",
}
OBJECTIVE_LABELS = {
    ObjectiveKind.PREPARATION_NEXT_GRADE.value: "Préparer la classe suivante",
    ObjectiveKind.REVISION.value: "Révision globale",
    ObjectiveKind.LONG_TERM_MASTERY.value: "Suivre les cours pendant l'année",
    ObjectiveKind.CONSOLIDATION.value: "Consolider les faiblesses",
    ObjectiveKind.HOMEWORK.value: "Préparer un contrôle",
    ObjectiveKind.PREPARATION_BREVET.value: "Préparer un examen",
    ObjectiveKind.CATCH_UP.value: "Rattrapage / remédiation",
}


def _family_service() -> FamilyLearnerManagementService:
    repository = _repository()
    profile_manager = LearnerProfileManagementService(repository)

    class _AccountGateway:
        def deactivate(self, parent_user_id: int, learner_external_ref: str) -> None:
            deactivate_student_account(parent_user_id, learner_external_ref)

    return FamilyLearnerManagementService(repository, profile_manager, _AccountGateway())


def _family_diagnostic_service() -> FamilyDataDiagnosticService:
    class _AccountProbe:
        def has_active(self, learner_external_ref: str) -> bool:
            return has_active_student_account(learner_external_ref)

    return FamilyDataDiagnosticService(_repository(), account_probe=_AccountProbe())


def _repository() -> DuckDBUnifiedExperienceRepository:
    return DuckDBUnifiedExperienceRepository()


def _homework_service() -> HomeworkService:
    from services.homework.factory import build_homework_service

    return build_homework_service(_repository())


def _virtual_teacher_repository() -> DuckDBVirtualTeacherRepository:
    return DuckDBVirtualTeacherRepository()


def _virtual_teacher_services() -> tuple[AITeacherService, AITeacherPreferencesService]:
    return build_virtual_teacher_stack(_virtual_teacher_repository)


def _homework_sessions() -> HomeworkSessionService:
    repository = DuckDBLearningSessionRepository()
    sessions = LearningSessionService(DuckDBRecommendationRepository(), repository, repository)
    return HomeworkSessionService(_repository(), sessions)


def _create_initial_session(result: OnboardingResult) -> int | None:
    recommendations = DuckDBRecommendationRepository()
    proposal = PersonalizedSessionService(
        decision_repository=DuckDBDecisionRepository(),
        learning_repository=DuckDBLearningRepository(),
        session_repository=recommendations,
    ).generate(result, recommendations.load_approved_contents(), result.created_at)
    if proposal.absence_code or not proposal.activities:
        return None
    proposal_id = recommendations.proposal_id_for_stable_id(proposal.stable_id)
    sessions = DuckDBLearningSessionRepository()
    session = LearningSessionService(recommendations, sessions, sessions).create_session(
        proposal_id,
        result.created_at,
    )
    return session.session_id


def _virtual_teacher_status_label(learner_id: int) -> str:
    try:
        preferences = DuckDBVirtualTeacherRepository().get_preferences(learner_id)
        if preferences is None:
            return "Non configuré"
        return "Activé" if preferences.feature_enabled else "Désactivé"
    except Exception:
        return "Indisponible"


def _child_creation_objectives() -> dict[str, ObjectiveKind]:
    return {
        "Préparer la classe suivante": ObjectiveKind.PREPARATION_NEXT_GRADE,
        "Révision globale": ObjectiveKind.REVISION,
        "Suivre les cours pendant l'année": ObjectiveKind.LONG_TERM_MASTERY,
        "Consolider les faiblesses": ObjectiveKind.CONSOLIDATION,
        "Préparer un contrôle": ObjectiveKind.HOMEWORK,
        "Préparer un examen": ObjectiveKind.PREPARATION_BREVET,
        "Rattrapage / remédiation": ObjectiveKind.CATCH_UP,
        "Approfondissement": ObjectiveKind.LONG_TERM_MASTERY,
    }


def _reset_child_creation_wizard() -> None:
    reset_child_creation_wizard()


def _save_child_virtual_teacher_preferences(
    *,
    user: dict[str, object],
    parent_ref: str,
    learner_id: int,
    data: dict[str, object],
) -> None:
    vt_repository = _virtual_teacher_repository()
    vt_repository.ensure_preferences(learner_id)
    if not data.get("vt_feature_enabled"):
        return
    _, preferences_service = _virtual_teacher_services()
    preferences_service.save_for_parent(
        user=user,
        parent_ref=parent_ref,
        learner_id=learner_id,
        patch=PreferencesPatch(
            feature_enabled=True,
            teacher_profile=str(data.get("vt_teacher_profile", "TEACHER_FEMALE_01")),
            teacher_name=str(data.get("vt_teacher_name", "Emma")),
            voice_id=str(data.get("vt_voice_id", "warm_female")),
            tone=str(data.get("vt_tone", "calm")),
            response_length=str(data.get("vt_response_length", "normal")),
            help_level=int(data.get("vt_help_level", 2)),
            audio_enabled=bool(data.get("vt_audio_enabled", False)),
            parent_locked=bool(data.get("vt_parent_locked", False)),
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


def _submit_child_from_wizard(
    *,
    parent_ref: str,
    user: dict[str, object],
    data: dict[str, object],
    repository: DuckDBUnifiedExperienceRepository,
    grade_labels: dict[int, str],
    subject_labels: dict[int, str],
    grade_by_id: dict[int, GradeLevel],
    objectives: dict[str, ObjectiveKind],
) -> bool:
    return bool(
        submit_child_creation(
            parent_ref=parent_ref,
            user=user,
            data=data,
            repository=repository,
            grade_by_id=grade_by_id,
            objectives=objectives,
            safe=_safe,
            create_initial_session=_create_initial_session,
            save_virtual_teacher_preferences=lambda learner_id, wizard_data: _save_child_virtual_teacher_preferences(
                user=user,
                parent_ref=parent_ref,
                learner_id=learner_id,
                data=wizard_data,
            ),
        )
    )


def _learner_id(user: dict[str, object]) -> int | None:
    external_ref = str(user.get("learner_external_ref") or f"legacy-user:{user['id']}")
    cached = cached_learner_id_if_valid(
        session_cache_key=st.session_state.get("unified_learner_cache_key"),
        user_id=user["id"],
        external_ref=external_ref,
        cached_learner_id=st.session_state.get("unified_learner_id"),
    )
    if cached is not None:
        return cached
    learner_id = _repository().learner_for_external_ref(external_ref)
    if learner_id:
        st.session_state.unified_learner_id = learner_id
        st.session_state.unified_learner_cache_key = learner_cache_key(user["id"], external_ref)
    else:
        st.session_state.pop("unified_learner_id", None)
        st.session_state.pop("unified_learner_cache_key", None)
    return learner_id


def _safe[T](operation: Callable[[], T]) -> T | None:
    try:
        return operation()
    except HomeworkCompletionError as exc:
        st.error(exc.user_message)
    except (ValueError, PermissionError, OnboardingValidationError) as exc:
        message = str(exc)
        if message == "Recommendation exceeds the available duration":
            st.error(
                "La durée planifiée de ce devoir est trop courte pour les exercices sélectionnés. "
                "Demande à ton parent de recréer le devoir avec une durée plus longue, ou réessaie dans quelques instants."
            )
        else:
            st.error(message)
    except Exception:
        LOGGER.exception("Unexpected unified experience persistence failure")
        st.error("Cette action n'est pas disponible pour le moment. Tes données existantes sont conservées.")
    return None


def onboarding(user: dict[str, object]) -> None:
    repository = _repository()
    st.title("Construisons ton parcours")
    st.caption("Ces informations permettent au moteur déterministe d'adapter les séances et le planning.")
    grades = repository.grade_levels()
    subjects = repository.reference_subjects()
    grade_labels = {item[0]: item[2] for item in grades}
    subject_labels = {item[0]: item[2] for item in subjects}
    if not grades or not subjects:
        st.error("Le catalogue de contenus approuvés est vide. Aucun parcours ne sera inventé.")
        return

    with st.form("unified_onboarding"):
        identity = st.columns(2)
        first_name = identity[0].text_input("Prénom", value=str(user["name"]))
        last_name = identity[1].text_input("Nom (facultatif)")
        email = st.text_input("Adresse e-mail")
        birth_date = st.date_input(
            "Date de naissance",
            value=None,
            min_value=date(date.today().year - 30, 1, 1),
            max_value=date(date.today().year - 5, 12, 31),
            format="DD/MM/YYYY",
        )
        current_id = st.selectbox("Classe actuelle", list(grade_labels), format_func=grade_labels.__getitem__)
        target_options: list[int | None] = [None, *grade_labels]
        target_id = st.selectbox(
            "Classe cible, si nécessaire",
            target_options,
            format_func=lambda item: "Aucune" if item is None else grade_labels[item],
        )
        year_options = academic_year_options(date.today())
        school_year = st.selectbox(
            "Année scolaire",
            year_options,
            index=year_options.index(default_academic_year(date.today())),
        )
        objective_label = st.selectbox(
            "Objectif principal",
            (
                "Préparer la classe suivante",
                "Révision globale",
                "Suivre les cours pendant l'année",
                "Consolider mes faiblesses",
                "Préparer un contrôle",
                "Préparer un examen",
                "Rattrapage / remédiation",
                "Approfondissement",
            ),
        )
        selected_subjects = st.multiselect(
            "Matières du parcours",
            list(subject_labels),
            default=list(subject_labels),
            format_func=subject_labels.__getitem__,
        )
        duration = st.slider("Temps d'étude préféré par jour", 10, 120, 30, 5)
        weekdays = st.multiselect(
            "Jours d'étude",
            list(range(7)),
            default=[0, 1, 2, 3, 4],
            format_func=lambda day: ("Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche")[day],
        )
        formats = st.multiselect(
            "Je préfère",
            (
                "Exemples avant les exercices",
                "Explications détaillées",
                "Exercices progressifs",
                "Exercices courts",
                "Défis",
            ),
            default=("Exercices progressifs",),
        )
        error_help = st.radio(
            "Quand je fais une erreur",
            ("HINT_FIRST", "EXPLAIN_METHOD", "SHOW_CORRECTION"),
            format_func=ERROR_HELP_LABELS.__getitem__,
        )
        diagnostic = st.radio(
            "Diagnostic initial",
            ("TAKE", "SKIP"),
            format_func={"TAKE": "Faire le diagnostic", "SKIP": "Commencer sans diagnostic"}.__getitem__,
        )
        submitted = st.form_submit_button("Créer mon parcours", type="primary")

    if not submitted:
        return
    objectives = {
        "Préparer la classe suivante": ObjectiveKind.PREPARATION_NEXT_GRADE,
        "Révision globale": ObjectiveKind.REVISION,
        "Suivre les cours pendant l'année": ObjectiveKind.LONG_TERM_MASTERY,
        "Consolider mes faiblesses": ObjectiveKind.CONSOLIDATION,
        "Préparer un contrôle": ObjectiveKind.HOMEWORK,
        "Préparer un examen": ObjectiveKind.PREPARATION_BREVET,
        "Rattrapage / remédiation": ObjectiveKind.CATCH_UP,
        "Approfondissement": ObjectiveKind.LONG_TERM_MASTERY,
    }
    grade_by_id = {item[0]: GradeLevel(item[1], index + 1, item[2]) for index, item in enumerate(grades)}
    academic_year = _safe(lambda: parse_academic_year(school_year))
    if academic_year is None:
        return
    stable_profile = f"legacy-user:{user['id']}"
    request = OnboardingRequest(
        f"{stable_profile}:{school_year}:{objectives[objective_label].value}",
        LearnerProfile(stable_profile, first_name.strip(), CreatorRole.STUDENT, birth_date=birth_date),
        academic_year,
        grade_by_id[int(current_id)],
        LearnerGoalConfiguration(
            objectives[objective_label],
            grade_by_id[int(target_id)] if target_id is not None else None,
            "BREVET" if objective_label == "Préparer un examen" else None,
        ),
        tuple(SubjectPreference(int(subject_id), priority=True) for subject_id in selected_subjects),
        StudyPreferences(
            duration,
            tuple(AvailabilitySlot(day, duration, time(17)) for day in weekdays),
            difficulty=DifficultyPreference.STANDARD,
        ),
        CreatorRole.STUDENT,
    )
    result = _safe(lambda: OnboardingService(DuckDBOnboardingRepository()).complete(request))
    if result is None:
        return
    learner_id = int(result.learner_id)
    _safe(
        lambda: UnifiedOnboardingProfileService(repository).save(
            OnboardingProfileInput(
                learner_id,
                first_name,
                last_name or None,
                birth_date,
                school_year,
                "FR-NATIONAL",
                tuple(formats),
                error_help,
                diagnostic == "TAKE",
                email,
            )
        )
    )
    st.session_state.unified_learner_id = learner_id
    session_id = _safe(lambda: _create_initial_session(result))
    if session_id:
        st.session_state.v2_session_id = session_id
        st.success("Ton parcours et ta première séance personnalisée sont prêts.")
    else:
        st.warning("Ton parcours est prêt, mais aucun contenu approuvé compatible n'est disponible pour une séance.")
    st.rerun()


def _homework_form(
    learner_id: int,
    actor_type: str,
    actor_ref: str,
    key: str,
    modes: tuple[AssignmentType, ...] = (AssignmentType.TARGETED, AssignmentType.GLOBAL_SUBJECT),
) -> None:
    repository = _repository()
    service = _homework_service()
    availability_service = HomeworkAvailabilityService(repository)
    grade_id = repository.learner_grade_id(learner_id)
    grade_labels = {item[0]: item[2] for item in repository.grade_levels()}
    try:
        availability = {
            item.subject_id: item for item in availability_service.list_for_learner(learner_id)
        }
    except Exception:
        LOGGER.exception("Homework availability lookup failed for learner %s", learner_id)
        availability = {}
    subjects = repository.curriculum_subjects_for_grade(grade_id)
    labels = {item[0]: item[2] for item in subjects}
    if not subjects:
        grade_label = grade_labels.get(grade_id, "cette classe")
        st.info(f"Aucune matière configurée dans le curriculum pour {grade_label}.")
        return
    mode = st.selectbox(
        "Mode",
        modes,
        format_func={
            AssignmentType.TARGETED: "Devoir ciblé",
            AssignmentType.GLOBAL_SUBJECT: "Devoir global",
            AssignmentType.FREE_REVISION: "Révision libre",
        }.get,
        key=f"{key}_mode",
    )
    st.selectbox(
        "Classe",
        (grade_id,),
        format_func=lambda item: grade_labels.get(item, "Classe actuelle"),
        disabled=True,
        key=f"{key}_grade",
    )
    subject_options: list[int | None] = [None, *labels]
    subject_id = st.selectbox(
        "Matière",
        subject_options,
        format_func=lambda item: (
            "Sélectionner une matière"
            if item is None
            else f"{labels[item]} — {availability[item].homework_status_label}"
            if item in availability
            else labels[item]
        ),
        key=f"{key}_subject",
    )
    reconcile_subject_change(st.session_state, key, subject_id)
    if subject_id is None:
        st.info("Sélectionnez une matière pour afficher le contenu approuvé disponible.")
        return
    subject_availability = availability.get(int(subject_id))
    if subject_availability:
        ai_enabled = service.supports_ai_completion()
        status_messages = {
            "available": (
                f"**{subject_availability.homework_status_label}** — "
                f"{subject_availability.eligible_count} contenu(s) éligible(s) sur "
                f"{subject_availability.chapters_total} chapitre(s) du curriculum."
            ),
            "limited": (
                f"**{subject_availability.homework_status_label}** — "
                f"{subject_availability.eligible_count} contenu(s) du catalogue ; "
                "le complément IA pourra compléter automatiquement le devoir."
                if ai_enabled
                else (
                    f"**{subject_availability.homework_status_label}** — "
                    f"seulement {subject_availability.eligible_count} contenu(s) publié(s) ; "
                    "le devoir sera limité en taille."
                )
            ),
            "unavailable": (
                "Catalogue vide — le complément IA pourra générer l'ensemble des exercices demandés."
                if ai_enabled
                else f"**{subject_availability.homework_status_label}** — aucun contenu publié éligible pour cette matière."
            ),
        }
        st.caption(status_messages.get(subject_availability.availability_status, ""))
    if (
        subject_availability
        and subject_availability.availability_status == "unavailable"
        and not service.supports_ai_completion()
    ):
        st.warning(
            f"Aucun devoir ne peut être créé pour {labels[int(subject_id)]} tant qu'aucun contenu n'est publié."
        )
        return
    selected_chapters: list[int] = []
    selected_skills: list[int] = []
    if mode is AssignmentType.GLOBAL_SUBJECT:
        clear_curriculum_selection(st.session_state, key)
        available_chapters = repository.chapters(int(subject_id), grade_id)
        if not available_chapters:
            st.info(
                f"Le catalogue pédagogique ne contient pas encore de contenu approuvé pour "
                f"{labels[int(subject_id)]} dans cette classe."
            )
            return
        st.caption(f"Le devoir sera équilibré automatiquement sur {len(available_chapters)} chapitre(s) approuvé(s).")
    else:
        chapters = repository.chapters(int(subject_id), grade_id)
        chapter_labels = dict(chapters)
        selected_chapters = st.multiselect(
            "Chapitres",
            list(chapter_labels),
            format_func=chapter_labels.__getitem__,
            key=f"{key}_chapters",
        )
        skills = (
            repository.skills(
                int(subject_id),
                tuple(int(item) for item in selected_chapters),
                grade_id,
            )
            if selected_chapters
            else ()
        )
        skill_labels = dict(skills)
        reconcile_skills(st.session_state, key, set(skill_labels))
        selected_skills = st.multiselect(
            "Compétences",
            list(skill_labels),
            format_func=skill_labels.__getitem__,
            key=f"{key}_skills",
        )
        if not chapters:
            st.info(
                f"Le catalogue pédagogique ne contient pas encore de chapitre approuvé pour "
                f"{labels[int(subject_id)]} dans cette classe."
            )
            return
        if not selected_chapters and not selected_skills:
            st.info("Sélectionnez au moins un chapitre ou une compétence pour prévisualiser et créer le devoir.")
            return
    difficulty = st.selectbox(
        "Difficulté",
        tuple(DifficultyMode),
        format_func={
            DifficultyMode.EASY: "Facile",
            DifficultyMode.MEDIUM: "Moyen",
            DifficultyMode.HARD: "Difficile",
            DifficultyMode.ADAPTIVE: "Adaptatif",
        }.get,
        key=f"{key}_difficulty",
    )
    exercise_count = st.slider("Nombre d'exercices", 1, 40, 10, key=f"{key}_exercise_count")
    preview_request = HomeworkRequest(
        learner_id,
        actor_type,
        actor_ref,
        mode,
        int(subject_id),
        grade_id,
        tuple(int(item) for item in selected_chapters),
        tuple(int(item) for item in selected_skills),
        difficulty,
        40,
        None,
        None,
    )
    preview_selection = _homework_service().preview_selection(preview_request)
    available_total = len(preview_selection.content_ids)
    difficulty_labels = {
        DifficultyMode.EASY: "Facile",
        DifficultyMode.MEDIUM: "Moyen",
        DifficultyMode.HARD: "Difficile",
        DifficultyMode.ADAPTIVE: "Adaptatif",
    }
    if available_total == 0:
        if service.supports_ai_completion():
            st.info(
                f"Aucun contenu catalogue pour {labels[int(subject_id)]} avec ces critères. "
                f"Le complément IA générera les {exercise_count} exercice(s) demandés."
            )
        else:
            st.warning(
                f"Aucun contenu approuvé disponible pour {labels[int(subject_id)]} avec ces critères. "
                "Élargissez le chapitre ou choisissez une autre matière."
            )
    elif preview_selection.difficulty_relaxed:
        st.info(
            f"Cette matière contient {available_total} contenu(s) approuvé(s). "
            "Le devoir combinera plusieurs niveaux de difficulté adaptés à ton profil."
        )
    elif available_total < exercise_count:
        if service.supports_ai_completion():
            st.info(
                f"{available_total} exercice(s) du catalogue ; "
                f"le complément IA complétera automatiquement jusqu'à {exercise_count} exercices."
            )
        else:
            st.info(
                f"Seulement {available_total} contenu(s) approuvé(s) disponible(s) "
                f"pour {labels[int(subject_id)]}. Le devoir sera limité à ce maximum."
            )
    else:
        st.caption(f"{available_total} contenu(s) approuvé(s) disponible(s) pour cette sélection.")
    target_duration = st.slider("Durée cible", 5, 120, 30, 5, key=f"{key}_duration")
    due_date = st.date_input(
        "Échéance",
        value=date.today(),
        format="DD/MM/YYYY",
        key=f"{key}_due_date",
    )
    correction = st.selectbox(
        "Correction",
        ("IMMEDIATE", "AFTER_EACH_EXERCISE", "AFTER_SUBMISSION"),
        format_func={
            "IMMEDIATE": "Immédiate",
            "AFTER_EACH_EXERCISE": "Après chaque exercice",
            "AFTER_SUBMISSION": "À la fin",
        }.get,
        key=f"{key}_correction",
    )
    create = st.button(
        "Créer le devoir",
        type="primary",
        key=f"{key}_create",
        disabled=(
            (mode is not AssignmentType.GLOBAL_SUBJECT and not selected_chapters and not selected_skills)
            or (available_total == 0 and not service.supports_ai_completion())
        ),
    )
    if create:
        request = HomeworkRequest(
            learner_id,
            actor_type,
            actor_ref,
            mode,
            int(subject_id),
            grade_id,
            tuple(int(item) for item in selected_chapters),
            tuple(int(item) for item in selected_skills),
            difficulty,
            exercise_count,
            target_duration,
            datetime.combine(due_date, time(23, 59), tzinfo=UTC),
            correction,
        )
        with st.spinner("Création du devoir en cours…"):
            if service.supports_ai_completion():
                generation = _safe(
                    lambda: service.assign_as_parent_with_diagnostics(actor_ref, request)
                    if actor_type == "PARENT"
                    else service.create_with_diagnostics(request)
                )
                if generation:
                    _render_homework_creation_feedback(generation, exercise_count)
            else:
                result = _safe(
                    lambda: service.assign_as_parent(actor_ref, request)
                    if actor_type == "PARENT"
                    else service.create(request)
                )
                if result:
                    selection = service.preview_selection(request)
                    _render_homework_catalog_feedback(selection, len(result.selected_content_ids), exercise_count)


def _render_homework_catalog_feedback(selection, selected_count: int, exercise_count: int) -> None:
    if selection.difficulty_relaxed:
        st.info(
            "La difficulté demandée n'avait aucun contenu publié ; "
            "des contenus d'un niveau proche ont été utilisés."
        )
    if selected_count < exercise_count:
        st.warning(
            f"Le catalogue contient actuellement {selected_count} contenu(s) compatible(s). "
            f"Le devoir a été créé avec {selected_count} contenu(s) au lieu des {exercise_count} demandés."
        )
    else:
        st.success(f"Devoir créé avec {selected_count} contenu(s) approuvé(s).")


def _render_homework_creation_feedback(generation, exercise_count: int) -> None:
    from domain.unified_experience.models import HomeworkGenerationResult

    if not isinstance(generation, HomeworkGenerationResult):
        return
    catalog_count = generation.catalog_count
    ai_count = generation.ai_accepted_count
    final_count = generation.final_count
    if final_count == exercise_count:
        if ai_count:
            st.success(f"Le devoir de {exercise_count} questions a été créé.")
            st.caption(
                f"{catalog_count} exercice(s) issus du catalogue · "
                f"{ai_count} exercice(s) généré(s) par IA"
            )
        else:
            st.success(f"Le devoir de {exercise_count} questions a été créé.")
    elif final_count > 0:
        st.warning(
            f"Le devoir a été créé avec {final_count} exercice(s) sur {exercise_count} demandés "
            "(catalogue et complément IA insuffisants)."
        )
    if generation.degraded_mode and generation.degradation_reason:
        st.caption(f"Mode dégradé : {generation.degradation_reason}")


def student_homework(learner_id: int, user: dict[str, object]) -> None:
    from ui.student_guidance import (
        load_homework_result_explanation,
        render_homework_before_guidance,
        render_homework_result_explanation,
    )

    st.title("Mes devoirs")
    from services.professor_ai.guided_cycle import FOCUS_HOMEWORK_KEY

    focus_homework_id = st.session_state.pop(FOCUS_HOMEWORK_KEY, None)
    if focus_homework_id is not None:
        st.info(f"Le Professeur IA te propose de te concentrer sur le devoir n°{int(focus_homework_id)}.")
    service = _homework_service()
    tabs = st.tabs(("À faire", "En cours", "Terminés", "Créer"))
    groups = (
        {AssignmentStatus.DRAFT, AssignmentStatus.READY},
        {AssignmentStatus.IN_PROGRESS, AssignmentStatus.PAUSED},
        {AssignmentStatus.COMPLETED, AssignmentStatus.EXPIRED},
    )
    assignments = service.list_for_learner(learner_id)
    for tab, statuses in zip(tabs[:3], groups, strict=True):
        with tab:
            selected = [item for item in assignments if item.status in statuses]
            if not selected:
                st.info("Aucun devoir dans cette catégorie.")
            for item in selected:
                with st.container(border=True):
                    st.write(
                        f"**{item.subject_label}** · {item.exercise_count} exercice(s) · {label(item.difficulty.value)}"
                    )
                    st.caption(f"État : {label(item.status.value)}")
                    if item.status in {AssignmentStatus.READY, AssignmentStatus.IN_PROGRESS, AssignmentStatus.PAUSED}:
                        render_homework_before_guidance(user, learner_id, item.homework_id)
                    if item.status is AssignmentStatus.READY and st.button(
                        "Commencer", key=f"hw_start_{item.homework_id}"
                    ):
                        opened = _safe(
                            partial(_homework_sessions().open_for_learner, learner_id, item.homework_id, datetime.now(UTC))
                        )
                        if opened and opened.session_id:
                            st.session_state.v2_session_id = opened.session_id
                            from ui.professor_ai_guided_cycle import remember_session_status

                            remember_session_status(st.session_state, int(opened.session_id), "RUNNING")
                            request_navigation(st.session_state, "student", "Ma séance IA")
                            st.rerun()
                    if item.status is AssignmentStatus.IN_PROGRESS and st.button(
                        "Reprendre la séance", key=f"hw_resume_session_{item.homework_id}"
                    ):
                        opened = _safe(
                            partial(_homework_sessions().open_for_learner, learner_id, item.homework_id, datetime.now(UTC))
                        )
                        if opened and opened.session_id:
                            st.session_state.v2_session_id = opened.session_id
                            from ui.professor_ai_guided_cycle import remember_session_status

                            remember_session_status(st.session_state, int(opened.session_id), "RUNNING")
                            request_navigation(st.session_state, "student", "Ma séance IA")
                            st.rerun()
                    if item.status is AssignmentStatus.IN_PROGRESS and st.button(
                        "Mettre en pause", key=f"hw_pause_{item.homework_id}"
                    ):
                        _safe(partial(service.pause, learner_id, item.homework_id))
                        st.rerun()
                    if item.status is AssignmentStatus.PAUSED and st.button(
                        "Reprendre", key=f"hw_resume_{item.homework_id}"
                    ):
                        _safe(partial(service.resume, learner_id, item.homework_id))
                        st.rerun()
                    if item.status is AssignmentStatus.COMPLETED:
                        explanation = load_homework_result_explanation(user, learner_id, item.homework_id)
                        render_homework_result_explanation(explanation)
    with tabs[3]:
        _homework_form(learner_id, "STUDENT", f"learner:{learner_id}", "student_homework_form")


def revision(learner_id: int, user: dict[str, object]) -> None:
    from ui.student_guidance import load_revision_guidance

    st.title("Révision libre")
    guidance = load_revision_guidance(user, learner_id)
    with st.container(border=True):
        st.subheader("Recommandation du Professeur IA", anchor=False)
        st.write(guidance.message)
        if guidance.degraded_notice:
            st.caption(guidance.degraded_notice)
    st.write(
        "Choisis une matière et un chapitre. Les résultats utiliseront le même moteur de maîtrise que les séances."
    )
    _homework_form(
        learner_id,
        "STUDENT",
        f"learner:{learner_id}",
        "revision_form",
        (AssignmentType.FREE_REVISION,),
    )


def coach_view(dashboard: StudentDashboard) -> None:
    st.title("Mon Coach d'apprentissage")
    advice = DeterministicCoachService().advice(dashboard.mastery)
    if not advice:
        st.info("Il faut davantage d'activités évaluées pour produire un conseil fondé.")
    for item in advice:
        with st.container(border=True):
            st.subheader(item.title)
            st.write(item.summary)
            st.caption(f"Pourquoi : {', '.join(item.reason_codes)}")
            st.write(f"Bénéfice attendu : {item.expected_benefit}")


def run_student(user: dict[str, object], learner_id: int) -> None:
    controller = build_student_experience_controller()
    pages = ("Tableau de bord", "Ma séance IA", "Mon professeur IA", "Devoirs", "Révision", "Mes progrès", "Mes résultats", "Mon planning", "Profil")
    if st.session_state.get("unified_student_page") == "Accueil":
        st.session_state["unified_student_page"] = "Tableau de bord"
    apply_navigation_request(st.session_state, "student", "unified_student_page", pages)
    with st.sidebar:
        st.success(f"Élève : {user['name']}")
        page = st.radio("Navigation", pages, key="unified_student_page")
        st.button("Déconnexion", on_click=logout)
    from ui.professor_ai_banner import render_professor_ai_banner

    actor = dict(user)
    actor["resolved_learner_id"] = learner_id
    render_professor_ai_banner(user=actor, learner_id=learner_id)
    dashboard = controller.dashboard(learner_id)
    if page == "Tableau de bord":
        from ui.student_guidance import load_student_dashboard_snapshot, render_mastery_bands, render_professor_ia_card

        snapshot = load_student_dashboard_snapshot(user, learner_id)
        render_professor_ia_card(snapshot)
        student_dashboard(controller, learner_id)
        render_mastery_bands(snapshot)
        if isinstance(dashboard, StudentDashboard):
            coach_view(dashboard)
    elif page == "Ma séance IA":
        session_screen(controller, learner_id, user=user)
    elif page == "Mon professeur IA":
        teacher_service, preferences_service = _virtual_teacher_services()
        profile = _safe(lambda: _repository().learner_management_profile(learner_id))
        grade_label = None
        if profile is not None:
            grades = {item[0]: item[2] for item in _repository().grade_levels()}
            grade_label = grades.get(profile.current_grade_id)
        render_student_virtual_teacher(
            user=user,
            learner_id=learner_id,
            teacher_service=teacher_service,
            preferences_service=preferences_service,
            learner_display_name=profile.first_name if profile else str(user["name"]),
            grade_label=grade_label,
        )
    elif page == "Devoirs":
        student_homework(learner_id, user)
    elif page == "Révision":
        revision(learner_id, user)
    elif page == "Mes progrès":
        if isinstance(dashboard, StudentDashboard):
            coach_view(dashboard)
    elif page == "Mes résultats":
        student_history(controller, learner_id)
        student_summary(controller, learner_id)
    elif page == "Mon planning":
        st.title("Mon planning")
        assignments = _homework_service().list_for_learner(learner_id)
        due = [
            item
            for item in assignments
            if item.due_at and item.status not in {AssignmentStatus.COMPLETED, AssignmentStatus.CANCELLED}
        ]
        if due:
            st.dataframe(
                [
                    {"Matière": item.subject_label, "Échéance": item.due_at, "État": label(item.status.value)}
                    for item in due
                ],
                hide_index=True,
            )
        else:
            st.info("Aucune échéance de devoir.")
    else:
        st.title("Mon profil")
        st.write(f"Identifiant apprenant : {learner_id}")
        st.write(f"Objectif : {dashboard.objective if isinstance(dashboard, StudentDashboard) else 'Indisponible'}")


def _render_child_management_back() -> None:
    if st.button("← Retour à la liste des enfants", key="child_management_back"):
        st.session_state.pop("manage_learner_action", None)
        st.rerun()


def _view_learner(user: dict[str, object], parent_ref: str, learner_id: int) -> None:
    repository = _repository()
    manager = LearnerProfileManagementService(repository)
    controller = build_parent_experience_controller()
    _, preferences_service = _virtual_teacher_services()
    render_parent_learner_sheet(
        user=user,
        parent_ref=parent_ref,
        learner_id=learner_id,
        profile_manager=manager,
        repository=repository,
        controller=controller,
        objective_labels=OBJECTIVE_LABELS,
        error_help_labels=ERROR_HELP_LABELS,
        on_back=_render_child_management_back,
        render_virtual_teacher=lambda: render_parent_virtual_teacher_settings(
            user=user,
            parent_ref=parent_ref,
            learner_id=learner_id,
            learner_label=str(
                _safe(lambda: manager.get(parent_ref, learner_id).first_name) or "Élève"
            ),
            preferences_service=preferences_service,
        ),
        render_homework_form=lambda: _homework_form(
            learner_id,
            "PARENT",
            parent_ref,
            f"sheet_homework_{learner_id}",
        ),
        safe=_safe,
    )


def _ai_profile_learner(user: dict[str, object], parent_ref: str, learner_id: int) -> None:
    manager = LearnerProfileManagementService(_repository())
    profile = _safe(lambda: manager.get(parent_ref, learner_id))
    if profile is None:
        return
    _render_child_management_back()
    _, preferences_service = _virtual_teacher_services()
    render_parent_virtual_teacher_settings(
        user=user,
        parent_ref=parent_ref,
        learner_id=learner_id,
        learner_label=profile.first_name,
        preferences_service=preferences_service,
    )


def _edit_learner(parent_ref: str, learner_id: int) -> None:
    repository = _repository()
    manager = LearnerProfileManagementService(repository)
    profile = _safe(lambda: manager.get(parent_ref, learner_id))
    if profile is None:
        return
    grades = repository.grade_levels()
    grade_labels = {item[0]: item[2] for item in grades}
    grade_by_id = {item[0]: GradeLevel(item[1], index + 1, item[2]) for index, item in enumerate(grades)}
    subjects = repository.reference_subjects()
    subject_labels = {item[0]: item[2] for item in subjects}
    objective_labels = {
        ObjectiveKind.PREPARATION_NEXT_GRADE: "Préparer la classe suivante",
        ObjectiveKind.REVISION: "Révision globale",
        ObjectiveKind.LONG_TERM_MASTERY: "Suivre les cours pendant l'année",
        ObjectiveKind.CONSOLIDATION: "Consolider les faiblesses",
        ObjectiveKind.HOMEWORK: "Préparer un contrôle",
        ObjectiveKind.CATCH_UP: "Rattrapage / remédiation",
    }
    objective_values = tuple(objective_labels)
    current_objective = ObjectiveKind(profile.objective)
    if current_objective not in objective_values:
        objective_values = (*objective_values, current_objective)

    _render_child_management_back()
    st.subheader(f"Modifier le profil de {profile.first_name}")
    with st.form(f"edit_learner_{learner_id}"):
        names = st.columns(2)
        first_name = names[0].text_input("Prénom", value=profile.first_name)
        last_name = names[1].text_input("Nom", value=profile.last_name or "")
        email = st.text_input(
            "Adresse e-mail du compte Élève",
            value=profile.email or "",
            disabled=True,
            help="La modification de l'identité de connexion sera proposée dans une évolution dédiée.",
        )
        birth_date = st.date_input(
            "Date de naissance",
            value=profile.birth_date,
            min_value=date(date.today().year - 30, 1, 1),
            max_value=date(date.today().year - 5, 12, 31),
            format="DD/MM/YYYY",
        )
        current_grade = st.selectbox(
            "Classe actuelle",
            list(grade_labels),
            index=list(grade_labels).index(profile.current_grade_id),
            format_func=grade_labels.__getitem__,
        )
        target_choices: list[int | None] = [None, *grade_labels]
        target_grade = st.selectbox(
            "Classe cible",
            target_choices,
            index=target_choices.index(profile.target_grade_id),
            format_func=lambda item: "Aucune" if item is None else grade_labels[item],
        )
        year_options = academic_year_options(date.today())
        if profile.school_year not in year_options:
            year_options = (*year_options, profile.school_year)
        school_year = st.selectbox(
            "Année scolaire",
            year_options,
            index=year_options.index(profile.school_year),
        )
        objective = st.selectbox(
            "Objectif pédagogique",
            objective_values,
            index=objective_values.index(current_objective),
            format_func=lambda item: objective_labels.get(item, item.value),
        )
        selected_subjects = st.multiselect(
            "Matières",
            list(subject_labels),
            default=[item for item in profile.subject_ids if item in subject_labels],
            format_func=subject_labels.__getitem__,
        )
        duration = st.slider("Temps d'étude quotidien", 10, 120, profile.daily_duration_minutes, 5)
        weekdays = st.multiselect(
            "Jours d'étude",
            list(range(7)),
            default=[item[0] for item in profile.availability],
            format_func=lambda day: ("Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche")[day],
        )
        formats = st.multiselect(
            "Préférences pédagogiques",
            (
                "Exemples avant les exercices",
                "Explications détaillées",
                "Exercices progressifs",
                "Exercices courts",
                "Défis",
            ),
            default=profile.preferred_formats,
        )
        error_help = st.selectbox(
            "Aide en cas d'erreur",
            ("HINT_FIRST", "EXPLAIN_METHOD", "SHOW_CORRECTION"),
            index=("HINT_FIRST", "EXPLAIN_METHOD", "SHOW_CORRECTION").index(profile.error_help_preference),
            format_func=ERROR_HELP_LABELS.__getitem__,
        )
        submitted = st.form_submit_button("Enregistrer les modifications", type="primary")
    if not submitted:
        return
    academic_year = _safe(lambda: parse_academic_year(school_year))
    if academic_year is None:
        return
    request = OnboardingRequest(
        f"profile-edit:{learner_id}:{datetime.now(UTC).isoformat()}",
        LearnerProfile(
            profile.external_ref,
            first_name.strip(),
            CreatorRole.PARENT,
            birth_date=birth_date,
            learner_id=learner_id,
        ),
        academic_year,
        grade_by_id[int(current_grade)],
        LearnerGoalConfiguration(
            objective,
            grade_by_id[int(target_grade)] if target_grade is not None else None,
        ),
        tuple(SubjectPreference(int(subject_id), priority=True) for subject_id in selected_subjects),
        StudyPreferences(
            duration,
            tuple(AvailabilitySlot(day, duration, time(17)) for day in weekdays),
            difficulty=DifficultyPreference.STANDARD,
        ),
        CreatorRole.PARENT,
        "parent_profile_edit",
    )
    experience_profile = OnboardingProfileInput(
        learner_id,
        first_name,
        last_name or None,
        birth_date,
        school_year,
        "FR-NATIONAL",
        tuple(formats),
        error_help,
        profile.diagnostic_status == "PLANNED",
        profile.email,
    )
    result = _safe(
        lambda: manager.update(
            parent_ref,
            request,
            experience_profile,
            OnboardingService(DuckDBOnboardingRepository()),
            UnifiedOnboardingProfileService(repository),
        )
    )
    if result is None:
        return
    _safe(lambda: _create_initial_session(result))
    st.success("Le profil, le parcours et les recommandations ont été mis à jour.")
    st.session_state.pop("manage_learner_action", None)
    st.rerun()


def _reset_student_password(parent_ref: str, learner_id: int) -> None:
    manager = LearnerProfileManagementService(_repository())
    profile = _safe(lambda: manager.get(parent_ref, learner_id))
    if profile is None:
        return
    _render_child_management_back()
    st.warning(f"Définir un nouveau mot de passe pour {profile.first_name}.")
    with st.form(f"reset_student_password_{learner_id}"):
        password = st.text_input("Nouveau mot de passe", type="password")
        confirmation = st.text_input("Confirmer le nouveau mot de passe", type="password")
        confirmed = st.checkbox(f"Je confirme la réinitialisation pour {profile.first_name}.")
        submitted = st.form_submit_button(
            "Réinitialiser le mot de passe",
            type="primary",
        )
    if not submitted:
        return
    if not confirmed:
        st.error("Confirmez la réinitialisation du mot de passe de l'élève.")
        return
    ok, message = reset_student_password(int(parent_ref), profile.external_ref, password, confirmation)
    if ok:
        st.session_state.pop("manage_learner_action", None)
        st.success(message)
        st.rerun()
    st.error(message)


def _create_orphan_student_account(parent_ref: str, learner_id: int) -> None:
    manager = LearnerProfileManagementService(_repository())
    profile = _safe(lambda: manager.get(parent_ref, learner_id))
    if profile is None:
        return
    existing = student_account_for_learner(profile.external_ref)
    if existing is not None:
        st.info("Un compte élève est déjà associé à ce profil.")
        return
    _render_child_management_back()
    st.warning(f"Créer le compte de connexion manquant pour {profile.first_name}.")
    with st.form(f"repair_student_account_{learner_id}"):
        username = st.text_input("Identifiant")
        email = st.text_input("Adresse e-mail")
        password = st.text_input("Mot de passe", type="password")
        confirmation = st.text_input("Confirmer le mot de passe", type="password")
        submitted = st.form_submit_button("Créer le compte élève", type="primary")
    if not submitted:
        return
    ok, message = create_student_account(
        int(parent_ref),
        profile.external_ref,
        profile.first_name,
        email,
        username,
        password,
        confirmation,
    )
    if ok and has_active_student_account(profile.external_ref):
        st.session_state.pop("manage_learner_action", None)
        st.success("Le compte élève a été créé. L'élève peut maintenant se connecter directement.")
        st.rerun()
    st.error(message if not ok else "Le lien avec le compte élève n'a pas pu être vérifié.")


def _delete_learner(parent_ref: str, learner_id: int) -> None:
    manager = LearnerProfileManagementService(_repository())
    profile = _safe(lambda: manager.get(parent_ref, learner_id))
    if profile is None:
        return
    _render_child_management_back()
    st.error(f"Supprimer {profile.first_name} ? Cette suppression est définitive.")
    understood = st.checkbox(
        "Je comprends que le profil et toutes les données d'apprentissage associées seront supprimés.",
        key=f"delete_understood_{learner_id}",
    )
    confirmation = st.text_input(
        "Saisissez exactement le prénom pour confirmer",
        key=f"delete_confirmation_{learner_id}",
    )
    cancel, remove = st.columns(2)
    if cancel.button("Annuler", key=f"delete_cancel_{learner_id}"):
        st.session_state.pop("manage_learner_action", None)
        st.rerun()
    if remove.button(
        "Supprimer l'élève",
        type="primary",
        disabled=not understood,
        key=f"delete_confirm_{learner_id}",
    ):

        def delete_confirmed() -> bool:
            deactivate_student_account(int(parent_ref), profile.external_ref)
            try:
                manager.delete(parent_ref, learner_id, confirmation, understood)
            except Exception:
                reactivate_student_account(int(parent_ref), profile.external_ref)
                raise
            delete_student_account(int(parent_ref), profile.external_ref)
            return True

        result = _safe(delete_confirmed)
        if result:
            st.session_state.pop("manage_learner_action", None)
            st.success("L'élève et toutes ses données associées ont été supprimés.")
            st.rerun()



def _archive_learner(parent_ref: str, learner_id: int) -> None:
    manager = LearnerProfileManagementService(_repository())
    profile = _safe(lambda: manager.get(parent_ref, learner_id))
    if profile is None:
        return
    _render_child_management_back()
    st.warning(
        f"Archiver {profile.first_name} ? L'élève ne pourra plus se connecter, "
        "mais ses données seront conservées et pourront être restaurées."
    )
    understood = st.checkbox(
        "Je comprends que le compte élève sera désactivé.",
        key=f"archive_understood_{learner_id}",
    )
    if st.button("Annuler", key=f"archive_cancel_{learner_id}"):
        st.session_state.pop("manage_learner_action", None)
        st.rerun()
    if st.button(
        "Archiver l'élève",
        type="primary",
        disabled=not understood,
        key=f"archive_confirm_{learner_id}",
    ):
        result = _safe(lambda: _family_service().archive(parent_ref, learner_id, int(parent_ref)))
        if result is not None:
            st.session_state.pop("manage_learner_action", None)
            st.success(f"{profile.first_name} a été archivé.")
            st.rerun()


def _restore_learner(parent_ref: str, learner_id: int) -> None:
    family = _family_service()
    if st.button("Restaurer", key=f"restore_learner_{learner_id}"):
        result = _safe(lambda: family.restore(parent_ref, learner_id))
        if result is not None:
            st.success("L'élève a été restauré. Réactivez le compte si nécessaire depuis la fiche.")
            st.rerun()


def _render_family_diagnostic(parent_ref: str) -> None:
    diagnostic = _family_diagnostic_service()
    issues = diagnostic.scan_for_parent(parent_ref)
    if not issues:
        return
    with st.expander("Diagnostic famille", expanded=False):
        st.caption("Des incohérences ont été détectées dans vos données familiales.")
        for issue in issues:
            st.write(f"**{issue.learner_name}** — {issue.message}")
            if st.button("Réparer", key=f"repair_{issue.code}_{issue.learner_id}") and _safe(
                partial(diagnostic.repair, parent_ref, issue)
            ):
                st.success("Réparation effectuée.")
                st.rerun()



def _create_child(parent_ref: str, *, prominent: bool = False, user: dict[str, object] | None = None) -> None:
    repository = _repository()
    grades = repository.grade_levels()
    subjects = repository.reference_subjects()
    grade_labels = {item[0]: item[2] for item in grades}
    subject_labels = {item[0]: item[2] for item in subjects}
    grade_by_id = {item[0]: GradeLevel(item[1], index + 1, item[2]) for index, item in enumerate(grades)}
    objectives = _child_creation_objectives()
    if user is None:
        user = {"id": parent_ref, "name": "Parent", "role": "parent"}
    render_child_creation_wizard(
        parent_ref=parent_ref,
        user=user,
        repository=repository,
        grade_labels=grade_labels,
        subject_labels=subject_labels,
        grade_by_id=grade_by_id,
        objectives=objectives,
        error_help_labels=ERROR_HELP_LABELS,
        submit_child=_submit_child_from_wizard,
    )


def _children_management(
    user: dict[str, object],
    parent_ref: str,
    learners: tuple[tuple[int, str], ...],
    *,
    prominent: bool = False,
) -> None:
    st.title("Mes enfants")
    created_name = st.session_state.pop("parent_child_created_flash", None)
    if created_name:
        st.success(
            f"Le compte de {created_name} a été créé. L'élève peut maintenant se connecter directement."
        )
    st.markdown(f"Bonjour **{user.get('name', 'Parent')}**")
    st.caption("Gérez les comptes élèves, leurs profils pédagogiques et le professeur virtuel.")
    active_action = st.session_state.get("manage_learner_action")
    if not learners:
        st.info(
            "Aucun compte élève n'est encore rattaché à votre espace familial. "
            "Utilisez l'assistant ci-dessous pour en créer un."
        )
    if not active_action:
        show_wizard = prominent or bool(st.session_state.get("parent_show_child_wizard"))
        if show_wizard:
            if prominent:
                st.subheader("Créer un compte élève")
            _create_child(parent_ref, prominent=prominent, user=user)
        elif st.button("+ Ajouter un enfant", key="parent_add_child", type="primary"):
            st.session_state.parent_show_child_wizard = True
            st.session_state.parent_child_wizard_step = 1
            st.rerun()
    manager = LearnerProfileManagementService(_repository())
    if learners and not active_action:
        st.subheader("Enfants rattachés")
    for learner_id, _ in learners:
        if active_action and int(active_action[1]) != learner_id:
            continue
        profile = _safe(partial(manager.get, parent_ref, learner_id))
        if profile is None:
            continue
        if active_action:
            continue
        with st.container(border=True):
            st.subheader(profile.first_name)
            grade = dict((item[0], item[2]) for item in _repository().grade_levels()).get(
                profile.current_grade_id, "Classe inconnue"
            )
            st.write(f"{profile.age if profile.age is not None else 'Âge inconnu'} ans • {grade}")
            st.caption(f"Préparation : {OBJECTIVE_LABELS.get(profile.objective, 'Parcours personnalisé')}")
            account = student_account_for_learner(profile.external_ref)
            if account and account["active"]:
                st.success("Compte élève : Actif")
                st.caption(f"Identifiant : {account['username']}")
            else:
                st.warning("Compte élève : Non configuré")
                if st.button("Créer le compte élève", key=f"repair_account_{learner_id}"):
                    st.session_state.manage_learner_action = ("account", learner_id)
                    st.rerun()
            st.caption(f"Professeur IA : {_virtual_teacher_status_label(learner_id)}")
            last_activity = _family_service().learner_last_activity(learner_id)
            st.caption(
                f"Dernière activité : {last_activity}" if last_activity else "Dernière activité : Aucune activité"
            )
            st.markdown("##### Actions")
            action_cols = st.columns(4)
            if action_cols[0].button("Ouvrir", key=f"child_view_{learner_id}", use_container_width=True):
                st.session_state.manage_learner_action = ("view", learner_id)
                st.rerun()
            if action_cols[1].button("Modifier", key=f"child_edit_{learner_id}", use_container_width=True):
                st.session_state.manage_learner_action = ("edit", learner_id)
                st.rerun()
            if action_cols[2].button("Professeur IA", key=f"child_ai_{learner_id}", use_container_width=True):
                st.session_state.manage_learner_action = ("ai_profile", learner_id)
                st.rerun()
            with action_cols[3].popover("Plus d'actions", use_container_width=True):
                if st.button("Mot de passe", key=f"child_password_{learner_id}", use_container_width=True):
                    st.session_state.manage_learner_action = ("password", learner_id)
                    st.rerun()
                if st.button("Archiver", key=f"child_archive_{learner_id}", use_container_width=True):
                    st.session_state.manage_learner_action = ("archive", learner_id)
                    st.rerun()
                if st.button("Supprimer", key=f"child_delete_{learner_id}", use_container_width=True):
                    st.session_state.manage_learner_action = ("delete", learner_id)
                    st.rerun()
    if active_action:
        if active_action[0] == "view":
            _view_learner(user, parent_ref, int(active_action[1]))
        elif active_action[0] == "edit":
            _edit_learner(parent_ref, int(active_action[1]))
        elif active_action[0] == "ai_profile":
            _ai_profile_learner(user, parent_ref, int(active_action[1]))
        elif active_action[0] == "delete":
            _delete_learner(parent_ref, int(active_action[1]))
        elif active_action[0] == "password":
            _reset_student_password(parent_ref, int(active_action[1]))
        elif active_action[0] == "account":
            _create_orphan_student_account(parent_ref, int(active_action[1]))
        elif active_action[0] == "archive":
            _archive_learner(parent_ref, int(active_action[1]))
    if not active_action:
        _render_family_diagnostic(parent_ref)
        archived = _family_service().list_archived_learners(parent_ref)
        if archived:
            st.subheader("Élèves archivés")
            for archived_id, archived_name in archived:
                with st.container(border=True):
                    st.write(f"**{archived_name}** (archivé)")
                    _restore_learner(parent_ref, archived_id)


def run_parent(user: dict[str, object]) -> None:
    controller = build_parent_experience_controller()
    parent_ref = parent_ref_from_user(user)
    try:
        learners = controller.learners(parent_ref)
    except Exception:
        LOGGER.exception("Failed to load parent learners for %s", parent_ref)
        st.error(
            "Impossible de charger la liste de vos enfants pour le moment. "
            "Réessayez dans quelques instants ou contactez le support si le problème persiste."
        )
        learners = ()
    pages = (
        "Mes enfants",
        "Tableau de bord",
        "Progression",
        "Devoirs",
        "Recommandations",
        "Programme",
        "Planning",
        "Profil élève",
    )
    apply_navigation_request(st.session_state, "parent", "parent_page", pages)
    with st.sidebar:
        st.success("Espace parent")
        page = st.radio(
            "Navigation",
            pages,
            key="parent_page",
        )
        if not learners:
            st.caption("Commencez par créer un compte élève dans « Mes enfants ».")
        st.button("Déconnexion", on_click=logout)
    if not learners:
        if page != "Mes enfants":
            st.info(
                "Aucun compte élève n'est encore rattaché à votre espace familial. "
                "Créez un premier compte depuis « Mes enfants »."
            )
            if st.button("Aller à Mes enfants", key="parent_go_children"):
                st.session_state.parent_page = "Mes enfants"
                st.rerun()
            return
        _children_management(user, parent_ref, (), prominent=True)
        return
    if page == "Mes enfants":
        _children_management(user, parent_ref, learners)
        return
    labels = dict(learners)
    selected = st.session_state.get("parent_selected_learner")
    options = list(labels)
    learner_id = int(
        st.selectbox(
            "Élève",
            options,
            index=options.index(selected) if selected in options else 0,
            format_func=labels.__getitem__,
        )
    )
    if page in {"Tableau de bord", "Progression", "Recommandations"}:
        parent_dashboard(controller, parent_ref, learner_id)
    elif page == "Devoirs":
        st.title("Assigner un devoir")
        _homework_form(learner_id, "PARENT", parent_ref, "parent_homework_form")
        st.subheader("Devoirs de l'élève")
        items = _homework_service().list_for_learner(learner_id)
        st.dataframe(
            [
                {"Matière": item.subject_label, "État": label(item.status.value), "Échéance": item.due_at}
                for item in items
            ],
            hide_index=True,
        )
    elif page == "Programme":
        st.title("Propositions de programme")
        changes = _safe(lambda: ProgrammeChangeService(_repository()).list_for_parent(parent_ref, learner_id)) or ()
        if not changes:
            st.info("Aucune modification majeure en attente.")
        for change in changes:
            with st.container(border=True):
                st.write(f"**{change.change_type}** · niveau {change.level} · {change.status}")
                st.write(f"Pourquoi : {', '.join(change.reason_codes)}")
                st.write(f"Bénéfice attendu : {change.expected_benefit}")
                if change.status == "PENDING_PARENT":
                    cols = st.columns(3)
                    for column, decision, action_label in zip(
                        cols, ("accept", "modify", "reject"), ("Accepter", "Modifier", "Refuser"), strict=True
                    ):
                        if column.button(action_label, key=f"change_{change.proposal_id}_{decision}"):
                            service = ProgrammeChangeService(_repository())
                            _safe(partial(service.decide, parent_ref, change.proposal_id, decision))
                            st.rerun()
    elif page == "Planning":
        st.title("Planning et échéances")
        items = _homework_service().list_for_learner(learner_id)
        st.dataframe(
            [
                {"Matière": item.subject_label, "Échéance": item.due_at, "État": label(item.status.value)}
                for item in items
            ],
            hide_index=True,
        )
    elif page == "Profil élève":
        st.title(labels[learner_id])
        parent_dashboard(controller, parent_ref, learner_id)


def run_unified_app(login_renderer: LoginRenderer) -> None:
    if not st.session_state.user:
        login_renderer()
        return
    user = st.session_state.user
    from core.database import session_user_still_valid
    from ui.session import logout

    if not session_user_still_valid(user):
        logout()
        st.warning("Votre session a expiré après un changement de mot de passe. Veuillez vous reconnecter.")
        login_renderer()
        return
    from services.auth.roles import AuthRole, normalize_auth_role

    auth_role = normalize_auth_role(user.get("role"))
    if auth_role is AuthRole.PARENT:
        run_parent(user)
        return
    if auth_role is AuthRole.STUDENT:
        learner_id = _learner_id(user)
        if learner_id is None or not _repository().onboarding_complete(learner_id):
            onboarding(user)
            return
        run_student(user, learner_id)
        return
    logout()
    st.error("Ce type de compte n'est pas pris en charge.")
    login_renderer()
