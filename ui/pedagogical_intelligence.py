"""Streamlit views for LCAI-0019 pedagogical intelligence (Phase 2)."""

from __future__ import annotations

import streamlit as st

from application.dto.pedagogical_intelligence import PedagogicalDashboardDTO
from application.pedagogical_intelligence_controllers import PedagogicalIntelligenceController, PresentationError
from domain.pedagogical_intelligence.models import PedagogicalIntelligenceOverview

CACHE_KEY = "lcai0019_dashboard_cache"
RUN_KEY = "lcai0019_diagnostic_run_id"
EXERCISE_KEY = "lcai0019_current_exercise_id"
REFRESH_KEY = "lcai0019_refresh_version"


def _band_label(band: str) -> str:
    return {"READY": "Prêt", "ALMOST_READY": "Presque prêt", "NOT_READY": "À renforcer"}.get(band, band)


def _load_dashboard(
    controller: PedagogicalIntelligenceController,
    learner_id: int,
    *,
    parent_ref: str | None = None,
) -> PedagogicalDashboardDTO | PresentationError:
    cache = st.session_state.get(CACHE_KEY, {})
    version = st.session_state.get(REFRESH_KEY, "v0")
    cached = cache.get(str(learner_id))
    if cached and cached.get("version") == version:
        return cached["dto"]
    result = (
        controller.parent_dashboard(parent_ref, learner_id, cache_version=version)
        if parent_ref
        else controller.student_dashboard(learner_id, cache_version=version)
    )
    if not isinstance(result, PresentationError):
        cache[str(learner_id)] = {"version": version, "dto": result}
        st.session_state[CACHE_KEY] = cache
    return result


def invalidate_dashboard_cache() -> None:
    st.session_state[REFRESH_KEY] = f"v{int(str(st.session_state.get(REFRESH_KEY, 'v0')).replace('v', '') or 0) + 1}"
    st.session_state.pop(CACHE_KEY, None)


def render_dashboard_dto(dto: PedagogicalDashboardDTO, *, parent: bool = False) -> None:
    path_code = getattr(dto.overview.active_path, "code", "") if dto.overview.active_path else ""
    if path_code == "FR_3E_DNB_BASELINE":
        st.subheader("Préparation au DNB 2027", anchor=False)
    else:
        st.subheader("Préparation au changement de niveau", anchor=False)
    columns = st.columns(4)
    columns[0].metric("Score global", f"{dto.readiness_score * 100:.0f} %")
    columns[1].metric("Couverture", f"{dto.coverage_score * 100:.0f} %")
    columns[2].metric("Confiance", f"{dto.confidence_score * 100:.0f} %")
    columns[3].metric("Statut", _band_label(dto.readiness_status))
    st.caption(f"Parcours : {dto.pathway_code} · Sources : {', '.join(dto.data_sources)}")
    st.caption(f"Dernier calcul : {dto.last_computed_at.strftime('%d/%m/%Y %H:%M')}")

    if dto.strong_skills:
        st.markdown("**Forces**")
        for item in dto.strong_skills[:5]:
            st.write(f"- {item.label} ({item.mastery_score * 100:.0f} %)")
    if dto.critical_gaps:
        st.markdown("**Priorités**")
        for item in dto.critical_gaps[:5]:
            st.write(f"- {item.label} ({item.reason})")
    if dto.recommendations:
        st.markdown("**Recommandations**")
        for item in dto.recommendations[:5]:
            st.write(f"- [{item.priority}] {item.reason}")
    if dto.current_plan and dto.current_plan.highlights:
        st.markdown("**Plan 7 jours**")
        for highlight in dto.current_plan.highlights:
            st.write(f"- {highlight}")
    if not parent:
        st.info(dto.pedagogical_message)


def render_diagnostic_panel(
    controller: PedagogicalIntelligenceController,
    learner_id: int,
    overview: PedagogicalIntelligenceOverview,
    *,
    key_prefix: str,
) -> None:
    st.subheader("Diagnostic adaptatif", anchor=False)
    if overview.active_path is None:
        st.info("Diagnostic indisponible pour cette classe.")
        return

    run_id = st.session_state.get(RUN_KEY)
    if overview.active_diagnostic is not None:
        run_id = overview.active_diagnostic.id
        st.session_state[RUN_KEY] = run_id

    if run_id and overview.active_diagnostic is not None:
        run_dto = controller.start_diagnostic(learner_id, overview.active_path.code)
        if isinstance(run_dto, PresentationError):
            st.error(run_dto.message)
            return
        item = run_dto.current_item
        if item is None:
            st.warning("Aucun exercice diagnostic disponible pour ce parcours.")
            return
        st.session_state[EXERCISE_KEY] = item.exercise_id
        st.write(f"**Question {item.sequence_number}** — {item.prompt}")
        answer = st.text_input("Ta réponse", key=f"{key_prefix}_diag_answer")
        if st.button("Valider ma réponse", key=f"{key_prefix}_diag_submit"):
            if not answer.strip():
                st.warning("Saisis une réponse avant de continuer.")
            else:
                result = controller.submit_diagnostic_answer(
                    run_id=int(run_id),
                    learner_id=learner_id,
                    exercise_id=int(item.exercise_id),
                    answer=answer,
                )
                if isinstance(result, PresentationError):
                    st.error(result.message)
                else:
                    st.write(result.feedback)
                    invalidate_dashboard_cache()
                    if result.should_continue and result.next_item is not None:
                        st.session_state[EXERCISE_KEY] = result.next_item.exercise_id
                        st.rerun()
                    else:
                        st.success("Diagnostic terminé.")
                        st.session_state.pop(RUN_KEY, None)
                        st.rerun()
        return

    if st.button("Lancer le diagnostic", key=f"{key_prefix}_start_diag"):
        run_dto = controller.start_diagnostic(learner_id, overview.active_path.code)
        if isinstance(run_dto, PresentationError):
            st.error(run_dto.message)
        elif run_dto.current_item is None:
            st.warning("Aucun contenu diagnostic publié n'est disponible.")
        else:
            st.session_state[RUN_KEY] = int(run_dto.run_id)
            st.session_state[EXERCISE_KEY] = run_dto.current_item.exercise_id
            st.rerun()


def render_pedagogical_intelligence_dashboard(
    controller: PedagogicalIntelligenceController,
    overview: PedagogicalIntelligenceOverview,
    learner_id: int,
    *,
    key_prefix: str,
    show_diagnostic: bool = True,
    parent_ref: str | None = None,
) -> None:
    dto = _load_dashboard(controller, learner_id, parent_ref=parent_ref)
    if isinstance(dto, PresentationError):
        st.warning(dto.message)
        return
    render_dashboard_dto(dto, parent=parent_ref is not None)
    if show_diagnostic:
        render_diagnostic_panel(controller, learner_id, overview, key_prefix=key_prefix)
