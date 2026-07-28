"""Streamlit — revue humaine D4 (Wave 1 / Wave 2) par compétence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from scripts.run_content_approval_d4_wave1 import _coverage_rows
from services.content.approval_coverage import tier
from services.content.d4_review import (
    PEDAGOGICAL_WARNING_FR,
    can_dual_approve,
    can_individual_approve,
    is_ai_prevalidated,
    is_ai_rejected,
    is_technically_blocked,
    pedagogical_attention_reason,
    requires_pedagogical_attention,
    requires_teacher_review,
)
from services.content.d4_wave2 import (
    build_skill_review_bundles,
    filter_skill_bundles,
    load_lot_review_queues,
    prioritize_skill_bundles,
    summarize_wave2_review_bundles,
)
from services.runtime import prepare_runtime
from ui.i18n import grade_label, label, subject_label

ROOT = Path(__file__).resolve().parents[1]
QUALITY = ROOT / "resources" / "content" / "quality"


def _load_wave2_combined_state(
    repository: DuckDBContentQualityRepository,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[int, str]]:
    combined_path = QUALITY / "lcai_0012d4_wave2_combined_review.json"
    if combined_path.exists():
        payload = json.loads(combined_path.read_text(encoding="utf-8"))
        bundles = payload["skills"]
        summary = payload.get("summary", summarize_wave2_review_bundles(bundles))
        baseline = int(payload.get("baseline_tier1", summary.get("baseline_tier1", 0)))
    else:
        coverage_rows = _coverage_rows()
        review_statuses = repository.approval_queue_review_statuses()
        queue = load_lot_review_queues(QUALITY, lots=(1, 2))
        bundles = prioritize_skill_bundles(
            build_skill_review_bundles(queue, review_statuses),
            coverage_rows,
        )
        summary = summarize_wave2_review_bundles(bundles)
        baseline = sum(
            tier(int(row["approved_practice"]) > 0, int(row["approved_assessment"]) > 0) == 1 for row in coverage_rows
        )
    review_statuses = repository.approval_queue_review_statuses()
    meta = {
        "baseline_tier1": baseline,
        "summary": summary,
        "campaign": "LCAI-0012D4-WAVE2",
    }
    return bundles, meta, review_statuses


def _ai_review_badge(item: dict[str, Any] | None, review_status: str | None = None) -> str:
    if item is None:
        return "—"
    decision = str(item.get("ai_prevalidation_decision", "—"))
    confidence = str(item.get("ai_prevalidation_confidence", ""))
    if review_status == "APPROVED" and decision == "AI_PREVALIDATED_HIGH":
        return "✓ Publié par validation IA contrôlée"
    if decision == "AI_PREVALIDATED_HIGH":
        return f"✓ Prévalidé IA — confiance élevée ({confidence})"
    if decision == "AI_PREVALIDATED_WITH_WARNING":
        return f"⚠ Prévalidé IA avec réserve ({confidence})"
    if decision in {"AI_PREVALIDATED"}:
        return f"✓ Prévalidé par l'IA ({confidence})"
    if decision == "TEACHER_REVIEW_REQUIRED":
        return "👨‍🏫 Revue enseignant requise"
    if decision == "AI_REJECTED":
        return "⛔ Rejeté par IA"
    return "—"


def _render_ai_review_summary(item: dict[str, Any] | None, side: Any, review_status: str | None = None) -> None:
    if item is None:
        return
    review = item.get("ai_pedagogical_review")
    if not review:
        side.info("Prévalidation IA : non disponible.")
        return
    side.markdown(f"**{_ai_review_badge(item, review_status)}**")
    side.caption(review.get("concise_reason", ""))
    grade_assessment = item.get("grade_assessment") or {}
    if grade_assessment:
        side.caption(
            f"Niveau scolaire : {grade_assessment.get('status')} — {grade_assessment.get('concise_reason', '')}"
        )
    if review.get("fact_check_required"):
        side.warning("Vérification factuelle requise.")
    side.write(
        {
            "confiance": review.get("confidence"),
            "réponse_indépendante": review.get("blind_answer"),
            "accord_attendu": review.get("expected_answer_match"),
            "scores": {
                key: review.get(key)
                for key in (
                    "answer_correctness",
                    "explanation_correctness",
                    "skill_alignment",
                    "curriculum_alignment",
                    "pedagogical_quality",
                )
            },
        }
    )


def _pair_ai_prevalidated(bundle: dict[str, Any]) -> bool:
    practice = bundle.get("practice")
    assessment = bundle.get("assessment")
    return (
        practice is not None
        and assessment is not None
        and is_ai_prevalidated(practice)
        and is_ai_prevalidated(assessment)
        and str(practice.get("ai_prevalidation_confidence")) == "HIGH"
        and str(assessment.get("ai_prevalidation_confidence")) == "HIGH"
    )


def _slot_status(item: dict[str, Any] | None, review_statuses: dict[int, str]) -> str | None:
    if item is None:
        return None
    return review_statuses.get(int(item["version_id"]))


def _skill_completed(bundle: dict[str, Any], review_statuses: dict[int, str]) -> bool:
    practice = bundle.get("practice")
    assessment = bundle.get("assessment")
    if practice is None or assessment is None:
        return False
    closed = {"APPROVED", "REJECTED", "KEEP_REVIEW"}
    return _slot_status(practice, review_statuses) in closed and _slot_status(assessment, review_statuses) in closed


def _projected_tier1(meta: dict[str, Any], completed_skills: int) -> int:
    return int(meta["baseline_tier1"]) + completed_skills


def _persist_decision(
    repository: DuckDBContentQualityRepository,
    *,
    item: dict[str, Any],
    action: str,
    reviewer: str,
    approver: str,
    reason: str,
    explicit_pedagogical_confirmation: bool,
) -> None:
    version_id = int(item["version_id"])
    if action == "APPROVE":
        repository.approve_for_production(
            item=item,
            reviewer=reviewer,
            approver=approver,
            reason=reason,
            human_pedagogical_confirmation=explicit_pedagogical_confirmation and requires_pedagogical_attention(item),
        )
        expected = "APPROVED"
    elif action in {"REJECT", "KEEP_FOR_REVIEW"}:
        repository.record_human_decision(
            version_id=version_id,
            reviewer=reviewer,
            decision=action,
            notes=reason,
        )
        expected = "REJECTED" if action == "REJECT" else "KEEP_REVIEW"
    else:
        raise ValueError(f"Action non supportée : {action}")

    persisted = repository.read_human_decision(version_id)
    if persisted is None or persisted.get("review_status") != expected:
        raise RuntimeError("La décision n'a pas pu être confirmée après écriture.")


def _render_candidate_panel(
    side: Any,
    *,
    title: str,
    item: dict[str, Any] | None,
    review_status: str | None,
    reviewer: str,
    approver: str,
    reason: str,
    repository: DuckDBContentQualityRepository,
    key_prefix: str,
) -> bool:
    """Render one slot panel. Returns True if a decision was persisted."""
    side.subheader(title)
    if item is None:
        side.warning("Aucun candidat disponible pour ce slot.")
        return False

    side.caption(
        f"Score **{item['candidate_score']}/100** · "
        f"{label(item['recommended_decision'])} · "
        f"Source **{item.get('candidate_source', '—')}** · "
        f"Alternatives **{item.get('alternate_count', 0)}**"
    )
    if review_status:
        side.info(f"Décision actuelle : **{label(review_status.lower())}**")

    if is_technically_blocked(item):
        side.error("Candidat techniquement bloqué — non exposé à l'approbation.")
        return False
    if is_ai_rejected(item):
        side.error("Rejeté par l'IA — non approvable. Rechercher une alternative ou un remplacement.")
        return False

    _render_ai_review_summary(item, side, review_status)

    side.markdown("**Question**")
    side.write(item["question"])
    if item.get("choices"):
        side.markdown("**Choix**")
        for choice in item["choices"]:
            side.write(f"- {choice}")
    side.markdown("**Réponse attendue**")
    side.code(str(item["expected_answer"]))
    side.markdown("**Explication**")
    side.write(item["explanation"])
    side.json(
        {
            "hard_gates": item["automated_checks"],
            "qualité": item["quality_result"],
            "motif": item["quality_reason"],
        }
    )

    pedagogical_confirmation = False
    if requires_teacher_review(item):
        side.warning("Revue enseignante spécialisée recommandée.")
    elif is_ai_prevalidated(item):
        side.success("Prévalidation IA — approbation rapide possible.")
    elif requires_pedagogical_attention(item):
        side.error(PEDAGOGICAL_WARNING_FR)
        side.markdown(f"**Motif :** {pedagogical_attention_reason(item)}")
        pedagogical_confirmation = side.checkbox(
            "Confirmation pédagogique explicite",
            key=f"{key_prefix}_pedagogical_confirm",
        )

    can_approve = can_individual_approve(
        item,
        reviewer=reviewer,
        approver=approver,
        explicit_pedagogical_confirmation=pedagogical_confirmation,
        review_status=review_status,
    )
    action_cols = side.columns(3)
    if action_cols[0].button("Approuver", key=f"{key_prefix}_approve", disabled=not can_approve):
        _persist_decision(
            repository,
            item=item,
            action="APPROVE",
            reviewer=reviewer,
            approver=approver,
            reason=reason,
            explicit_pedagogical_confirmation=pedagogical_confirmation,
        )
        return True
    if action_cols[1].button("Rejeter", key=f"{key_prefix}_reject", disabled=not reviewer.strip()):
        _persist_decision(
            repository,
            item=item,
            action="REJECT",
            reviewer=reviewer,
            approver="",
            reason=reason,
            explicit_pedagogical_confirmation=False,
        )
        return True
    if action_cols[2].button("Maintenir en revue", key=f"{key_prefix}_keep", disabled=not reviewer.strip()):
        _persist_decision(
            repository,
            item=item,
            action="KEEP_FOR_REVIEW",
            reviewer=reviewer,
            approver="",
            reason=reason,
            explicit_pedagogical_confirmation=False,
        )
        return True
    return False


def run() -> None:
    prepare_runtime()
    st.set_page_config(page_title="LCAI — Revue D4", layout="wide")
    st.title("LCAI-0012D4 — Revue humaine D4")
    st.caption("Wave 2 · Lots 1+2 · une compétence = Entraînement + Évaluation")

    repository = DuckDBContentQualityRepository()
    bundles, meta, review_statuses = _load_wave2_combined_state(repository)
    summary = meta["summary"]

    st.sidebar.header("Campagne")
    st.sidebar.write(meta["campaign"])
    reviewer = st.sidebar.text_input("Relecteur")
    approver = st.sidebar.text_input("Approbateur")
    reason = st.sidebar.text_area("Motif", value="Revue humaine LCAI-0012D4 Wave 2.")

    lot_filter = st.sidebar.selectbox("Lot", ("Tous", "Lot 1", "Lot 2"))
    grade_filter = st.sidebar.selectbox(
        "Niveau",
        ("Tous", "FR-3E", "FR-4E"),
        format_func=lambda value: "Tous" if value == "Tous" else grade_label(value),
    )
    subject_filter = st.sidebar.selectbox("Matière", ("Toutes", *sorted({b["subject"] for b in bundles})))
    status_filter = st.sidebar.selectbox("Statut", ("À traiter", "Terminées"))
    ai_filter = st.sidebar.selectbox(
        "Statut de prévalidation IA",
        (
            "Tous",
            "File prévalidée rapide",
            "Prévalidé IA — confiance élevée",
            "Prévalidé IA avec réserve",
            "Prévalidé par IA",
            "Revue enseignant requise",
            "Rejeté par IA",
            "Vérification factuelle requise",
        ),
    )
    teacher_reason_filter = st.sidebar.text_input("Motif revue enseignant (filtre)")
    warning_filter = st.sidebar.checkbox("Attention pédagogique seulement")
    dual_filter = st.sidebar.checkbox("Prêtes pour approbation double")

    lot_number = None if lot_filter == "Tous" else int(lot_filter.split()[-1])
    ai_prevalidation = None if ai_filter == "Tous" else ai_filter
    filtered = filter_skill_bundles(
        bundles,
        lot_number=lot_number,
        grade=None if grade_filter == "Tous" else grade_filter,
        subject=None if subject_filter == "Toutes" else subject_filter,
        status="pending" if status_filter == "À traiter" else "completed",
        pedagogical_warning=True if warning_filter else None,
        dual_ready=True if dual_filter else None,
        ai_prevalidation=ai_prevalidation,
        fact_check_required=True if ai_filter == "Vérification factuelle requise" else None,
        review_statuses=review_statuses,
    )
    if teacher_reason_filter.strip():
        needle = teacher_reason_filter.strip().lower()
        filtered = [
            bundle
            for bundle in filtered
            if any(
                needle in str((item.get("ai_pedagogical_review") or {}).get("concise_reason", "")).lower()
                for item in (bundle.get("practice"), bundle.get("assessment"))
                if item is not None
            )
        ]

    completed_count = sum(1 for bundle in bundles if _skill_completed(bundle, review_statuses))
    metrics = st.columns(5)
    metrics[0].metric("Compétences uniques", summary["skills"])
    metrics[1].metric("Candidats entraînement", summary["practice_candidates"])
    metrics[2].metric("Candidats évaluation", summary["assessment_candidates"])
    metrics[3].metric("Tier 1 actuel", meta["baseline_tier1"])
    metrics[4].metric("Tier 1 projeté", _projected_tier1(meta, completed_count))

    st.write(
        f"**Priorisation :** haute confiance double = {summary['high_confidence_dual']} · "
        f"mixte = {summary['mixed_review']} · "
        f"pédagogique double = {summary['pedagogical_dual']} · "
        f"bloqués = {summary['technically_blocked']}"
    )

    if not filtered:
        st.success("Aucune compétence ne correspond aux filtres.")
        return

    index = int(st.session_state.get("d4_wave2_skill_index", 0))
    index = min(index, len(filtered) - 1)
    bundle = filtered[index]
    st.session_state.d4_wave2_skill_index = index

    nav_prev, nav_pos, nav_next = st.columns((1, 3, 1))
    if nav_prev.button("← Compétence précédente", disabled=index == 0):
        st.session_state.d4_wave2_skill_index = index - 1
        st.rerun()
    nav_pos.markdown(
        f"**Compétence {index + 1} / {len(filtered)}** · "
        f"reste **{max(0, len([b for b in filtered if not _skill_completed(b, review_statuses)]) - (0 if _skill_completed(bundle, review_statuses) else 1))}** · "
        f"lots {', '.join(str(n) for n in bundle.get('lot_numbers', []))}"
    )
    if nav_next.button("Compétence suivante →", disabled=index >= len(filtered) - 1):
        st.session_state.d4_wave2_skill_index = index + 1
        st.rerun()

    st.subheader(f"{grade_label(bundle['grade'])} · {subject_label(bundle['subject'])} · {bundle['chapter']}")
    st.write(f"**Compétence :** {bundle.get('skill_name', bundle['skill'])} (`{bundle['skill']}`)")
    if _pair_ai_prevalidated(bundle):
        st.success("✓ COMPÉTENCE PRÉVALIDÉE PAR IA — approbation rapide de la paire possible.")

    practice = bundle.get("practice")
    assessment = bundle.get("assessment")
    practice_status = _slot_status(practice, review_statuses)
    assessment_status = _slot_status(assessment, review_statuses)

    left, right = st.columns(2)
    decided = False
    if _render_candidate_panel(
        left,
        title="Entraînement",
        item=practice,
        review_status=practice_status,
        reviewer=reviewer.strip(),
        approver=approver.strip(),
        reason=reason.strip(),
        repository=repository,
        key_prefix=f"practice_{bundle['skill']}",
    ):
        decided = True
    if _render_candidate_panel(
        right,
        title="Évaluation",
        item=assessment,
        review_status=assessment_status,
        reviewer=reviewer.strip(),
        approver=approver.strip(),
        reason=reason.strip(),
        repository=repository,
        key_prefix=f"assessment_{bundle['skill']}",
    ):
        decided = True

    dual_ready = can_dual_approve(
        practice,
        assessment,
        reviewer=reviewer.strip(),
        approver=approver.strip(),
        practice_pedagogical_confirmation=bool(
            st.session_state.get(f"practice_{bundle['skill']}_pedagogical_confirm", False)
        ),
        assessment_pedagogical_confirmation=bool(
            st.session_state.get(f"assessment_{bundle['skill']}_pedagogical_confirm", False)
        ),
        practice_status=practice_status,
        assessment_status=assessment_status,
    )
    if st.button(
        "Approuver les deux",
        type="primary",
        disabled=not dual_ready,
        help="Crée deux décisions d'approbation traçables.",
    ):
        try:
            practice_confirm = bool(st.session_state.get(f"practice_{bundle['skill']}_pedagogical_confirm", False))
            assessment_confirm = bool(st.session_state.get(f"assessment_{bundle['skill']}_pedagogical_confirm", False))
            _persist_decision(
                repository,
                item=practice,
                action="APPROVE",
                reviewer=reviewer.strip(),
                approver=approver.strip(),
                reason=reason.strip(),
                explicit_pedagogical_confirmation=practice_confirm,
            )
            _persist_decision(
                repository,
                item=assessment,
                action="APPROVE",
                reviewer=reviewer.strip(),
                approver=approver.strip(),
                reason=reason.strip(),
                explicit_pedagogical_confirmation=assessment_confirm,
            )
            decided = True
            st.success("Les deux slots ont été approuvés avec traçabilité individuelle.")
        except (RuntimeError, ValueError) as exc:
            st.error(str(exc))

    if decided:
        if _skill_completed(bundle, repository.approval_queue_review_statuses()) and index < len(filtered) - 1:
            st.session_state.d4_wave2_skill_index = index + 1
        st.rerun()


if __name__ == "__main__":
    run()
