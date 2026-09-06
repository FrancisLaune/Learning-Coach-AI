"""LCAI-0031 Phase 6 — Accueil élève Objectif Brevet (§29)."""

from __future__ import annotations

import streamlit as st

from application.dto.student_guidance import StudentDashboardSnapshot
from services.dnb.coach import coach_context_from_home
from services.dnb.coach_decisions import decide_next_work, format_decision_for_student
from services.learning_session.experience import StudentDashboard
from ui.navigation import request_navigation


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.0%}"


def render_brevet_student_home(
    *,
    snapshot: StudentDashboardSnapshot,
    dashboard: StudentDashboard | None = None,
) -> None:
    """Dashboard élève §29 — sans surcharge de métriques techniques."""
    context = snapshot.context
    coach = coach_context_from_home(
        display_name=context.display_name,
        objective=context.objective,
        fragile=context.fragile_skills,
        strong=context.strong_skills,
        mastery=context.mastery,
        revision_priorities=context.revision_priorities,
        recent_score=context.recent_score,
        success_rate=context.success_rate,
    )
    decision = decide_next_work(coach)

    st.title(f"Objectif Brevet — {context.display_name}")
    st.caption("Préparation au DNB 2027 · Coach Brevet unique")

    # 1. Countdown
    cols = st.columns(3)
    days = coach.days_until_exam
    cols[0].metric("Jours avant le DNB", "—" if days is None else str(days))
    cols[1].metric("Readiness", _pct(coach.readiness_score))
    cols[2].metric("Niveau readiness", coach.readiness_band or "—")
    if coach.exam_dates_summary:
        st.caption(f"Calendrier (config versionnée) : {coach.exam_dates_summary}")

    # 2. Weekly objective + 3. Next session
    with st.container(border=True):
        st.subheader("Objectif de la semaine", anchor=False)
        st.write(coach.weekly_objective or context.objective or "Lancer un diagnostic et fixer une priorité.")
        if coach.mock_exam_hint:
            st.caption(coach.mock_exam_hint)
        if dashboard is not None and dashboard.current_session is not None:
            session = dashboard.current_session
            st.info(
                f"Prochaine session : séance en cours/planifiée "
                f"({dashboard.recommended_duration_minutes} min, état {session.status})."
            )
        elif context.revision_priorities:
            top = context.revision_priorities[0]
            st.info(
                f"Prochaine session recommandée : {top.skill_label} ({top.subject_label}) "
                f"— ~{top.estimated_minutes} min."
            )
        else:
            st.info("Prochaine session : ouvre « S'entraîner » ou « Réviser » pour démarrer.")

    # 4. Program progress (lightweight)
    mastery_count = len(context.mastery)
    fragile_count = len(context.fragile_skills)
    with st.container(border=True):
        st.subheader("Progression programme", anchor=False)
        st.write(
            f"{mastery_count} compétence(s) suivie(s) · {fragile_count} point(s) fragile(s). "
            f"Moyenne générale : "
            f"{'—' if context.overall_average_out_of_20 is None else f'{context.overall_average_out_of_20:g}/20'}."
        )
        if coach.readiness_explanation:
            st.caption(coach.readiness_explanation)

    # 5–6. Strong / weak
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Points forts", anchor=False)
        if context.strong_skills:
            for item in context.strong_skills[:5]:
                st.write(f"• {item.subject_label}: {item.label} ({item.score:.0f} %)")
        else:
            st.caption("Pas encore assez de données.")
    with col_b:
        st.subheader("Points faibles", anchor=False)
        if context.fragile_skills:
            for item in context.fragile_skills[:5]:
                st.write(f"• {item.subject_label}: {item.label} ({item.score:.0f} %)")
        else:
            st.caption("Aucun point fragile détecté pour l'instant.")

    # 7. Due revisions
    with st.container(border=True):
        st.subheader("Révisions dues", anchor=False)
        if context.revision_priorities:
            for item in context.revision_priorities[:5]:
                st.write(f"• {item.subject_label} — {item.skill_label} ({item.reason})")
        elif context.next_revision:
            st.write(f"Prochaine révision suggérée : {context.next_revision.strftime('%d/%m/%Y')}")
        else:
            st.caption("Aucune révision planifiée — le Coach te proposera une priorité.")

    # 8. Next mock
    with st.container(border=True):
        st.subheader("Prochain Brevet blanc", anchor=False)
        st.write(coach.mock_exam_hint or "Planifie un blanc quand la readiness le permettra.")
        if st.button("Voir les Brevets blancs", key=f"home_mock_{context.learner_id}"):
            request_navigation(st.session_state, "student", "Brevets blancs")
            st.rerun()

    # 9. Coach message
    with st.container(border=True):
        st.subheader("Message du Coach Brevet", anchor=False)
        greeting = snapshot.welcome.greeting
        st.write(greeting)
        st.caption(format_decision_for_student(decision))
        if snapshot.welcome.primary_action:
            st.info(f"Action prioritaire : {snapshot.welcome.primary_action}")

    actions = st.columns(4)
    navs = (
        ("Devoir personnalisé", f"home_hw_{context.learner_id}"),
        ("S'entraîner", f"home_train_{context.learner_id}"),
        ("Réviser", f"home_rev_{context.learner_id}"),
        ("Coach Brevet", f"home_coach_{context.learner_id}"),
    )
    for column, (label, key) in zip(actions, navs, strict=True):
        if column.button(label, key=key, use_container_width=True):
            request_navigation(st.session_state, "student", label)
            st.rerun()

    from ui.chatgpt_voice import render_chatgpt_voice_access

    render_chatgpt_voice_access(
        snapshot=snapshot,
        expanded=False,
        key_prefix=f"home_chatgpt_{context.learner_id}",
    )
