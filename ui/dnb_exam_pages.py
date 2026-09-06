"""LCAI-0031 Phase 6 — pages Sujets Brevet / Blancs / Oral (shells produit)."""

from __future__ import annotations

import streamlit as st

from services import dnb as dnb_service
from services.dnb import BrevetExamMode


def render_sujets_brevet_page(*, learner_id: int) -> None:
    _ = learner_id
    st.title("Sujets Brevet")
    st.caption("Formats d'épreuve DNB — distincts des devoirs personnalisés.")
    templates = (
        ("MATHEMATICS_WRITTEN", "Mathématiques"),
        ("FRENCH_WRITTEN", "Français"),
        ("HISTORY_GEOGRAPHY_EMC_WRITTEN", "Histoire-Géo-EMC"),
        ("SCIENCES_WRITTEN", "Sciences (2 disciplines / 3)"),
    )
    for code, label in templates:
        try:
            blueprint = dnb_service.brevet_exam(code, mode=BrevetExamMode.BREVET_STYLE.value)
        except Exception as exc:
            with st.container(border=True):
                st.markdown(f"**{label}**")
                st.caption(str(exc))
            continue
        template = blueprint.template
        with st.container(border=True):
            st.markdown(f"**{template.label}** · mode {blueprint.mode.value}")
            st.caption(f"Durée indicative : {template.duration_minutes} min")
            for section in blueprint.section_plan[:8]:
                st.write(f"• {section.label} ({section.duration_minutes} min)")
            if blueprint.rules:
                st.caption("Règles : " + " · ".join(blueprint.rules[:3]))
    st.info(
        "Les annales officielles et les sujets générés restent distincts "
        "(jamais d'IA marquée « officielle »)."
    )


def render_brevet_blancs_page(*, learner_id: int) -> None:
    _ = learner_id
    st.title("Brevets blancs")
    st.caption("Simulation globale des écrits (± oral).")
    try:
        session = dnb_service.mock_brevet_session(include_oral=False)
    except Exception as exc:
        st.error(str(exc))
        return
    st.subheader("Session blanche proposée", anchor=False)
    for exam in session:
        template = exam.template
        with st.container(border=True):
            st.markdown(f"**{template.label}**")
            st.caption(
                f"Code {template.exam_code.value} · {template.duration_minutes} min · mode {exam.mode.value}"
            )
            for section in exam.section_plan[:4]:
                st.write(f"• {section.label}")
    st.info("Exécution complète en séance et correction détaillée : à brancher en validation / Phase 7.")


def render_oral_page(*, learner_id: int) -> None:
    _ = learner_id
    st.title("Oral du Brevet")
    st.caption("Préparation du projet + questions de jury (Coach Brevet).")
    with st.form("oral_project_form"):
        title = st.text_input("Titre du projet", value="Mon projet interdisciplinaire")
        problematique = st.text_area(
            "Problématique",
            value="En quoi ce sujet éclaire un enjeu de société ?",
            height=80,
        )
        outline_raw = st.text_area(
            "Plan (une idée par ligne)",
            value="Introduction\nDéveloppement\nConclusion",
            height=100,
        )
        submitted = st.form_submit_button("Générer le parcours oral", type="primary")
    if not submitted:
        st.caption("Renseigne ton projet pour obtenir étapes et questions jury.")
        return
    outline = tuple(line.strip() for line in outline_raw.splitlines() if line.strip())
    try:
        project = dnb_service.oral_project(title=title, problematique=problematique, outline=outline)
        jury = dnb_service.oral_jury_pack(project)
    except Exception as exc:
        st.error(str(exc))
        return
    st.subheader("Parcours", anchor=False)
    for stage in project.stages:
        st.write(f"• {stage.value}")
    st.caption(f"Durée cible : ~{project.target_minutes} min")
    st.subheader("Questions jury", anchor=False)
    for question in jury:
        st.write(f"• [{question.kind.value}] {question.prompt}")
