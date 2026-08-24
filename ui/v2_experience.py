"""Accessible Streamlit views for the optional V2 learner experience."""

from __future__ import annotations

import subprocess
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


def _inject_session_button_styles() -> None:
    if st.session_state.get("_session_btn3d_css_loaded"):
        return
    st.session_state["_session_btn3d_css_loaded"] = True
    st.markdown(
        """
<style>
.btn3d [data-testid="stButton"] > button {
  border: 1px solid #1e3a8a !important;
  border-radius: 12px !important;
  background: linear-gradient(180deg, #60a5fa 0%, #2563eb 100%) !important;
  color: #ffffff !important;
  font-weight: 700 !important;
  box-shadow: 0 4px 0 #1e40af, 0 8px 18px rgba(37,99,235,.25) !important;
  transition: transform .08s ease, box-shadow .08s ease, filter .08s ease !important;
}
.btn3d [data-testid="stButton"] > button:hover {
  filter: brightness(1.05) !important;
}
.btn3d [data-testid="stButton"] > button:active {
  transform: translateY(2px) !important;
  box-shadow: 0 2px 0 #1e40af, 0 5px 12px rgba(37,99,235,.25) !important;
}
</style>
        """,
        unsafe_allow_html=True,
    )


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


def _history_rows(
    sessions: tuple[SessionListItem, ...],
    *,
    session_kinds: dict[int, str] | None = None,
) -> list[dict[str, object]]:
    kinds = session_kinds or {}
    rows: list[dict[str, object]] = []
    for item in sessions:
        kind = kinds.get(int(item.session_id), "Séance")
        rows.append(
            {
                "Type": kind,
                "Date": item.created_at.strftime("%d/%m/%Y %H:%M"),
                "Durée": f"{item.duration_seconds // 60} min",
                "Score": f"{item.score:.0f} %",
                "Progression": f"{item.mastery_gain:+.1f}",
                "Achèvement": f"{item.completion_rate:.0f} %",
            }
        )
    return rows


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
            from ui.professor_ai_guided_cycle import remember_session_status

            remember_session_status(st.session_state, int(session.session_id), session.status)
            request_navigation(st.session_state, "student", "Ma séance")
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
    from ui.professor_ai_guided_cycle import mark_cycle_synthesis_closed, remember_session_status

    remember_session_status(st.session_state, int(session_id), result.session.status)
    total = max(1, len(result.activities))
    st.title("Séance d'apprentissage")
    left, middle, right = st.columns(3)
    left.metric("Activités terminées", f"{result.completed_activities}/{len(result.activities)}")
    middle.metric("Temps écoulé", f"{result.elapsed_seconds // 60} min")
    right.metric("Temps restant", f"{result.remaining_seconds // 60} min")
    prog_col, calc_col = st.columns([5, 1])
    with prog_col:
        st.progress(
            result.completed_activities / total,
            text=f"Progression de la séance — {_status_label(result.session.status)}",
        )
    with calc_col:
        if st.button("🧮 Calculatrice", help="Ouvre la calculatrice Windows", key="open_calculator", use_container_width=True):
            try:
                subprocess.Popen(["calc.exe"])
            except FileNotFoundError:
                st.warning("Calculatrice introuvable sur ce système.")
    if result.session.status == "RUNNING":
        execution = build_unified_session_execution_service()
        question = execution.current(learner_id, result.session.session_id)
        feedback_key = f"session_feedback_{result.session.session_id}"
        feedback = st.session_state.pop(feedback_key, None)
        if feedback:
            if getattr(feedback, "skipped", False):
                st.toast("Question passée ⏭️", icon="⏭️")
            elif feedback.correct:
                st.toast(f"Bonne réponse ✅ — {feedback.score:.0f} %", icon="✅")
            else:
                st.toast(f"À consolider ❌ — {feedback.score:.0f} %", icon="❌")
        if question:
            st.divider()
            st.caption(f"Question {question.position}/{question.total} · {question.activity_title}")
            if question.instructions:
                st.write(question.instructions)
            if question.context:
                st.info(question.context)
            st.markdown(f"### {question.statement}")
            from services.learning_session.answer_input import (
                SCIENTIFIC_NOTATION_GUIDE,
                needs_scientific_notation_guide,
                prefers_multiline_answer,
            )

            if needs_scientific_notation_guide(
                statement=question.statement,
                instructions=question.instructions or "",
                context=question.context or "",
            ):
                st.info(SCIENTIFIC_NOTATION_GUIDE)
            render_homework_during_guidance(
                actor,
                learner_id,
                result.session.session_id,
                question.activity_id,
                key_prefix=f"session_{result.session.session_id}_{question.question_id}",
                statement=question.statement,
                hint_text=question.hints[0][1] if question.hints else None,
                notion_reminder=question.instructions or None,
                method_outline=None,
            )
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
            elif prefers_multiline_answer(
                question.response_type,
                statement=question.statement,
                instructions=question.instructions or "",
            ):
                st.caption("Tu peux répondre sur plusieurs lignes.")
                answer = st.text_area("Ta réponse", key=answer_key, height=160)
            else:
                st.caption("Saisis ta réponse au clavier (une ligne).")
                answer = st.text_input("Ta réponse", key=answer_key)
            if question.hints:
                with st.expander("Besoin d'un indice ?", expanded=False):
                    for hint_id, _, penalty in question.hints:
                        if st.button(f"Afficher l'indice ({penalty:g} point de pénalité)", key=f"hint_{hint_id}"):
                            text = execution.use_hint(learner_id, result.session.session_id, hint_id, datetime.now(UTC))
                            st.session_state[f"shown_hint_{hint_id}"] = text
                        if shown := st.session_state.get(f"shown_hint_{hint_id}"):
                            st.info(shown)
            started_key = f"question_started_{question.session_id}_{question.question_id}"
            st.session_state.setdefault(started_key, time.monotonic())
            action_cols = st.columns(2)
            _inject_session_button_styles()
            with action_cols[0]:
                st.markdown("<div class='btn3d'>", unsafe_allow_html=True)
                submit_pressed = st.button(
                    "✅ Valider ma réponse",
                    key=f"session_submit_{question.session_id}_{question.question_id}",
                    use_container_width=True,
                    disabled=not str(answer).strip(),
                )
                st.markdown("</div>", unsafe_allow_html=True)
                if submit_pressed:
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
            with action_cols[1]:
                st.markdown("<div class='btn3d'>", unsafe_allow_html=True)
                skip_pressed = st.button(
                    "⏭️ Passer",
                    key=f"session_skip_{question.session_id}_{question.question_id}",
                    use_container_width=True,
                    help="Passe cette question sans bloquer le devoir.",
                )
                st.markdown("</div>", unsafe_allow_html=True)
                if skip_pressed:
                    elapsed = int((time.monotonic() - float(st.session_state[started_key])) * 1000)
                    try:
                        st.session_state[feedback_key] = execution.skip(
                            learner_id,
                            result.session.session_id,
                            datetime.now(UTC),
                            elapsed,
                        )
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
        else:
            st.info("Toutes les questions disponibles ont été traitées.")
    st.divider()
    st.subheader("Activités de la séance", anchor=False)
    for position, activity in enumerate(result.activities, 1):
        with st.container(border=True):
            st.markdown(f"#### Activité {position} — {activity.title}")
            st.write(f"Type : {label(activity.activity_type)} · État : {_status_label(activity.status)}")
            if activity.status == "COMPLETED":
                st.write(f"Score : {activity.score:.0f} %")
    actions = st.columns(3)
    error = None
    action_taken = False
    success_message = None
    if result.session.status == "READY" and actions[0].button("Commencer", type="primary"):
        action_taken = True
        error = controller.start(result.session.session_id, datetime.now(UTC))
        success_message = "Séance démarrée."
    elif result.session.status == "RUNNING" and actions[1].button("Mettre en pause"):
        action_taken = True
        error = controller.pause_for_learner(learner_id, result.session.session_id, datetime.now(UTC))
        success_message = "Séance mise en pause. Tu pourras la reprendre depuis ton tableau de bord ou tes devoirs."
    elif result.session.status == "PAUSED" and actions[0].button("Reprendre", type="primary"):
        action_taken = True
        error = controller.resume_for_learner(learner_id, result.session.session_id, datetime.now(UTC))
        success_message = "Séance reprise."
    if error:
        _error(error)
    elif action_taken:
        if success_message:
            st.success(success_message)
        st.rerun()
    if result.session.status == "COMPLETED":
        closed_key = f"professor_ai_cycle_closed_{result.session.session_id}"
        if not st.session_state.get(closed_key):
            try:
                from application.experience_factory import build_professor_ai_orchestrator

                build_professor_ai_orchestrator().close_session_cycle(
                    actor,
                    learner_id,
                    int(result.session.session_id),
                )
                mark_cycle_synthesis_closed(st.session_state, int(result.session.session_id))
            except Exception:
                mark_cycle_synthesis_closed(st.session_state, int(result.session.session_id))
        explanation = load_session_result_explanation(actor, learner_id, result.session.session_id)
        if explanation:
            render_homework_result_explanation(explanation)
        st.success("Synthèse du cycle prête. Tu peux revenir à l'accueil ou ouvrir un nouveau devoir.")
        home_cols = st.columns(2)
        if home_cols[0].button("Retour à l'accueil", key=f"cycle_home_{result.session.session_id}"):
            request_navigation(st.session_state, "student", "Tableau de bord")
            st.rerun()
        if home_cols[1].button("Mes devoirs", key=f"cycle_hw_{result.session.session_id}"):
            request_navigation(st.session_state, "student", "Devoirs")
            st.rerun()


def student_history(
    controller: StudentExperienceController,
    learner_id: int,
    *,
    homework_items: tuple[object, ...] | None = None,
    show_title: bool = True,
) -> None:
    result = controller.history(learner_id)
    if show_title:
        st.title("Historique des séances")
    else:
        st.subheader("Historique des séances", anchor=False)
    if isinstance(result, PresentationError):
        _error(result)
        return
    if not result:
        st.info("Aucune séance terminée pour le moment.")
        return
    session_kinds: dict[int, str] = {}
    if homework_items:
        for item in homework_items:
            session_id = getattr(item, "session_id", None)
            if session_id is None:
                continue
            is_evaluation = bool(getattr(item, "is_evaluation", False))
            session_kinds[int(session_id)] = "Évaluation" if is_evaluation else "Devoir"
    st.dataframe(_history_rows(result, session_kinds=session_kinds), use_container_width=True, hide_index=True)


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
