"""File Streamlit interne pour la validation humaine contrôlée."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository
from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from services.content.approval_queue import build_dynamic_queue, filter_queue
from services.runtime import prepare_runtime
from ui.i18n import PRIORITY_LABELS_FR, grade_label, label, subject_label, tier_label

QUEUE = Path(__file__).resolve().parents[1] / "resources" / "content" / "quality" / "lcai_0012d3_approval_priority.json"

PRIORITY_FILTERS = (
    "Plan minimal — prioritaire",
    "Complète immédiatement un Tier 1",
    "Tier 3 → Tier 2",
    "Évaluation manquante",
    "Entraînement manquant",
    "Tous les candidats recommandés",
    "Sans impact direct",
)


def _load_queue() -> list[dict[str, Any]]:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def _subject_options(base_queue: list[dict[str, Any]]) -> tuple[str, ...]:
    """Keep widget options stable even when the last candidate is removed."""
    return tuple(sorted({str(item["subject"]) for item in base_queue}))


def _resolve_candidate_index(
    items: list[dict[str, Any]],
    current_version_id: int | None,
    previous_index: int,
) -> int | None:
    """Resolve navigation without assuming a removed object still exists."""
    if not items:
        return None
    if current_version_id is not None:
        for position, candidate in enumerate(items):
            if int(candidate["version_id"]) == current_version_id:
                return position
    return min(max(0, previous_index), len(items) - 1)


def _remember_position(index: int, version_id: int) -> None:
    """Keep a stable identity and numeric fallback across a Streamlit rerun."""
    st.session_state.approval_queue_index = index
    st.session_state.approval_current_version_id = version_id


def _prepare_navigation_after_decision(
    previous_index: int,
    version_id: int,
    review_status: str,
) -> None:
    """Clear the removed identity only after persistence has been confirmed."""
    st.session_state.approval_queue_index = previous_index
    st.session_state.approval_current_version_id = None
    st.session_state.approval_last_decision = {
        "version_id": version_id,
        "review_status": review_status,
    }


def _reset_priority_selection() -> None:
    st.session_state.approval_priority_filter = "Plan minimal — prioritaire"
    st.session_state.approval_priority_levels = ["P1", "P2"]
    st.session_state.approval_queue_index = 0
    st.session_state.approval_current_version_id = None


def _persist_and_verify_decision(
    repository: DuckDBContentQualityRepository,
    *,
    item: dict[str, Any],
    action: str,
    reviewer: str,
    approver: str,
    reason: str,
) -> dict[str, Any]:
    """Persist one business decision, then verify it through an independent read."""
    version_id = int(item["version_id"])
    if action == "APPROVE":
        repository.approve_for_production(
            item=item,
            reviewer=reviewer,
            approver=approver,
            reason=reason,
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
        raise ValueError(f"Unsupported approval action: {action}")

    persisted = repository.read_human_decision(version_id)
    if persisted is None or persisted.get("review_status") != expected_status:
        raise RuntimeError("La décision n’a pas pu être confirmée après écriture.")
    if persisted.get("source_status") != "draft" or not persisted.get("audit_trail_present"):
        raise RuntimeError("La source Draft ou la piste d’audit n’est pas conforme.")
    if persisted.get("reviewer") != reviewer:
        raise RuntimeError("Le relecteur persisté ne correspond pas à la décision.")
    if action == "APPROVE":
        valid_approval = (
            persisted.get("published_status") == "approved"
            and persisted.get("content_status") == "active"
            and persisted.get("active_version_number") == persisted.get("published_version_number")
            and persisted.get("approver") == approver
            and persisted.get("approved") is True
            and persisted.get("approval_active") is True
            and persisted.get("production_enabled") is True
            and persisted.get("reason") == reason
            and persisted.get("approved_at") is not None
            and persisted.get("published_at") is not None
        )
        if not valid_approval:
            raise RuntimeError("L’approbation persistée est incomplète ou inactive.")
    elif action == "REJECT" and (
        persisted.get("decision_status") != "archived" or persisted.get("decision") != "REJECT"
    ):
        raise RuntimeError("Le rejet persisté est incomplet.")
    elif action == "KEEP_FOR_REVIEW" and (
        persisted.get("decision_status") != "review" or persisted.get("decision") != "KEEP_FOR_REVIEW"
    ):
        raise RuntimeError("Le maintien en révision persisté est incomplet.")
    return persisted


def _coverage_rows() -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in DuckDBContentFactoryRepository().active_skill_coverage():
        practice = sum(
            count for slot, count in row.approved.items() if slot.content_type.value in {"practice", "guided_practice"}
        )
        assessment = sum(count for slot, count in row.approved.items() if slot.content_type.value == "assessment")
        output.append(
            {
                "grade": row.target.grade_code,
                "subject": row.target.subject_code,
                "chapter": row.target.chapter_code,
                "skill": row.target.primary_skill_code,
                "approved_practice": practice,
                "approved_assessment": assessment,
            }
        )
    return output


def _display_impact(item: dict[str, Any]) -> None:
    impact = item["coverage_impact"]
    if impact["completes_tier_1"]:
        st.success("🟢 **IMPACT : cette validation rend la compétence complète (Tier 1)**")
    elif impact["improves_tier_2"]:
        missing = "Évaluation" if not impact["potential"]["assessment_approved"] else "Entraînement"
        st.warning(
            f"🟡 **IMPACT : cette validation améliore la couverture de la compétence**  \n{missing} encore manquant."
        )
    else:
        st.info("⚪ **IMPACT DE CETTE VALIDATION : aucun impact immédiat sur le Tier**")
    current, potential = impact["current"], impact["potential"]
    left, right = st.columns(2)
    left.markdown(
        "**Statut actuel de la compétence**  \n"
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
    st.set_page_config(page_title="LCAI — File de validation", layout="wide")
    st.title("File de validation des contenus — 4e et 3e")
    st.warning("Outil interne : chaque action modifie individuellement le lifecycle éditorial.")
    last_decision = st.session_state.pop("approval_last_decision", None)
    if last_decision:
        st.success(
            f"Décision {label(last_decision['review_status'])} confirmée pour la version {last_decision['version_id']}."
        )
    repository = DuckDBContentQualityRepository()
    skipped = set(st.session_state.get("approval_skipped_versions", set()))
    base_queue = _load_queue()
    queue, summary = build_dynamic_queue(
        base_queue,
        _coverage_rows(),
        repository.approval_queue_review_statuses(),
        skipped=skipped,
    )

    metrics = st.columns(4)
    metrics[0].metric("Plan minimal restant", summary["minimal_plan_remaining"])
    metrics[1].metric("Compétences complètes", summary["current_tier_1"])
    metrics[2].metric("Compétences complètes supplémentaires", summary["additional_tier_1"])
    metrics[3].metric("Maximum de compétences complètes", summary["maximum_tier_1"])

    st.sidebar.header("Priorité de validation")
    priority_filter = st.sidebar.radio(
        "Vue principale",
        PRIORITY_FILTERS,
        index=0,
        key="approval_priority_filter",
    )
    priority_levels = st.sidebar.multiselect(
        "Niveaux de priorité",
        ("P1", "P2", "P3", "P4", "P5"),
        default=("P1", "P2"),
        key="approval_priority_levels",
    )
    for status in PRIORITY_LABELS_FR:
        st.sidebar.caption(f"{PRIORITY_LABELS_FR[status]} : {summary['priority_counts'].get(status, 0)}")
    tier1_only = st.sidebar.checkbox("Seulement les validations qui créent un Tier 1")
    grade = st.sidebar.selectbox(
        "Niveau",
        ("Tous", "FR-3E", "FR-4E"),
        format_func=lambda value: "Tous" if value == "Tous" else grade_label(value),
    )
    subjects = st.sidebar.multiselect(
        "Matière",
        _subject_options(base_queue),
        format_func=subject_label,
    )
    priority_4e = st.sidebar.checkbox("Priorité 4e")
    balance_subjects = st.sidebar.checkbox("Équilibrer les matières")
    reviewer = st.sidebar.text_input("Relecteur")
    approver = st.sidebar.text_input("Approbateur")
    reason = st.sidebar.text_area("Motif de décision", value="Revue humaine LCAI-0012D3A.")

    filtered = filter_queue(
        queue,
        priority_filter=priority_filter,
        priority_levels=priority_levels,
        grade=grade,
        subjects=subjects,
        tier1_only=tier1_only,
        priority_4e=priority_4e,
        balance_subjects=balance_subjects,
    )
    st.sidebar.metric("Résultats", len(filtered))
    if not filtered:
        st.session_state.approval_current_version_id = None
        st.session_state.approval_queue_index = 0
        st.info("Aucun contenu restant dans cette sélection.")
        st.button(
            "Afficher le prochain contenu prioritaire",
            on_click=_reset_priority_selection,
        )
        return

    stored_version = st.session_state.get("approval_current_version_id")
    index = _resolve_candidate_index(
        filtered,
        int(stored_version) if stored_version is not None else None,
        int(st.session_state.get("approval_queue_index", 0)),
    )
    if index is None:
        st.info("Aucun contenu restant dans cette sélection.")
        return
    item = filtered[index]
    _remember_position(index, int(item["version_id"]))
    item["review_status"] = "IN_REVIEW"
    previous, position, following = st.columns((1, 2, 1))
    if previous.button("← Précédent", disabled=index == 0):
        target = filtered[index - 1]
        _remember_position(index - 1, int(target["version_id"]))
        st.rerun()
    position.write(
        f"**{index + 1}/{len(filtered)}** · `{item['code']}` · "
        f"**{PRIORITY_LABELS_FR[str(item['approval_priority_status'])]}** · "
        f"rang {item['approval_priority_rank']}"
    )
    if following.button("Suivant →", disabled=index == len(filtered) - 1):
        target = filtered[index + 1]
        _remember_position(index + 1, int(target["version_id"]))
        st.rerun()

    st.subheader(f"{grade_label(item['grade'])} · {subject_label(item['subject'])} · {item['chapter']}")
    st.write(f"**Compétence :** {item['skill']}")
    content_label = {
        "practice": "Entraînement",
        "assessment": "Évaluation",
        "remediation": "Remédiation",
        "diagnostic": "Diagnostic",
    }.get(str(item["content_type"]), str(item["content_type"]))
    st.write(
        f"**Type :** {content_label} · **Difficulté :** {item['difficulty']} · "
        f"**Score :** {item['candidate_score']}/100 · "
        f"**Statut de revue :** {label(item['review_status'])}"
    )
    _display_impact(item)

    st.markdown("### Question")
    st.write(item["question"])
    if item["choices"]:
        st.markdown("### Choix")
        for choice in item["choices"]:
            st.write(f"- {choice}")
    st.markdown("### Réponse attendue")
    st.code(str(item["expected_answer"]))
    st.markdown("### Explication")
    st.write(item["explanation"])
    left, right = st.columns(2)
    left.json(
        {
            "STRUCTURE": item["automated_checks"].get("structural_validity"),
            "CURRICULUM": item["automated_checks"].get("curriculum_alignment"),
            "ALIGNEMENT_COMPÉTENCE": item["automated_checks"].get("skill_alignment"),
            "RÉPONSE": item["automated_checks"].get("answer_correctness"),
            "CONTRÔLE_DÉTERMINISTE": item["deterministic_verification"],
            "DOUBLON": item["automated_checks"].get("duplicate_safety"),
            "EXÉCUTABILITÉ": item["automated_checks"].get("executability"),
            "NIVEAU": item["automated_checks"].get("grade_appropriateness"),
        }
    )
    right.json(
        {
            "résultat_qualité": label(item["quality_result"]),
            "motif": item["quality_reason"],
            "recommandation": label(item["recommended_decision"]),
        }
    )

    approve, reject, keep, skip = st.columns(4)
    identities_ready = bool(reviewer.strip() and approver.strip() and reviewer != approver)
    if approve.button(
        "Approuver",
        type="primary",
        disabled=not identities_ready or item["recommended_decision"] != "APPROVE",
    ):
        try:
            persisted = _persist_and_verify_decision(
                repository,
                item=item,
                action="APPROVE",
                reviewer=reviewer.strip(),
                approver=approver.strip(),
                reason=reason.strip(),
            )
            _prepare_navigation_after_decision(
                index,
                int(item["version_id"]),
                str(persisted["review_status"]),
            )
            st.rerun()
        except (RuntimeError, ValueError) as exc:
            st.error(str(exc))
    if reject.button("Rejeter", disabled=not reviewer.strip()):
        try:
            persisted = _persist_and_verify_decision(
                repository,
                item=item,
                action="REJECT",
                reviewer=reviewer.strip(),
                approver="",
                reason=reason.strip(),
            )
            _prepare_navigation_after_decision(
                index,
                int(item["version_id"]),
                str(persisted["review_status"]),
            )
            st.rerun()
        except (RuntimeError, ValueError) as exc:
            st.error(str(exc))
    if keep.button("Maintenir en révision", disabled=not reviewer.strip()):
        try:
            persisted = _persist_and_verify_decision(
                repository,
                item=item,
                action="KEEP_FOR_REVIEW",
                reviewer=reviewer.strip(),
                approver="",
                reason=reason.strip(),
            )
            _prepare_navigation_after_decision(
                index,
                int(item["version_id"]),
                str(persisted["review_status"]),
            )
            st.rerun()
        except (RuntimeError, ValueError) as exc:
            st.error(str(exc))
    if skip.button("Ignorer pour cette session"):
        skipped.add(int(item["version_id"]))
        st.session_state.approval_skipped_versions = skipped
        _remember_position(index, int(item["version_id"]))
        st.rerun()


if __name__ == "__main__":
    run()
