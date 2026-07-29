"""Central tabbed learner sheet for parent family management (LCAI-0015B)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import streamlit as st

from application.experience_controllers import ParentExperienceController, PresentationError
from infrastructure.database.legacy_gateway import student_account_for_learner
from services.homework.factory import build_homework_service
from services.unified_experience import LearnerProfileManagementService, ProgrammeChangeService
from ui.i18n import label
from ui.navigation import request_navigation
from ui.v2_experience import parent_dashboard


def render_parent_learner_sheet(
    *,
    user: dict[str, object],
    parent_ref: str,
    learner_id: int,
    profile_manager: LearnerProfileManagementService,
    repository: Any,
    controller: ParentExperienceController,
    objective_labels: dict[str, str],
    error_help_labels: dict[str, str],
    on_back: Callable[[], None],
    render_virtual_teacher: Callable[[], None],
    render_homework_form: Callable[[], None],
    safe: Callable[[Callable[[], Any]], Any | None],
) -> None:
    profile = safe(lambda: profile_manager.get(parent_ref, learner_id))
    if profile is None:
        return
    on_back()
    st.subheader(f"Fiche de {profile.first_name}")
    grade_labels = dict((item[0], item[2]) for item in repository.grade_levels())
    subject_labels = dict((item[0], item[2]) for item in repository.reference_subjects())
    account = student_account_for_learner(profile.external_ref)
    last_activity = repository.learner_last_activity_label(learner_id)

    tabs = st.tabs(
        (
            "Vue d'ensemble",
            "Informations",
            "Programme",
            "Compte",
            "Professeur IA",
            "Devoirs",
            "Planning",
            "Progression",
            "Historique",
        )
    )

    with tabs[0]:
        st.write(f"**Classe :** {grade_labels.get(profile.current_grade_id, '—')}")
        st.write(f"**Objectif :** {objective_labels.get(profile.objective, 'Parcours personnalisé')}")
        if last_activity:
            st.write(f"**Dernière activité :** {last_activity}")
        else:
            st.write("**Dernière activité :** Aucune activité")
        if account and account["active"]:
            st.success("Compte élève actif")
        else:
            st.warning("Compte élève non configuré")
        if st.button("Ouvrir le tableau de bord", key=f"sheet_dashboard_{learner_id}"):
            request_navigation(st.session_state, "parent", "Tableau de bord", learner_id)
            st.rerun()

    with tabs[1]:
        st.write(f"**Prénom :** {profile.first_name}")
        st.write(f"**Nom :** {profile.last_name or '—'}")
        st.write(f"**Âge :** {profile.age if profile.age is not None else 'Inconnu'} ans")
        st.write(f"**Année scolaire :** {profile.school_year}")
        if profile.subject_ids:
            subjects = ", ".join(subject_labels.get(subject_id, str(subject_id)) for subject_id in profile.subject_ids)
            st.write(f"**Matières :** {subjects}")
        st.write(f"**Temps d'étude quotidien :** {profile.daily_duration_minutes} min")
        st.write(f"**Aide en cas d'erreur :** {error_help_labels.get(profile.error_help_preference, profile.error_help_preference)}")
        if st.button("Modifier le profil", key=f"sheet_edit_{learner_id}"):
            st.session_state.manage_learner_action = ("edit", learner_id)
            st.rerun()

    with tabs[2]:
        target_grade = (
            "Non définie"
            if profile.target_grade_id is None
            else grade_labels.get(profile.target_grade_id, "Classe inconnue")
        )
        st.write(f"**Classe actuelle :** {grade_labels.get(profile.current_grade_id, 'Classe inconnue')}")
        st.write(f"**Classe cible :** {target_grade}")
        st.write(f"**Statut diagnostic :** {profile.diagnostic_status}")
        if st.button("Réinitialiser le diagnostic", key=f"sheet_reset_diag_{learner_id}") and safe(
            lambda: profile_manager.reset_diagnostic(parent_ref, learner_id)
        ) is not None:
            st.success("Le diagnostic a été réinitialisé.")
            st.rerun()
        changes = safe(lambda: ProgrammeChangeService(repository).list_for_parent(parent_ref, learner_id)) or ()
        if changes:
            st.markdown("#### Propositions de programme")
            for change in changes:
                st.write(f"- **{change.change_type}** · {change.status}")

    with tabs[3]:
        if account and account["active"]:
            st.success("Compte élève actif")
            st.write(f"**Identifiant :** {account['username']}")
            if account.get("email"):
                st.write(f"**E-mail :** {account['email']}")
        else:
            st.warning("Compte élève non configuré")
            if st.button("Créer le compte élève", key=f"sheet_repair_account_{learner_id}"):
                st.session_state.manage_learner_action = ("account", learner_id)
                st.rerun()
        if st.button("Réinitialiser le mot de passe", key=f"sheet_password_{learner_id}"):
            st.session_state.manage_learner_action = ("password", learner_id)
            st.rerun()

    with tabs[4]:
        render_virtual_teacher()

    with tabs[5]:
        render_homework_form()
        items = build_homework_service(repository).list_for_learner(learner_id)
        if not items:
            st.info("Aucun devoir assigné.")
        else:
            st.dataframe(
                [
                    {"Matière": item.subject_label, "État": label(item.status.value), "Échéance": item.due_at}
                    for item in items
                ],
                hide_index=True,
            )

    with tabs[6]:
        items = build_homework_service(repository).list_for_learner(learner_id)
        if not items:
            st.info("Aucune échéance planifiée.")
        else:
            st.dataframe(
                [
                    {"Matière": item.subject_label, "Échéance": item.due_at, "État": label(item.status.value)}
                    for item in items
                ],
                hide_index=True,
            )

    with tabs[7]:
        parent_dashboard(controller, parent_ref, learner_id)

    with tabs[8]:
        history = controller.history(parent_ref, learner_id)
        if isinstance(history, PresentationError):
            st.error(history.message)
        elif history:
            st.dataframe(
                [
                    {
                        "Séance": item.session_id,
                        "Statut": item.status,
                        "Créée le": item.created_at,
                        "Durée (s)": item.duration_seconds,
                        "Score": item.score,
                    }
                    for item in history
                ],
                hide_index=True,
            )
        else:
            st.info("Aucune séance terminée.")
