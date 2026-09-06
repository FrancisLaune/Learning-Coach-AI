"""LCAI-0031 Phase 6 — dashboard parent Objectif Brevet (§30)."""

from __future__ import annotations

from contextlib import suppress
from typing import Any

import streamlit as st

from services.dnb.coach import coach_context_from_home
from services.dnb.coach_decisions import decide_next_work, format_decision_for_student


def project_dnb_band(readiness: float | None) -> tuple[str, str]:
    """Fourchette de projection (pas de fausse précision)."""
    if readiness is None:
        return "non calculée", "faible"
    mid = 8.0 + float(readiness) * 10.0
    low = max(0.0, round(mid - 1.5, 1))
    high = min(20.0, round(mid + 1.5, 1))
    confidence = "élevée" if readiness >= 0.7 else "moyenne" if readiness >= 0.45 else "faible"
    return f"{low:g} – {high:g} / 20", confidence


def render_parent_brevet_overview(
    *,
    display_name: str,
    learner_id: int,
    metric_cards: Any | None = None,
    mastery_rows: tuple[Any, ...] = (),
    fragile_labels: tuple[str, ...] = (),
    strong_labels: tuple[str, ...] = (),
    homework_todo: int = 0,
    homework_overdue: int = 0,
    recent_sessions: int = 0,
    recommended_minutes: int | None = None,
) -> None:
    """Vue générale parent — alertes et actions, sans détail algo difficulté."""
    _ = learner_id
    st.title(f"Vue générale — {display_name}")
    st.caption("Objectif Brevet 2027 · suivi parental")

    if metric_cards is not None:
        with suppress(TypeError):
            metric_cards()

    # Build a light coach pack from mastery-like rows if possible
    coach = coach_context_from_home(
        display_name=display_name,
        fragile=(),
        strong=(),
        mastery=(),
    )
    # Override fragile/strong from labels when mastery objects unavailable
    decision = decide_next_work(coach)
    projection, confidence = project_dnb_band(coach.readiness_score)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Jours avant DNB", "—" if coach.days_until_exam is None else str(coach.days_until_exam))
    c2.metric("Readiness", f"{coach.readiness_score:.0%}" if coach.readiness_score is not None else "—")
    c3.metric("Devoirs à faire", str(homework_todo))
    c4.metric("Devoirs en retard", str(homework_overdue))

    with st.container(border=True):
        st.subheader("Projection DNB", anchor=False)
        st.write(f"**{projection}** · confiance {confidence}")
        st.caption("Fourchette indicative — pas une note officielle.")

    with st.container(border=True):
        st.subheader("Régularité & temps de travail", anchor=False)
        minutes = recommended_minutes if recommended_minutes is not None else 30
        st.write(
            f"Séances récentes suivies : {recent_sessions}. "
            f"Temps conseillé / session : ~{minutes} min."
        )
        if recent_sessions == 0:
            st.warning("Peu d'activité récente — encourager une séance courte cette semaine.")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Points d'alerte", anchor=False)
        if homework_overdue:
            st.error(f"{homework_overdue} devoir(s) en retard.")
        if fragile_labels:
            for label in fragile_labels[:5]:
                st.write(f"• {label}")
        elif not homework_overdue:
            st.caption("Aucune alerte majeure pour le moment.")
    with col_b:
        st.subheader("Points solides", anchor=False)
        if strong_labels:
            for label in strong_labels[:5]:
                st.write(f"• {label}")
        else:
            st.caption("En attente de davantage d'activités évaluées.")

    with st.container(border=True):
        st.subheader("Maîtrise par matière", anchor=False)
        if mastery_rows:
            for row in mastery_rows[:12]:
                label = getattr(row, "label", None) or getattr(row, "skill_label", None) or str(row)
                subject = getattr(row, "subject_label", "") or ""
                score = getattr(row, "score", None)
                if score is None:
                    score = getattr(row, "mastery_score", None)
                score_txt = f"{float(score):.0f} %" if score is not None else "—"
                st.write(f"• {subject}: {label} — {score_txt}" if subject else f"• {label} — {score_txt}")
        else:
            st.caption("Pas encore de maîtrise agrégée.")

    with st.container(border=True):
        st.subheader("Recommandations & actions", anchor=False)
        st.write(format_decision_for_student(decision))
        st.write("Actions concrètes :")
        st.write("1. Vérifier les devoirs en retard et fixer une échéance réaliste.")
        st.write("2. Encourager une révision sur le point le plus fragile.")
        st.write("3. Planifier un Brevet blanc quand la readiness le permet.")

    with st.container(border=True):
        st.subheader("Contrôle continu & blancs", anchor=False)
        st.write(
            "Anglais / Espagnol : suivi en contrôle continu (hors écrits terminaux standard). "
            "Les Brevets blancs et sujets d'écrits se préparent dans l'espace élève."
        )
        if coach.mock_exam_hint:
            st.caption(coach.mock_exam_hint)


def render_parent_alerts(
    *,
    display_name: str,
    homework_overdue: int,
    fragile_labels: tuple[str, ...],
) -> None:
    st.title(f"Alertes & recommandations — {display_name}")
    if homework_overdue:
        st.error(f"{homework_overdue} devoir(s) en retard à traiter.")
    if fragile_labels:
        st.warning("Compétences fragiles :")
        for label in fragile_labels:
            st.write(f"• {label}")
    if not homework_overdue and not fragile_labels:
        st.success("Pas d'alerte critique — maintenir la régularité.")
    st.info("Le détail des algorithmes de difficulté n'est pas exposé aux parents.")


def render_parent_continuous_assessment(*, display_name: str) -> None:
    st.title(f"Contrôle continu — {display_name}")
    st.write(
        "Suivi des matières de contrôle continu (notamment langues vivantes). "
        "Saisie fine des notes scolaires : à enrichir ; pour l'instant, rappels produit uniquement."
    )
    st.caption("Ne pas confondre contrôle continu et épreuves terminales du DNB.")


def render_parent_brevet_prep(*, display_name: str) -> None:
    st.title(f"Préparation Brevet — {display_name}")
    calendar = __import__("services.dnb", fromlist=["exam_calendar"]).exam_calendar()
    days = calendar.countdown_days()
    st.metric("Jours avant le premier écrit", "—" if days is None else str(days))
    st.write("Écrits configurés :")
    for item in calendar.written_exams:
        st.write(f"• {item.label} — {item.exam_date.isoformat()}")
    try:
        mocks = __import__("services.dnb", fromlist=["mock_brevet_session"]).mock_brevet_session()
        st.subheader("Structure d'un Brevet blanc", anchor=False)
        for exam in mocks:
            st.write(f"• {getattr(exam, 'exam_code', exam)}")
    except Exception as exc:
        st.caption(str(exc))
