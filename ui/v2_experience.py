"""Accessible Streamlit views for the optional V2 learner experience."""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from application.experience_controllers import (
    ParentExperienceController,
    PresentationError,
    StudentExperienceController,
)
from application.experience_factory import (
    build_parent_experience_controller,
    build_student_experience_controller,
)
from services.learning_session.experience import SessionListItem, StudentDashboard
from ui.session import logout


def _error(error: PresentationError) -> None:
    st.error(error.message, icon="⚠️")
    st.info(error.recovery)


def _status_label(status: str) -> str:
    return {
        "READY": "Prête",
        "RUNNING": "En cours",
        "PAUSED": "En pause",
        "COMPLETED": "Terminée",
        "ABANDONED": "Arrêtée",
    }.get(status, status.replace("_", " ").title())


def _metric_cards(dashboard: StudentDashboard) -> None:
    columns = st.columns(min(5, len(dashboard.metrics)))
    for column, metric in zip(columns, dashboard.metrics, strict=True):
        column.metric(metric.label, metric.value, help=metric.help_text or None)


def _mastery(dashboard: StudentDashboard) -> None:
    st.subheader("Compétences", anchor=False)
    if not dashboard.mastery:
        st.info("Les compétences apparaîtront après les premières activités évaluées.")
        return
    for item in dashboard.mastery:
        st.write(f"**{item.label}** — {item.score:.0f} % — {item.level.replace('_', ' ').title()}")
        st.progress(min(100, max(0, int(item.score))), text=f"Tendance : {item.trend.lower()}")


def _history_rows(sessions: tuple[SessionListItem, ...]) -> list[dict[str, object]]:
    return [
        {
            "Date": item.created_at.strftime("%d/%m/%Y %H:%M"),
            "Durée": f"{item.duration_seconds // 60} min",
            "Score": f"{item.score:.0f} %",
            "Progression": f"{item.mastery_gain:+.1f}",
            "Achèvement": f"{item.completion_rate:.0f} %",
        }
        for item in sessions
    ]


def student_dashboard(controller: StudentExperienceController, learner_id: int) -> None:
    result = controller.dashboard(learner_id)
    if isinstance(result, PresentationError):
        _error(result)
        return
    st.title(f"Bonjour {result.display_name}")
    st.markdown(f"### Objectif du jour : {result.objective}")
    _metric_cards(result)
    session = result.current_session
    if session:
        st.subheader("Prochaine séance", anchor=False)
        st.write(f"Durée estimée : **{result.recommended_duration_minutes} minutes**")
        label = "Continuer la séance" if session.status in {"RUNNING", "PAUSED"} else "Commencer la séance"
        if st.button(label, type="primary", use_container_width=True):
            st.session_state.v2_session_id = session.session_id
            st.session_state.v2_student_page = "Séance"
            st.rerun()
    else:
        st.info("Aucune séance n'est actuellement planifiée.")
    if result.next_revision:
        st.caption(f"Prochaine révision : {result.next_revision.strftime('%d/%m/%Y')}")
    _mastery(result)


def session_screen(controller: StudentExperienceController, learner_id: int) -> None:
    session_id = st.session_state.get("v2_session_id")
    if not session_id:
        st.info("Sélectionne une séance depuis le tableau de bord.")
        return
    result = controller.session(learner_id, int(session_id))
    if isinstance(result, PresentationError):
        _error(result)
        return
    total = max(1, len(result.activities))
    st.title("Séance d'apprentissage")
    left, middle, right = st.columns(3)
    left.metric("Activités terminées", f"{result.completed_activities}/{len(result.activities)}")
    middle.metric("Temps écoulé", f"{result.elapsed_seconds // 60} min")
    right.metric("Temps restant", f"{result.remaining_seconds // 60} min")
    st.progress(
        result.completed_activities / total, text=f"Progression de la séance — {_status_label(result.session.status)}"
    )
    for position, activity in enumerate(result.activities, 1):
        with st.container(border=True):
            st.markdown(f"#### Activité {position} — {activity.title}")
            st.write(f"Type : {activity.activity_type} · État : {_status_label(activity.status)}")
            if activity.status == "COMPLETED":
                st.write(f"Score : {activity.score:.0f} %")
    actions = st.columns(3)
    error = None
    action_taken = False
    if result.session.status == "READY" and actions[0].button("Commencer", type="primary"):
        action_taken = True
        error = controller.start(result.session.session_id, datetime.now(UTC))
    elif result.session.status == "RUNNING" and actions[1].button("Mettre en pause"):
        action_taken = True
        error = controller.pause(result.session.session_id, datetime.now(UTC))
    elif result.session.status == "PAUSED" and actions[0].button("Reprendre", type="primary"):
        action_taken = True
        error = controller.resume(result.session.session_id, datetime.now(UTC))
    if error:
        _error(error)
    elif action_taken:
        st.rerun()


