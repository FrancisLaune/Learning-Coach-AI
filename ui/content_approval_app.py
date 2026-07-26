"""Standalone internal Streamlit queue for controlled content approval."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from services.runtime import prepare_runtime

QUEUE = Path(__file__).resolve().parents[1] / "resources" / "content" / "quality" / "lcai_0012d2_approval_queue.json"


def _load_queue() -> list[dict[str, object]]:
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
    missing_only = st.sidebar.checkbox("Couverture manquante uniquement", value=True)
    reviewer = st.sidebar.text_input("Reviewer")
    approver = st.sidebar.text_input("Approver")
    reason = st.sidebar.text_area("Motif de décision", value="Revue humaine LCAI-0012D2.")
    filtered = [
        item
        for item in queue
        if (not grade or item["grade"] in grade)
        and (not subject or item["subject"] in subject)
        and (not content_type or item["content_type"] in content_type)
        and (not recommendation or item["recommended_decision"] in recommendation)
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
    left.json(item["automated_checks"])
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
