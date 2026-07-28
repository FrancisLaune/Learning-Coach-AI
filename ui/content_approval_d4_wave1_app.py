"""Streamlit interne — file de revue LCAI-0012D4 Wave 1 (54 candidats max)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from scripts.run_content_approval_acceleration import _review_taxonomy
from scripts.run_content_approval_d4_wave1 import _coverage_rows
from scripts.run_content_quality_audit import _candidate_sources
from services.content.d4_wave1 import (
    PEDAGOGICAL_WARNING_FR,
    WAVE_BAND_FINAL,
    WAVE_BAND_G2,
    WAVE_BAND_TIER2,
    append_final_generated_candidates,
    build_active_wave1_queue,
    build_wave1_final_human_queue,
    build_wave1_targets,
    g2_complement_plan,
    normalize_wave1_review_queue,
    pedagogical_attention_reason,
    prepare_ranked_records,
    projected_tier1_totals,
    requires_pedagogical_attention,
)
from services.runtime import prepare_runtime
from ui.i18n import grade_label, label, subject_label, tier_label

ROOT = Path(__file__).resolve().parents[1]
QUALITY = ROOT / "resources" / "content" / "quality"

WAVE_BAND_LABELS = {
    WAVE_BAND_TIER2: "Complétion Tier 2 → Tier 1",
    WAVE_BAND_G2: "G2 — candidat existant (complément après approbation)",
    WAVE_BAND_FINAL: "Finalisation Wave 1 — dernières compétences Tier 1",
}


def _load_quality_inputs() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], set[str], set[str]]:
    results = json.loads((QUALITY / "lcai_0012d_quality_results.json").read_text(encoding="utf-8"))
    duplicates = json.loads((QUALITY / "lcai_0012d_duplicate_audit.json").read_text(encoding="utf-8"))
    sources = _candidate_sources()
    near_codes = {
        str(item[key])
        for item in duplicates["near_groups"]
        for key in ("left", "right")
        if item["decision"] == "REVIEW"
    }
    _, resolved = _review_taxonomy(results, sources, near_codes)
    return results, sources, near_codes, resolved


def _rebuild_wave1_state(
    repository: DuckDBContentQualityRepository,
    *,
    skipped: set[int],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    results, sources, near_codes, resolved = _load_quality_inputs()
    coverage_rows = _coverage_rows()
    coverage = {str(row["skill"]): row for row in coverage_rows}
    ranked = prepare_ranked_records(
        results,
        sources,
        coverage,
        near_codes=near_codes,
        resolved=resolved,
    )
    targets = build_wave1_targets(coverage_rows, ranked)
    review_statuses = repository.approval_queue_review_statuses()
    queue, summary = build_active_wave1_queue(
        targets,
        coverage_rows,
        review_statuses,
        skipped=skipped,
    )
    complements = g2_complement_plan(targets, review_statuses)
    if queue:
        summary["projection"] = projected_tier1_totals(coverage_rows, targets)
    else:
        queue, final_summary = build_wave1_final_human_queue(coverage_rows, ranked, review_statuses)
        coverage_by_skill = {str(row["skill"]): row for row in coverage_rows}
        queue = append_final_generated_candidates(
            queue,
            artifact_path=QUALITY / "lcai_0012d4_wave1_final_svt_assessment.json",
            review_statuses=review_statuses,
            baseline_tier1=final_summary["baseline_tier1"],
            coverage_by_skill=coverage_by_skill,
        )
        final_summary["queue_size"] = len(queue)
        final_summary["projected_tier1_if_all_approved"] = final_summary["baseline_tier1"] + len(queue)
        summary = {
            **summary,
            **final_summary,
            "finalization_mode": True,
            "projection": {
                "baseline_tier1": final_summary["baseline_tier1"],
                "after_all_final_approvals": final_summary["projected_tier1_if_all_approved"],
            },
        }
    summary["g2_complements_ready"] = sum(1 for item in complements if item["ready_to_generate"])
    summary["g2_complements_total"] = len(complements)
    if queue:
        queue = normalize_wave1_review_queue(queue, coverage_rows)
    return queue, summary, complements


def _persist_and_verify_decision(
    repository: DuckDBContentQualityRepository,
    *,
    item: dict[str, Any],
    action: str,
    reviewer: str,
    approver: str,
    reason: str,
    explicit_pedagogical_confirmation: bool = False,
) -> dict[str, Any]:
    version_id = int(item["version_id"])
    if action == "APPROVE":
        repository.approve_for_production(
            item=item,
            reviewer=reviewer,
            approver=approver,
            reason=reason,
            human_pedagogical_confirmation=(
                explicit_pedagogical_confirmation if requires_pedagogical_attention(item) else False
            ),
        )
        expected_status = "APPROVED"
    elif action in {"REJECT", "KEEP_FOR_REVIEW"}:
        repository.record_human_decision(
            version_id=version_id,
            reviewer=reviewer,
            decision=action,
            notes=reason,
        )
        expected_status = "REJECTED" if action == "REJECT" else "KEEP_REVIEW"
    else:
        raise ValueError(f"Action non supportée : {action}")

    persisted = repository.read_human_decision(version_id)
    if persisted is None or persisted.get("review_status") != expected_status:
        raise RuntimeError("La décision n’a pas pu être confirmée après écriture.")
    if action == "APPROVE" and not persisted.get("production_enabled"):
        raise RuntimeError("L’approbation Wave 1 n’a pas activé la production.")
    return persisted


def _display_impact(item: dict[str, Any]) -> None:
    impact = item["coverage_impact"]
    band = str(item.get("wave_band"))
    if band in {WAVE_BAND_TIER2, WAVE_BAND_FINAL} and impact["completes_tier_1"]:
        st.success("🟢 **IMPACT : cette validation complète la compétence (Tier 1)**")
    elif band == WAVE_BAND_G2:
        st.info("🔵 **IMPACT G2 : cette validation couvre un slot ; le complément sera généré ensuite.**")
    elif impact["improves_tier_2"]:
        st.warning("🟡 **IMPACT : amélioration partielle de la couverture (Tier 2)**")
    else:
        st.info("⚪ **IMPACT : aucun effet Tier 1 immédiat**")

    current, potential = impact["current"], impact["potential"]
    left, right = st.columns(2)
    left.markdown(
        "**Statut actuel**  \n"
        f"- Entraînement approuvé : {'Oui' if current['practice_approved'] else 'Non'}  \n"
        f"- Évaluation approuvée : {'Oui' if current['assessment_approved'] else 'Non'}  \n"
        f"- État : **{tier_label(int(current['tier']))}**"
    )
    right.markdown(
        "**Après approbation**  \n"
        f"- Entraînement approuvé : {'Oui' if potential['practice_approved'] else 'Non'}  \n"
        f"- Évaluation approuvée : {'Oui' if potential['assessment_approved'] else 'Non'}  \n"
        f"- État : **{tier_label(int(potential['tier']))}**"
    )


def run() -> None:
    prepare_runtime()
    st.set_page_config(page_title="LCAI — Wave 1 D4", layout="wide")
    st.title("LCAI-0012D4 — Wave 1 · Objectif 100 Tier 1")
    st.caption("File minimale : 1 meilleur candidat par compétence Tier 2 ou G2. Pas de revue des 798 Drafts.")

    repository = DuckDBContentQualityRepository()
    skipped = set(st.session_state.get("d4_wave1_skipped_versions", set()))
    queue, summary, complements = _rebuild_wave1_state(repository, skipped=skipped)
    projection = summary["projection"]

    metrics = st.columns(5)
    metrics[0].metric("File active", summary["queue_size"])
    metrics[1].metric("Tier 2", summary["tier2_selected"])
    metrics[2].metric("G2", summary["g2_selected"])
    metrics[3].metric("Tier 1 actuel", projection["baseline_tier1"])
    metrics[4].metric(
        "Tier 1 cible Wave 1",
        projection.get(
            "after_g2_complements", projection.get("after_all_final_approvals", projection["baseline_tier1"])
        ),
    )

    if summary.get("finalization_mode"):
        st.info(
            f"**Finalisation Wave 1 :** Tier 1 actuel **{projection['baseline_tier1']}** → "
            f"**{projection['after_all_final_approvals']}** après approbation des {summary['queue_size']} candidats restants."
        )
    else:
        st.markdown(
            f"**Projection :** {projection['baseline_tier1']} → "
            f"{projection['after_tier2_approvals']} (Tier 2) → "
            f"{projection['after_g2_complements']} (avec compléments G2)"
        )

    with st.expander("Compléments G2 (génération après approbation)"):
        ready = [item for item in complements if item["ready_to_generate"]]
        waiting = [item for item in complements if not item["ready_to_generate"]]
        st.write(f"Prêts à générer : **{len(ready)}** · En attente d’approbation : **{len(waiting)}**")
        if ready:
            st.warning("Lancez `python scripts/run_content_d4_wave1_generation.py` après validation des candidats G2.")
        for item in complements:
            slot = "Entraînement" if item["generate_slot"] == "practice" else "Évaluation"
            st.write(
                f"- {grade_label(item['grade'])} · {subject_label(item['subject'])} · "
                f"`{item['skill']}` · complément **{slot}** · {label(item['status'].lower())}"
            )

    if not queue:
        st.success("Aucun candidat Wave 1 restant dans la file active.")
        return

    st.sidebar.header("Revue humaine")
    reviewer = st.sidebar.text_input("Relecteur")
    approver = st.sidebar.text_input("Approbateur")
    reason = st.sidebar.text_area("Motif", value="Revue humaine LCAI-0012D4 Wave 1.")
    explicit_pedagogical_confirmation = False
    grade_filter = st.sidebar.selectbox(
        "Niveau",
        ("Tous", "FR-3E", "FR-4E"),
        format_func=lambda value: "Tous" if value == "Tous" else grade_label(value),
    )
    band_filter = st.sidebar.selectbox(
        "Bande",
        ("Toutes", WAVE_BAND_TIER2, WAVE_BAND_G2),
        format_func=lambda value: "Toutes" if value == "Toutes" else WAVE_BAND_LABELS.get(str(value), str(value)),
    )

    filtered = queue
    if grade_filter != "Tous":
        filtered = [item for item in filtered if item["grade"] == grade_filter]
    if band_filter != "Toutes":
        filtered = [item for item in filtered if item["wave_band"] == band_filter]
    st.sidebar.metric("Résultats filtrés", len(filtered))

    if not filtered:
        st.info("Aucun candidat pour cette sélection.")
        return

    stored_version = st.session_state.get("d4_wave1_current_version_id")
    index = 0
    if stored_version is not None:
        for position, candidate in enumerate(filtered):
            if int(candidate["version_id"]) == int(stored_version):
                index = position
                break
    else:
        index = min(int(st.session_state.get("d4_wave1_queue_index", 0)), len(filtered) - 1)

    item = filtered[index]
    st.session_state.d4_wave1_queue_index = index
    st.session_state.d4_wave1_current_version_id = int(item["version_id"])

    nav_prev, nav_pos, nav_next = st.columns((1, 2, 1))
    if nav_prev.button("← Précédent", disabled=index == 0):
        st.session_state.d4_wave1_current_version_id = int(filtered[index - 1]["version_id"])
        st.rerun()
    nav_pos.write(
        f"**{index + 1}/{len(filtered)}** · rang Wave 1 **{item['wave1_rank']}** · "
        f"{WAVE_BAND_LABELS.get(str(item['wave_band']), item['wave_band'])}"
    )
    if nav_next.button("Suivant →", disabled=index >= len(filtered) - 1):
        st.session_state.d4_wave1_current_version_id = int(filtered[index + 1]["version_id"])
        st.rerun()

    st.subheader(f"{grade_label(item['grade'])} · {subject_label(item['subject'])} · {item['chapter']}")
    st.write(f"**Compétence :** {item.get('skill_name', item['skill'])} (`{item['skill']}`)")
    st.write(
        f"**Slot visé :** {item.get('missing_slot_label', item['content_type'])} · "
        f"**Score :** {item['candidate_score']}/100 · "
        f"**Alternatives restantes :** {item.get('alternate_count', 0)}"
    )
    _display_impact(item)

    if summary.get("finalization_mode") and item.get("projected_tier1_if_approved") is not None:
        st.warning(f"**Projection si ce candidat est approuvé : Tier 1 = {item['projected_tier1_if_approved']}**")

    if requires_pedagogical_attention(item):
        st.error(PEDAGOGICAL_WARNING_FR)
        st.markdown(f"**Motif :** {pedagogical_attention_reason(item)}")
        explicit_pedagogical_confirmation = st.sidebar.checkbox(
            "Je confirme la validation pédagogique explicite",
            key=f"d4_wave1_pedagogical_confirm_{item['version_id']}",
        )

    st.markdown("### Question")
    st.write(item["question"])
    if item.get("choices"):
        st.markdown("### Choix")
        for choice in item["choices"]:
            st.write(f"- {choice}")
    st.markdown("### Réponse attendue")
    st.code(str(item["expected_answer"]))
    st.markdown("### Explication")
    st.write(item["explanation"])

    left, right = st.columns(2)
    left.markdown("**Vérifications automatiques**")
    left.json(
        {
            "Structure": item["automated_checks"].get("structural_validity"),
            "Alignement curriculaire": item["automated_checks"].get("curriculum_alignment"),
            "Alignement compétence": item["automated_checks"].get("skill_alignment"),
            "Réponse": item["automated_checks"].get("answer_correctness"),
            "Vérification déterministe": item["deterministic_verification"],
            "Doublon": item["automated_checks"].get("duplicate_safety"),
            "Exécutabilité": item["automated_checks"].get("executability"),
            "Niveau": item["automated_checks"].get("grade_appropriateness"),
        }
    )
    right.markdown("**Qualité**")
    right.json(
        {
            "résultat": label(item["quality_result"]),
            "recommandation": label(item["recommended_decision"]),
            "motif": item["quality_reason"],
        }
    )

    approve, reject, keep, skip = st.columns(4)
    identities_ready = bool(reviewer.strip() and approver.strip() and reviewer != approver)
    pedagogical_ready = not requires_pedagogical_attention(item) or explicit_pedagogical_confirmation
    can_approve = (
        identities_ready
        and pedagogical_ready
        and item["hard_gates_passed"]
        and item["recommended_decision"] != "REJECT"
    )

    if approve.button("Approuver", type="primary", disabled=not can_approve):
        try:
            _persist_and_verify_decision(
                repository,
                item=item,
                action="APPROVE",
                reviewer=reviewer.strip(),
                approver=approver.strip(),
                reason=reason.strip(),
                explicit_pedagogical_confirmation=explicit_pedagogical_confirmation,
            )
            st.success("Approbation confirmée. Couverture recalculée au prochain affichage.")
            st.rerun()
        except (RuntimeError, ValueError) as exc:
            st.error(str(exc))

    if reject.button("Rejeter", disabled=not reviewer.strip()):
        try:
            _persist_and_verify_decision(
                repository,
                item=item,
                action="REJECT",
                reviewer=reviewer.strip(),
                approver="",
                reason=reason.strip(),
            )
            st.info("Candidat rejeté. Le second meilleur sera proposé automatiquement.")
            st.rerun()
        except (RuntimeError, ValueError) as exc:
            st.error(str(exc))

    if keep.button("Maintenir en révision", disabled=not reviewer.strip()):
        try:
            _persist_and_verify_decision(
                repository,
                item=item,
                action="KEEP_FOR_REVIEW",
                reviewer=reviewer.strip(),
                approver="",
                reason=reason.strip(),
            )
            st.rerun()
        except (RuntimeError, ValueError) as exc:
            st.error(str(exc))

    if skip.button("Ignorer (session)"):
        skipped.add(int(item["version_id"]))
        st.session_state.d4_wave1_skipped_versions = skipped
        st.rerun()


if __name__ == "__main__":
    run()