def student_history(controller: StudentExperienceController, learner_id: int) -> None:
    result = controller.history(learner_id)
    st.title("Historique des séances")
    if isinstance(result, PresentationError):
        _error(result)
        return
    if not result:
        st.info("Aucune séance terminée pour le moment.")
        return
    st.dataframe(_history_rows(result), use_container_width=True, hide_index=True)


def student_summary(controller: StudentExperienceController, learner_id: int) -> None:
    session_id = st.session_state.get("v2_session_id")
    if not session_id:
        st.info("Aucune synthèse sélectionnée.")
        return
    result = controller.summary(learner_id, int(session_id))
    if isinstance(result, PresentationError):
        _error(result)
        return
    st.title("Synthèse de la séance")
    columns = st.columns(4)
    columns[0].metric("Achèvement", f"{result.session.completion_rate:.0f} %")
    columns[1].metric("Durée", f"{result.session.duration_seconds // 60} min")
    columns[2].metric("Score", f"{result.session.score:.0f} %")
    columns[3].metric("Gain de maîtrise", f"{result.session.mastery_gain:+.1f}")
    st.subheader("Points forts", anchor=False)
    st.write(", ".join(result.strengths) if result.strengths else "À déterminer avec davantage d'activités.")
    st.subheader("À consolider", anchor=False)
    st.write(", ".join(result.weaknesses) if result.weaknesses else "Aucune faiblesse identifiée.")
    if result.recommendation:
        st.info(result.recommendation)


def run_student_experience(user: dict[str, object]) -> None:
    controller = build_student_experience_controller()
    learner_id = int(str(user["id"]))
    pages = ("Tableau de bord", "Séance", "Synthèse", "Historique", "Paramètres")
    with st.sidebar:
        st.success(f"Élève : {user['name']}")
        page = st.radio("Navigation principale", pages, key="v2_student_page")
        st.button("Déconnexion", on_click=logout)
    if page == "Tableau de bord":
        student_dashboard(controller, learner_id)
    elif page == "Séance":
        session_screen(controller, learner_id)
    elif page == "Synthèse":
        student_summary(controller, learner_id)
    elif page == "Historique":
        student_history(controller, learner_id)
    else:
        st.title("Paramètres")
        st.info("Les préférences pédagogiques sont gérées par les services du parcours.")


def parent_dashboard(controller: ParentExperienceController, parent_ref: str, learner_id: int) -> None:
    result = controller.dashboard(parent_ref, learner_id)
    if isinstance(result, PresentationError):
        _error(result)
        return
    st.title(f"Suivi de {result.display_name}")
    _metric_cards(result)
    _mastery(result)


def run_parent_experience(user: dict[str, object]) -> None:
    controller = build_parent_experience_controller()
    parent_ref = str(user["id"])
    learners = controller.learners(parent_ref)
    with st.sidebar:
        st.success("Espace parent")
        page = st.radio("Navigation principale", ("Tableau de bord", "Historique", "Statistiques", "Compétences"))
        st.button("Déconnexion", on_click=logout)
    if not learners:
        st.info("Aucun apprenant V2 n'est disponible.")
        return
    learner_id = st.selectbox("Apprenant", [item[0] for item in learners], format_func=dict(learners).__getitem__)
    if page == "Historique":
        result = controller.history(parent_ref, int(learner_id))
        if isinstance(result, PresentationError):
            _error(result)
        elif result:
            st.dataframe(_history_rows(result), use_container_width=True, hide_index=True)
        else:
            st.info("Aucune séance terminée.")
    else:
        parent_dashboard(controller, parent_ref, int(learner_id))
