"""Standalone internal Streamlit queue for controlled content approval."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from services.runtime import prepare_runtime

QUEUE = Path(__file__).resolve().parents[1] / "resources" / "content" / "quality" / "lcai_0012d3_approval_priority.json"


def _load_queue() -> list[dict[str, Any]]:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def run() -> None:
    prepare_runtime()
    st.set_page_config(page_title="LCAI — Approval Queue", layout="wide")
    st.title("Content Approval Queue — 4e & 3e")
    st.warning("Outil interne : chaque action modifie individuellement le lifecycle éditorial.")
    queue = _load_queue()
    grade = st.sidebar.multiselect("Niveau", sorted({str(item["grade"]) for item in queue}))
    subject = st.sidebar.multiselect("Matière", sorted({str(item["subject"]) for item in queue}))
    content_type = st.sidebar.multiselect("Type", sorted({str(item["content_type"]) for item in queue}))
    recommendation = st.sidebar.multiselect(
        "Recommandation", sorted({str(item["recommended_decision"]) for item in queue})
    )
    review_group = st.sidebar.multiselect("Groupe de revue", sorted({str(item["approval_group"]) for item in queue}))
    missing_only = st.sidebar.checkbox("Couverture manquante uniquement", value=True)
    reviewer = st.sidebar.text_input("Reviewer")
    approver = st.sidebar.text_input("Approver")
    reason = st.sidebar.text_area("Motif de décision", value="Revue humaine LCAI-0012D3.")
    filtered = [
        item
        for item in queue
        if (not grade or item["grade"] in grade)
        and (not subject or item["subject"] in subject)
        and (not content_type or item["content_type"] in content_type)
        and (not recommendation or item["recommended_decision"] in recommendation)
        and (not review_group or item["approval_group"] in review_group)
        and (not missing_only or item["missing_coverage"])
    ]
    st.sidebar.metric("Résultats", len(filtered))
    if not filtered:
        st.info("Aucun candidat pour ces filtres.")
        return
    index = int(st.session_state.get("approval_queue_index", 0))
    index = min(index, len(filtered) - 1)
    item = filtered[index]
    previous, position, following = st.columns((1, 2, 1))
    if previous.button("← Previous", disabled=index == 0):
        st.session_state.approval_queue_index = index - 1
        st.rerun()
    position.write(f"**{index + 1}/{len(filtered)}** · `{item['code']}`")
    if following.button("Next →", disabled=index == len(filtered) - 1):
        st.session_state.approval_queue_index = index + 1
        st.rerun()
    st.subheader(f"{item['grade']} · {item['subject']} · {item['chapter']}")
    st.write(f"**Skill :** {item['skill']}")
    st.write(
        f"**Type :** {item['content_type']} · **Difficulté :** {item['difficulty']} · "
        f"**Score :** {item['candidate_score']}/100"
    )
    impact = item["coverage_impact"]
    st.info(
        "**Impact couverture —** "
        f"Practice: {'YES' if impact['current']['practice_approved'] else 'NO'} → "
        f"{'YES' if impact['potential']['practice_approved'] else 'NO'} · "
        f"Assessment: {'YES' if impact['current']['assessment_approved'] else 'NO'} → "
        f"{'YES' if impact['potential']['assessment_approved'] else 'NO'} · "
        f"Tier {impact['current']['tier']} → Tier {impact['potential']['tier']}"
    )
    st.write(
        "**THIS APPROVAL WOULD:** "
        + " · ".join(
            label
            for enabled, label in (
                (impact["adds_practice"], "add practice"),
                (impact["adds_assessment"], "add assessment"),
                (impact["completes_tier_1"], "complete Tier 1"),
                (impact["improves_tier_2"], "improve Tier 2"),
                (impact["no_coverage_impact"], "no coverage impact"),
            )
            if enabled
        )
    )
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
            "SKILL_ALIGNMENT": item["automated_checks"].get("skill_alignment"),
            "ANSWER": item["automated_checks"].get("answer_correctness"),
            "DETERMINISTIC_CHECK": item["deterministic_verification"],
            "QCM_CHECK": (
                item["automated_checks"].get("executability")
                if item["answer_kind"] in {"single_choice", "multiple_choice"}
                else "N/A"
            ),
            "DUPLICATE_CHECK": item["automated_checks"].get("duplicate_safety"),
            "EXECUTABILITY": item["automated_checks"].get("executability"),
            "LEVEL": item["automated_checks"].get("grade_appropriateness"),
        }
    )
    right.json(
        {
            "quality_result": item["quality_result"],
            "reason": item["quality_reason"],
            "deterministic_verification": item["deterministic_verification"],
            "recommendation": item["recommended_decision"],
        }
    )
    repository = DuckDBContentQualityRepository()
    approve, reject, keep = st.columns(3)
    identities_ready = bool(reviewer.strip() and approver.strip() and reviewer != approver)
    if approve.button(
        "Approve",
        type="primary",
        disabled=not identities_ready or item["recommended_decision"] != "APPROVE",
    ):
        try:
            content_id = repository.approve_for_production(
                item=item,
                reviewer=reviewer.strip(),
                approver=approver.strip(),
                reason=reason.strip(),
            )
            st.success(f"Contenu publié individuellement : {content_id}")
        except ValueError as exc:
            st.error(str(exc))
    if reject.button("Reject", disabled=not reviewer.strip()):
        repository.record_human_decision(
            version_id=int(item["version_id"]),
            reviewer=reviewer.strip(),
            decision="REJECT",
            notes=reason.strip(),
        )
        st.success("Contenu rejeté et archivé.")
    if keep.button("Keep Review", disabled=not reviewer.strip()):
        repository.record_human_decision(
            version_id=int(item["version_id"]),
            reviewer=reviewer.strip(),
            decision="KEEP_FOR_REVIEW",
            notes=reason.strip(),
        )
        st.success("Contenu maintenu en revue.")


if __name__ == "__main__":
    run()
