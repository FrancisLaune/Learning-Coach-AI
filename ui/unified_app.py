"""Unified role-aware V2 Streamlit shell for students and parents."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, time
from functools import partial
from uuid import uuid4

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
from services.academic_year import academic_year_options, default_academic_year, parse_academic_year
from services.learning_session.experience import StudentDashboard
from services.learning_session.orchestration import LearningSessionService
from services.onboarding import OnboardingService, OnboardingValidationError
from services.recommendation import PersonalizedSessionService
from services.unified_experience import (
    DeterministicCoachService,
    HomeworkService,
    HomeworkSessionService,
    LearnerProfileManagementService,
    OnboardingProfileInput,
    ProgrammeChangeService,
    UnifiedOnboardingProfileService,
)
from ui.curriculum_state import clear_curriculum_selection, reconcile_skills, reconcile_subject_change
from ui.i18n import label
from ui.navigation import apply_navigation_request, request_navigation
from ui.session import logout
from ui.v2_experience import (
    parent_dashboard,
    session_screen,
    student_dashboard,
    student_history,
    student_summary,
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


def _repository() -> DuckDBUnifiedExperienceRepository:
    return DuckDBUnifiedExperienceRepository()


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


def _learner_id(user: dict[str, object]) -> int | None:
    cached = st.session_state.get("unified_learner_id")
    if cached:
        return int(cached)
    external_ref = user.get("learner_external_ref") or f"legacy-user:{user['id']}"
    learner_id = _repository().learner_for_external_ref(str(external_ref))
    if learner_id:
        st.session_state.unified_learner_id = learner_id
    return learner_id


def _safe[T](operation: Callable[[], T]) -> T | None:
    try:
        return operation()
    except (ValueError, PermissionError, OnboardingValidationError) as exc:
        st.error(str(exc))
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
    service = HomeworkService(repository)
    grade_id = repository.learner_grade_id(learner_id)
    grade_labels = {item[0]: item[2] for item in repository.grade_levels()}
    subjects = repository.subjects_for_grade(grade_id)
    labels = {item[0]: item[2] for item in subjects}
    if not subjects:
        grade_label = grade_labels.get(grade_id, "cette classe")
        st.info(f"Le catalogue pédagogique ne contient pas encore de contenu approuvé pour {grade_label}.")
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
        format_func=lambda item: "Sélectionner une matière" if item is None else labels[item],
        key=f"{key}_subject",
    )
    reconcile_subject_change(st.session_state, key, subject_id)
    if subject_id is None:
        st.info("Sélectionnez une matière pour afficher le contenu approuvé disponible.")
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
        disabled=mode is not AssignmentType.GLOBAL_SUBJECT and not selected_chapters,
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
        result = _safe(
            lambda: service.assign_as_parent(actor_ref, request) if actor_type == "PARENT" else service.create(request)
        )
        if result:
            selected_count = len(result.selected_content_ids)
            if selected_count < exercise_count:
                st.warning(
                    f"Le catalogue contient actuellement {selected_count} contenu(s) compatible(s). "
                    f"Le devoir a été créé avec {selected_count} contenu(s) au lieu des {exercise_count} demandés."
                )
            else:
                st.success(f"Devoir créé avec {selected_count} contenu(s) approuvé(s).")


def student_homework(learner_id: int) -> None:
    st.title("Mes devoirs")
    service = HomeworkService(_repository())
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
                    if item.status is AssignmentStatus.READY and st.button(
                        "Commencer", key=f"hw_start_{item.homework_id}"
                    ):
                        materialized = _safe(
                            partial(_homework_sessions().materialize, learner_id, item.homework_id, datetime.now(UTC))
                        )
                        if materialized and materialized.session_id:
                            st.session_state.v2_session_id = materialized.session_id
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
    with tabs[3]:
        _homework_form(learner_id, "STUDENT", f"learner:{learner_id}", "student_homework_form")


def revision(learner_id: int) -> None:
    st.title("Révision libre")
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
    pages = ("Accueil", "Ma séance IA", "Devoirs", "Révision", "Mes progrès", "Mes résultats", "Mon planning", "Profil")
    apply_navigation_request(st.session_state, "student", "unified_student_page", pages)
    with st.sidebar:
        st.success(f"Élève : {user['name']}")
        page = st.radio("Navigation", pages, key="unified_student_page")
        st.button("Déconnexion", on_click=logout)
    dashboard = controller.dashboard(learner_id)
    if page == "Accueil":
        student_dashboard(controller, learner_id)
        if isinstance(dashboard, StudentDashboard):
            coach_view(dashboard)
    elif page == "Ma séance IA":
        session_screen(controller, learner_id)
    elif page == "Devoirs":
        student_homework(learner_id)
    elif page == "Révision":
        revision(learner_id)
    elif page == "Mes progrès":
        if isinstance(dashboard, StudentDashboard):
            coach_view(dashboard)
    elif page == "Mes résultats":
        student_history(controller, learner_id)
        student_summary(controller, learner_id)
    elif page == "Mon planning":
        st.title("Mon planning")
        assignments = HomeworkService(_repository()).list_for_learner(learner_id)
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
        email,
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


def _create_child(parent_ref: str) -> None:
    repository = _repository()
    grades = repository.grade_levels()
    subjects = repository.reference_subjects()
    grade_labels = {item[0]: item[2] for item in grades}
    subject_labels = {item[0]: item[2] for item in subjects}
    grade_by_id = {item[0]: GradeLevel(item[1], index + 1, item[2]) for index, item in enumerate(grades)}
    objectives = {
        "Préparer la classe suivante": ObjectiveKind.PREPARATION_NEXT_GRADE,
        "Révision globale": ObjectiveKind.REVISION,
        "Suivre les cours pendant l'année": ObjectiveKind.LONG_TERM_MASTERY,
        "Consolider les faiblesses": ObjectiveKind.CONSOLIDATION,
        "Préparer un contrôle": ObjectiveKind.HOMEWORK,
        "Préparer un examen": ObjectiveKind.PREPARATION_BREVET,
        "Rattrapage / remédiation": ObjectiveKind.CATCH_UP,
        "Approfondissement": ObjectiveKind.LONG_TERM_MASTERY,
    }
    with (
        st.expander("Ajouter un élève", expanded=not bool(st.session_state.get("manage_learner_action"))),
        st.form("parent_create_child"),
    ):
        st.markdown("#### Compte de connexion de l'élève")
        names = st.columns(2)
        first_name = names[0].text_input("Prénom de l'élève")
        last_name = names[1].text_input("Nom de l'élève")
        student_username = st.text_input("Identifiant de connexion de l'élève")
        email = st.text_input("Adresse e-mail de l'élève")
        credentials = st.columns(2)
        student_password = credentials[0].text_input(
            "Mot de passe de l'élève",
            type="password",
        )
        student_password_confirmation = credentials[1].text_input(
            "Confirmer le mot de passe de l'élève",
            type="password",
        )
        st.markdown("#### Profil pédagogique")
        birth_date = st.date_input(
            "Date de naissance",
            value=date(2012, 1, 1),
            min_value=date(date.today().year - 30, 1, 1),
            max_value=date(date.today().year - 5, 12, 31),
            format="DD/MM/YYYY",
        )
        current_grade = st.selectbox("Classe actuelle", list(grade_labels), format_func=grade_labels.__getitem__)
        target_choices: list[int | None] = [None, *grade_labels]
        target_grade = st.selectbox(
            "Classe cible",
            target_choices,
            format_func=lambda item: "Aucune" if item is None else grade_labels[item],
        )
        year_options = academic_year_options(date.today())
        school_year = st.selectbox(
            "Année scolaire",
            year_options,
            index=year_options.index(default_academic_year(date.today())),
        )
        objective_label = st.selectbox("Objectif pédagogique", tuple(objectives), index=2)
        selected_subjects = st.multiselect(
            "Matières",
            list(subject_labels),
            default=list(subject_labels),
            format_func=subject_labels.__getitem__,
        )
        duration = st.slider("Temps d'étude quotidien", 10, 120, 30, 5)
        weekdays = st.multiselect(
            "Jours d'étude",
            list(range(7)),
            default=[0, 1, 2, 3, 4],
            format_func=lambda day: (
                "Lundi",
                "Mardi",
                "Mercredi",
                "Jeudi",
                "Vendredi",
                "Samedi",
                "Dimanche",
            )[day],
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
            default=("Exercices progressifs",),
        )
        error_help = st.selectbox(
            "Aide en cas d'erreur",
            ("HINT_FIRST", "EXPLAIN_METHOD", "SHOW_CORRECTION"),
            format_func=ERROR_HELP_LABELS.__getitem__,
        )
        submitted = st.form_submit_button("Créer l'élève", type="primary")
    if not submitted:
        return
    if not first_name.strip():
        st.error("Le prénom est obligatoire.")
        return
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        st.error("L'adresse e-mail de l'élève n'est pas valide.")
        return
    academic_year = _safe(lambda: parse_academic_year(school_year))
    if academic_year is None:
        return
    stable_profile = st.session_state.setdefault("parent_child_stable_ref", f"parent-child:{uuid4()}")
    request = OnboardingRequest(
        f"{stable_profile}:{school_year}:{objectives[objective_label].value}",
        LearnerProfile(
            stable_profile,
            first_name.strip(),
            CreatorRole.PARENT,
            birth_date=birth_date,
        ),
        academic_year,
        grade_by_id[int(current_grade)],
        LearnerGoalConfiguration(
            objectives[objective_label],
            grade_by_id[int(target_grade)] if target_grade is not None else None,
        ),
        tuple(SubjectPreference(int(subject_id), priority=True) for subject_id in selected_subjects),
        StudyPreferences(
            duration,
            tuple(AvailabilitySlot(day, duration, time(17)) for day in weekdays),
            difficulty=DifficultyPreference.STANDARD,
        ),
        CreatorRole.PARENT,
        "parent_created_learner",
    )
    manager = LearnerProfileManagementService(repository)
    result = _safe(
        lambda: manager.create(
            parent_ref,
            request,
            OnboardingProfileInput(
                0,
                first_name,
                last_name or None,
                birth_date,
                school_year,
                "FR-NATIONAL",
                tuple(formats),
                error_help,
                True,
                email,
            ),
            OnboardingService(DuckDBOnboardingRepository()),
            UnifiedOnboardingProfileService(repository),
        )
    )
    if result is None:
        return
    account_created, account_message = create_student_account(
        int(parent_ref),
        stable_profile,
        first_name,
        email,
        student_username,
        student_password,
        student_password_confirmation,
    )
    if not account_created:
        _safe(lambda: manager.delete(parent_ref, result.learner_id, first_name.strip(), True))
        st.error(account_message)
        return
    account_linked = has_active_student_account(stable_profile)
    parent_linked = repository.parent_authorized(parent_ref, result.learner_id)
    if not account_linked or not parent_linked:
        deactivate_student_account(int(parent_ref), stable_profile)
        _safe(lambda: manager.delete(parent_ref, result.learner_id, first_name.strip(), True))
        st.error(
            "Les liens Parent, Élève et profil pédagogique n'ont pas tous pu être vérifiés. "
            "Aucun profil partiel n'a été conservé."
        )
        return
    _safe(lambda: _create_initial_session(result))
    st.session_state.pop("parent_child_stable_ref", None)
    st.success("Le compte élève a été créé. L'élève peut maintenant se connecter directement.")
    st.rerun()


def _children_management(parent_ref: str, learners: tuple[tuple[int, str], ...]) -> None:
    st.title("Mes enfants")
    _create_child(parent_ref)
    manager = LearnerProfileManagementService(_repository())
    for learner_id, _ in learners:
        profile = _safe(partial(manager.get, parent_ref, learner_id))
        if profile is None:
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
            open_col, edit_col, menu_col = st.columns((2, 2, 1))
            if open_col.button("Ouvrir", key=f"child_open_{learner_id}"):
                request_navigation(st.session_state, "parent", "Tableau de bord", learner_id)
                st.rerun()
            if edit_col.button("Modifier", key=f"child_edit_{learner_id}"):
                st.session_state.manage_learner_action = ("edit", learner_id)
                st.rerun()
            with menu_col.popover("⋮"):
                if st.button("Modifier le profil", key=f"menu_profile_{learner_id}"):
                    st.session_state.manage_learner_action = ("edit", learner_id)
                    st.rerun()
                if st.button("Modifier le programme", key=f"menu_programme_{learner_id}"):
                    request_navigation(st.session_state, "parent", "Programme", learner_id)
                    st.rerun()
                if st.button("Réinitialiser le mot de passe", key=f"menu_password_{learner_id}"):
                    st.session_state.manage_learner_action = ("password", learner_id)
                    st.rerun()
                if st.button("Réinitialiser le diagnostic", key=f"menu_diagnostic_{learner_id}"):

                    def reset_diagnostic(learner_id: int = learner_id) -> bool:
                        manager.reset_diagnostic(parent_ref, learner_id)
                        return True

                    reset = _safe(reset_diagnostic)
                    if reset:
                        st.success("Le diagnostic sera reproposé.")
                if st.button("Supprimer l'élève", key=f"menu_delete_{learner_id}"):
                    st.session_state.manage_learner_action = ("delete", learner_id)
                    st.rerun()
    action = st.session_state.get("manage_learner_action")
    if action:
        if action[0] == "edit":
            _edit_learner(parent_ref, int(action[1]))
        elif action[0] == "delete":
            _delete_learner(parent_ref, int(action[1]))
        elif action[0] == "password":
            _reset_student_password(parent_ref, int(action[1]))
        elif action[0] == "account":
            _create_orphan_student_account(parent_ref, int(action[1]))


def run_parent(user: dict[str, object]) -> None:
    controller = build_parent_experience_controller()
    parent_ref = str(user["id"])
    learners = controller.learners(parent_ref)
    pages = (
        "Mes enfants",
        "Tableau de bord",
        "Progression",
        "Devoirs",
        "Recommandations",
        "Programme",
        "Planning",
        "Profil élève",
        "Paramètres",
    )
    apply_navigation_request(st.session_state, "parent", "parent_page", pages)
    with st.sidebar:
        st.success("Espace parent")
        page = st.radio(
            "Navigation",
            pages,
            key="parent_page",
        )
        st.button("Déconnexion", on_click=logout)
    if not learners:
        if page == "Mes enfants":
            _children_management(parent_ref, ())
        else:
            st.info("Aucun apprenant V2 n'est encore rattaché à ce compte parent.")
        return
    if page == "Mes enfants":
        _children_management(parent_ref, learners)
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
        items = HomeworkService(_repository()).list_for_learner(learner_id)
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
        items = HomeworkService(_repository()).list_for_learner(learner_id)
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
    else:
        st.title("Paramètres parent")
        st.write("Les accès restent limités aux apprenants explicitement rattachés.")


def run_unified_app(login_renderer: LoginRenderer) -> None:
    if not st.session_state.user:
        login_renderer()
        return
    user = st.session_state.user
    if user["role"] == "parent":
        run_parent(user)
        return
    learner_id = _learner_id(user)
    if learner_id is None or not _repository().onboarding_complete(learner_id):
        onboarding(user)
        return
    run_student(user, learner_id)
