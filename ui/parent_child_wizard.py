"""Five-step parent child creation wizard for LCAI-0015B."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, time
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import streamlit as st

from domain.decision.enums import ObjectiveKind
from domain.learning.models import GradeLevel
from domain.onboarding.enums import CreatorRole, DifficultyPreference
from domain.onboarding.models import (
    AvailabilitySlot,
    LearnerGoalConfiguration,
    LearnerProfile,
    OnboardingRequest,
    StudyPreferences,
    SubjectPreference,
)
from infrastructure.database.legacy_gateway import (
    create_student_account,
    deactivate_student_account,
    has_active_student_account,
)
from infrastructure.repositories.onboarding import DuckDBOnboardingRepository
from services.academic_year import academic_year_options, default_academic_year, parse_academic_year
from services.auth.passwords import is_password_too_short, password_length_error
from services.onboarding import OnboardingService
from services.unified_experience import (
    LearnerProfileManagementService,
    OnboardingProfileInput,
    UnifiedOnboardingProfileService,
)

if TYPE_CHECKING:
    from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository

WizardContext = dict[str, Any]
SubmitChildFn = Callable[..., bool | None]


WEEKDAY_LABELS = (
    "Lundi",
    "Mardi",
    "Mercredi",
    "Jeudi",
    "Vendredi",
    "Samedi",
    "Dimanche",
)

FORMAT_OPTIONS = (
    "Exemples avant les exercices",
    "Explications détaillées",
    "Exercices progressifs",
    "Exercices courts",
    "Défis",
)


def reset_child_creation_wizard() -> None:
    for key in (
        "parent_show_child_wizard",
        "parent_child_wizard_step",
        "parent_child_wizard_data",
        "parent_child_stable_ref",
    ):
        st.session_state.pop(key, None)


def render_child_creation_wizard(
    *,
    parent_ref: str,
    user: dict[str, object],
    repository: DuckDBUnifiedExperienceRepository,
    grade_labels: dict[int, str],
    subject_labels: dict[int, str],
    grade_by_id: dict[int, GradeLevel],
    objectives: dict[str, ObjectiveKind],
    error_help_labels: dict[str, str],
    submit_child: SubmitChildFn,
) -> None:
    step = int(st.session_state.setdefault("parent_child_wizard_step", 1))
    data: dict[str, Any] = st.session_state.setdefault("parent_child_wizard_data", {})
    st.subheader(f"Ajouter un enfant — étape {step}/5")
    st.progress(step / 5)

    if st.button("Annuler", key="parent_child_wizard_cancel"):
        reset_child_creation_wizard()
        st.rerun()

    if step == 1:
        _render_step_identity(data, grade_labels)
        step2_submitted = False
    elif step == 2:
        step2_submitted = _render_step_account(data)
    elif step == 3:
        _render_step_pedagogy(data, grade_labels, subject_labels, objectives, error_help_labels)
        step2_submitted = False
    elif step == 4:
        _render_step_virtual_teacher(data)
        step2_submitted = False
        step5_submitted = False
    else:
        step5_submitted = _render_step_confirmation(data, grade_labels, subject_labels, objectives)
        step2_submitted = False

    nav_prev, nav_next = st.columns(2)
    if step > 1 and nav_prev.button("← Précédent", key="parent_child_wizard_prev"):
        st.session_state.parent_child_wizard_step = step - 1
        st.rerun()

    if step == 2:
        if step2_submitted:
            error = _validate_step(step, data, grade_labels, subject_labels, objectives)
            if error:
                st.error(error)
            else:
                st.session_state.parent_child_wizard_step = step + 1
                st.rerun()
    elif step == 5:
        if step5_submitted:
            error = _validate_step(5, data, grade_labels, subject_labels, objectives)
            if error:
                st.error(error)
            else:
                with st.spinner("Création du compte élève en cours…"):
                    created = submit_child(
                        parent_ref=parent_ref,
                        user=user,
                        data=data,
                        repository=repository,
                        grade_labels=grade_labels,
                        subject_labels=subject_labels,
                        grade_by_id=grade_by_id,
                        objectives=objectives,
                    )
                if created:
                    st.session_state.parent_child_created_flash = str(data.get("first_name", "L'élève"))
                    reset_child_creation_wizard()
                    st.rerun()
                else:
                    st.error(
                        "La création n'a pas abouti. Corrigez les informations indiquées puis réessayez."
                    )
    elif step < 5:
        if nav_next.button("Suivant →", key="parent_child_wizard_next", type="primary"):
            error = _validate_step(step, data, grade_labels, subject_labels, objectives)
            if error:
                st.error(error)
            else:
                st.session_state.parent_child_wizard_step = step + 1
                st.rerun()


def submit_child_creation(
    *,
    parent_ref: str,
    user: dict[str, object],
    data: dict[str, Any],
    repository: DuckDBUnifiedExperienceRepository,
    grade_by_id: dict[int, GradeLevel],
    objectives: dict[str, ObjectiveKind],
    safe: Callable[[Callable[[], Any]], Any | None],
    create_initial_session: Callable[[Any], Any],
    save_virtual_teacher_preferences: Callable[[int, dict[str, Any]], None],
) -> bool:
    first_name = str(data["first_name"]).strip()
    normalized_email = str(data.get("email") or "").strip().lower()
    school_year = str(data["school_year"])
    academic_year = safe(lambda: parse_academic_year(school_year))
    if academic_year is None:
        return False
    stable_profile = st.session_state.setdefault("parent_child_stable_ref", f"parent-child:{uuid4()}")
    existing_learner_id = repository.learner_for_external_ref(stable_profile)
    if existing_learner_id is not None and repository.parent_authorized(parent_ref, existing_learner_id):
        return True
    objective_label = str(data["objective_label"])
    request = OnboardingRequest(
        f"{stable_profile}:{school_year}:{objectives[objective_label].value}",
        LearnerProfile(
            stable_profile,
            first_name,
            CreatorRole.PARENT,
            birth_date=data["birth_date"],
        ),
        academic_year,
        grade_by_id[int(data["current_grade"])],
        LearnerGoalConfiguration(
            objectives[objective_label],
            grade_by_id[int(data["target_grade"])] if data.get("target_grade") is not None else None,
        ),
        tuple(SubjectPreference(int(subject_id), priority=True) for subject_id in data["selected_subjects"]),
        StudyPreferences(
            int(data["duration"]),
            tuple(AvailabilitySlot(day, int(data["duration"]), time(17)) for day in data["weekdays"]),
            difficulty=DifficultyPreference.STANDARD,
        ),
        CreatorRole.PARENT,
        "parent_created_learner",
    )
    manager = LearnerProfileManagementService(repository)
    result = safe(
        lambda: manager.create(
            parent_ref,
            request,
            OnboardingProfileInput(
                0,
                first_name,
                data.get("last_name") or None,
                data["birth_date"],
                school_year,
                "FR-NATIONAL",
                tuple(data["formats"]),
                str(data["error_help"]),
                bool(data.get("take_diagnostic", True)),
                normalized_email or None,
            ),
            OnboardingService(DuckDBOnboardingRepository()),
            UnifiedOnboardingProfileService(repository),
        )
    )
    if result is None:
        return False
    account_created, account_message = create_student_account(
        int(parent_ref),
        stable_profile,
        first_name,
        normalized_email,
        str(data["student_username"]),
        str(data["student_password"]),
        str(data["student_password_confirmation"]),
    )
    if not account_created:
        safe(lambda: manager.delete(parent_ref, result.learner_id, first_name, True))
        st.error(account_message)
        return False
    if not has_active_student_account(stable_profile) or not repository.parent_authorized(parent_ref, result.learner_id):
        deactivate_student_account(int(parent_ref), stable_profile)
        safe(lambda: manager.delete(parent_ref, result.learner_id, first_name, True))
        st.error(
            "Les liens Parent, Élève et profil pédagogique n'ont pas tous pu être vérifiés. "
            "Aucun profil partiel n'a été conservé."
        )
        return False
    save_virtual_teacher_preferences(result.learner_id, data)
    safe(lambda: create_initial_session(result))
    return True


def _render_step_identity(data: dict[str, Any], grade_labels: dict[int, str]) -> None:
    st.markdown("#### Étape 1 — Identité")
    names = st.columns(2)
    data["first_name"] = names[0].text_input("Prénom", value=str(data.get("first_name", "")))
    data["last_name"] = names[1].text_input("Nom", value=str(data.get("last_name", "")))
    data["birth_date"] = st.date_input(
        "Date de naissance",
        value=data.get("birth_date", date(2012, 1, 1)),
        min_value=date(date.today().year - 30, 1, 1),
        max_value=date(date.today().year - 5, 12, 31),
        format="DD/MM/YYYY",
    )
    data["current_grade"] = st.selectbox(
        "Classe actuelle",
        list(grade_labels),
        index=list(grade_labels).index(data["current_grade"]) if data.get("current_grade") in grade_labels else 0,
        format_func=grade_labels.__getitem__,
    )
    year_options = academic_year_options(date.today())
    default_year = str(data.get("school_year") or default_academic_year(date.today()))
    data["school_year"] = st.selectbox(
        "Année scolaire",
        year_options,
        index=year_options.index(default_year) if default_year in year_options else 0,
    )


def _render_step_account(data: dict[str, Any]) -> bool:
    st.markdown("#### Étape 2 — Compte Élève")
    with st.form("parent_child_wizard_step2_form", clear_on_submit=False):
        username = st.text_input("Identifiant", value=str(data.get("student_username", "")))
        email = st.text_input("Adresse e-mail (facultatif)", value=str(data.get("email", "")))
        credentials = st.columns(2)
        password = credentials[0].text_input("Mot de passe", type="password")
        confirmation = credentials[1].text_input("Confirmer le mot de passe", type="password")
        submitted = st.form_submit_button("Suivant →", type="primary")
    if submitted:
        data["student_username"] = username
        data["email"] = email
        data["student_password"] = password
        data["student_password_confirmation"] = confirmation
    return submitted


def _render_step_pedagogy(
    data: dict[str, Any],
    grade_labels: dict[int, str],
    subject_labels: dict[int, str],
    objectives: dict[str, ObjectiveKind],
    error_help_labels: dict[str, str],
) -> None:
    st.markdown("#### Étape 3 — Parcours pédagogique")
    # Produit 3e : cible = classe actuelle (pas de multi-niveaux).
    data["target_grade"] = data.get("current_grade")
    st.caption("Classe cible : 3e — Objectif Brevet 2027 (pas de changement de niveau).")
    objective_keys = tuple(objectives)
    data["objective_label"] = st.selectbox("Objectif pédagogique", objective_keys, index=2)
    data["selected_subjects"] = st.multiselect(
        "Matières",
        list(subject_labels),
        default=list(data.get("selected_subjects") or subject_labels),
        format_func=subject_labels.__getitem__,
    )
    data["duration"] = st.slider("Temps d'étude quotidien", 10, 120, int(data.get("duration", 30)), 5)
    data["weekdays"] = st.multiselect(
        "Jours d'étude",
        list(range(7)),
        default=list(data.get("weekdays") or [0, 1, 2, 3, 4]),
        format_func=lambda day: WEEKDAY_LABELS[day],
    )
    data["formats"] = st.multiselect(
        "Préférences pédagogiques",
        FORMAT_OPTIONS,
        default=tuple(data.get("formats") or ("Exercices progressifs",)),
    )
    data["error_help"] = st.selectbox(
        "Aide en cas d'erreur",
        ("HINT_FIRST", "EXPLAIN_METHOD", "SHOW_CORRECTION"),
        format_func=error_help_labels.__getitem__,
    )
    data["take_diagnostic"] = st.checkbox(
        "Proposer le diagnostic initial à la première connexion",
        value=bool(data.get("take_diagnostic", True)),
    )


def _render_step_virtual_teacher(data: dict[str, Any]) -> None:
    st.markdown("#### Étape 4 — Professeur IA")
    data["vt_feature_enabled"] = st.checkbox(
        "Activer le professeur virtuel dès maintenant",
        value=bool(data.get("vt_feature_enabled", False)),
    )
    data["vt_teacher_profile"] = st.selectbox(
        "Profil",
        ["TEACHER_FEMALE_01", "TEACHER_MALE_01"],
        index=0 if data.get("vt_teacher_profile") != "TEACHER_MALE_01" else 1,
    )
    data["vt_teacher_name"] = st.selectbox(
        "Prénom affiché",
        ["Emma", "Léa", "Lucas", "Hugo"],
        index=["Emma", "Léa", "Lucas", "Hugo"].index(str(data.get("vt_teacher_name", "Emma"))),
    )
    data["vt_voice_id"] = st.selectbox(
        "Voix",
        ["warm_female", "warm_male"],
        index=0 if data.get("vt_voice_id") != "warm_male" else 1,
    )
    data["vt_tone"] = st.selectbox("Ton", ["calm", "encouraging", "academic"])
    data["vt_response_length"] = st.selectbox("Longueur des réponses", ["short", "normal", "detailed"])
    data["vt_help_level"] = st.slider("Niveau d'aide", 1, 3, int(data.get("vt_help_level", 2)))
    data["vt_audio_enabled"] = st.checkbox(
        "Autoriser la lecture audio",
        value=bool(data.get("vt_audio_enabled", False)),
    )
    data["vt_parent_locked"] = st.checkbox(
        "Verrouiller les réglages côté élève",
        value=bool(data.get("vt_parent_locked", False)),
    )


def _render_step_confirmation(
    data: dict[str, Any],
    grade_labels: dict[int, str],
    subject_labels: dict[int, str],
    objectives: dict[str, ObjectiveKind],
) -> bool:
    st.markdown("#### Étape 5 — Confirmation")
    subjects = ", ".join(subject_labels.get(int(item), str(item)) for item in data.get("selected_subjects", ()))
    with st.form("parent_child_wizard_step5_form", clear_on_submit=False):
        st.write(f"**Élève :** {data.get('first_name')} {data.get('last_name') or ''}".strip())
        st.write(f"**Classe :** {grade_labels.get(int(data['current_grade']), '—')}")
        st.write(f"**Identifiant :** {data.get('student_username')}")
        st.write(f"**Objectif :** {data.get('objective_label')}")
        st.write(f"**Matières :** {subjects}")
        vt_state = "Activé" if data.get("vt_feature_enabled") else "Désactivé (activation possible plus tard)"
        st.write(f"**Professeur IA :** {vt_state}")
        submitted = st.form_submit_button("Créer l'élève", type="primary")
    return submitted


def _validate_step(
    step: int,
    data: dict[str, Any],
    grade_labels: dict[int, str],
    subject_labels: dict[int, str],
    objectives: dict[str, ObjectiveKind],
) -> str | None:
    if step == 1:
        if not str(data.get("first_name", "")).strip():
            return "Le prénom est obligatoire."
        if not grade_labels:
            return "Les niveaux scolaires ne sont pas disponibles."
    if step == 2:
        if not str(data.get("student_username", "")).strip():
            return "L'identifiant de connexion est obligatoire."
        password = str(data.get("student_password", ""))
        confirmation = str(data.get("student_password_confirmation", ""))
        if not password:
            return "Le mot de passe est obligatoire."
        if is_password_too_short(password):
            return password_length_error()
        if password != confirmation:
            return "La confirmation du mot de passe ne correspond pas."
        email = str(data.get("email") or "").strip().lower()
        if email and ("@" not in email or "." not in email.rsplit("@", 1)[-1]):
            return "L'adresse e-mail n'est pas valide."
    if step == 3:
        if not data.get("selected_subjects"):
            return "Sélectionnez au moins une matière."
        if not data.get("weekdays"):
            return "Sélectionnez au moins un jour d'étude."
        if str(data.get("objective_label")) not in objectives:
            return "Objectif pédagogique invalide."
    if step >= 5:
        for check_step in (1, 2, 3):
            message = _validate_step(check_step, data, grade_labels, subject_labels, objectives)
            if message:
                return message
    return None
