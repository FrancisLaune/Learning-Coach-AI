"""Accessible Streamlit views for the optional V2 learner experience."""

from __future__ import annotations

import time
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
    build_unified_session_execution_service,
)
from services.learning_session.experience import SessionListItem, StudentDashboard
from ui.i18n import label, status_label
from ui.navigation import request_navigation
from ui.session import logout


def _error(error: PresentationError, *, actions: tuple[tuple[str, str], ...] = ()) -> None:
    st.error(error.message, icon="⚠️")
    st.info(error.recovery)
    if actions:
        columns = st.columns(len(actions))
        for column, (button_label, page_key) in zip(columns, actions, strict=True):
            if column.button(button_label, use_container_width=True, key=f"recovery_{page_key}"):
                request_navigation(st.session_state, "student", page_key)
                st.rerun()


def _status_label(status: str) -> str:
    return status_label(status, feminine=True)


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
        st.write(f"**{item.label}** — {item.score:.0f} % — {label(item.level)}")
        st.progress(min(100, max(0, int(item.score))), text=f"Tendance : {label(item.trend)}")


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
        _error(result, actions=(("Retour au tableau de bord", "Tableau de bord"), ("Mes devoirs", "Devoirs")))
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
            request_navigation(st.session_state, "student", "Ma séance IA")
            st.rerun()
    else:
        st.info("Aucune séance n'est actuellement planifiée.")
    if result.next_revision:
        st.caption(f"Prochaine révision : {result.next_revision.strftime('%d/%m/%Y')}")
    _mastery(result)
    from application.experience_factory import build_pedagogical_intelligence_controller
    from ui.pedagogical_intelligence import render_pedagogical_intelligence_dashboard

    pi_controller = build_pedagogical_intelligence_controller()
    pi_overview = pi_controller.student_overview(learner_id)
    if isinstance(pi_overview, PresentationError):
        st.warning(pi_overview.message)
    else:
        st.divider()
        render_pedagogical_intelligence_dashboard(
            pi_controller,
            pi_overview,
            learner_id,
            key_prefix=f"student_pi_{learner_id}",
            show_diagnostic=True,
        )


def session_screen(
    controller: StudentExperienceController,
    learner_id: int,
    *,
    user: dict[str, object] | None = None,
) -> None:
    from ui.student_guidance import (
        load_session_result_explanation,
        render_homework_during_guidance,
        render_homework_result_explanation,
    )

    actor = user or {"id": learner_id, "name": "Élève", "role": "STUDENT", "resolved_learner_id": learner_id}
    session_id = st.session_state.get("v2_session_id")
    if not session_id:
        st.info("Sélectionne une séance depuis l'accueil ou reprends un devoir en cours.")
        left, right = st.columns(2)
        if left.button("Retour à l'accueil", use_container_width=True, key="session_back_home"):
            request_navigation(st.session_state, "student", "Tableau de bord")
            st.rerun()
        if right.button("Mes devoirs", use_container_width=True, key="session_back_homework"):
            request_navigation(st.session_state, "student", "Devoirs")
            st.rerun()
        return
    result = controller.session(learner_id, int(session_id))
    if isinstance(result, PresentationError):
        _error(
            result,
            actions=(
                ("Retour au tableau de bord", "Tableau de bord"),
                ("Mes devoirs", "Devoirs"),
            ),
        )
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
            st.write(f"Type : {label(activity.activity_type)} · État : {_status_label(activity.status)}")
            if activity.status == "COMPLETED":
                st.write(f"Score : {activity.score:.0f} %")
    if result.session.status == "RUNNING":
        execution = build_unified_session_execution_service()
        question = execution.current(learner_id, result.session.session_id)
        feedback_key = f"session_feedback_{result.session.session_id}"
        feedback = st.session_state.get(feedback_key)
        if feedback:
            if feedback.correct:
                st.success(f"Bonne réponse — {feedback.score:.0f} %")
            else:
                st.error(f"Réponse à consolider — {feedback.score:.0f} %")
            st.write(f"**Méthode :** {feedback.method}")
            st.write(feedback.explanation)
            if feedback.advice:
                st.info(feedback.advice)
            st.caption(f"Maîtrise : {feedback.mastery_before * 100:.0f} % → {feedback.mastery_after * 100:.0f} %")
            if st.button("Activité suivante", type="primary"):
                del st.session_state[feedback_key]
                st.rerun()
        elif question:
            st.divider()
            st.caption(f"Question {question.position}/{question.total} · {question.activity_title}")
            if question.instructions:
                st.write(question.instructions)
            if question.context:
                st.info(question.context)
            st.markdown(f"### {question.statement}")
            answer_key = f"answer_{question.session_id}_{question.question_id}"
            if question.options:
                option_codes = [item[0] for item in question.options]
                if question.response_type.casefold() in {"multiple_choice", "mcq_multi"}:
                    answer = st.multiselect(
                        "Tes réponses",
                        option_codes,
                        format_func=dict(question.options).__getitem__,
                        key=answer_key,
                    )
                else:
                    answer = st.radio(
                        "Ta réponse",
                        option_codes,
                        format_func=dict(question.options).__getitem__,
                        key=answer_key,
                    )
            else:
                answer = st.text_input("Ta réponse", key=answer_key)
            if question.hints:
                with st.expander("Besoin d'un indice ?"):
                    for hint_id, _, penalty in question.hints:
                        if st.button(f"Afficher l'indice ({penalty:g} point de pénalité)", key=f"hint_{hint_id}"):
                            text = execution.use_hint(learner_id, result.session.session_id, hint_id, datetime.now(UTC))
                            st.session_state[f"shown_hint_{hint_id}"] = text
                        if shown := st.session_state.get(f"shown_hint_{hint_id}"):
                            st.info(shown)
            render_homework_during_guidance(
                actor,
                learner_id,
                result.session.session_id,
                question.activity_id,
                key_prefix=f"session_{result.session.session_id}_{question.question_id}",
            )
            started_key = f"question_started_{question.session_id}_{question.question_id}"
            st.session_state.setdefault(started_key, time.monotonic())
            if st.button("Valider ma réponse", type="primary", disabled=not str(answer).strip()):
                elapsed = int((time.monotonic() - float(st.session_state[started_key])) * 1000)
                try:
                    st.session_state[feedback_key] = execution.submit(
                        learner_id,
                        result.session.session_id,
                        answer,
                        datetime.now(UTC),
                        elapsed,
                    )
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        else:
            st.info("Toutes les questions disponibles ont été traitées.")
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
    if result.session.status == "COMPLETED":
        explanation = load_session_result_explanation(actor, learner_id, result.session.session_id)
        if explanation:
            render_homework_result_explanation(explanation)


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
