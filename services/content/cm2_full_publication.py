"""LCAI-0018D CM2 full chapter publication (relaxed AI policy, sequential subjects)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from domain.content.pedagogical_review import AI_REVIEW_PIPELINE_VERSION
from infrastructure.database.v2 import reset_v2_connections
from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from services.content.ai_controlled_publication import (
    DEFAULT_REVIEW_MODEL,
    assess_publication_eligibility,
    build_publication_provenance,
    classify_warning_severity,
)
from services.content.d4_review import ai_prevalidation_decision, is_ai_rejected, is_authoritative_ai_review
from services.content.primary_ai_review import CAMPAIGN_ID as PRIMARY_REVIEW_CAMPAIGN
from services.content.primary_controlled_publication import (
    PUBLICATION_CAMPAIGN,
    _current_production_draft_hashes,
    _find_item,
    build_primary_execution_manifest,
    load_primary_publication_bundles,
)

GRADE = "FR-CM2"
LOCK_RETRY_ATTEMPTS = 5
LOCK_RETRY_DELAY_SECONDS = 0.5

CM2_SUBJECT_ORDER: tuple[str, ...] = (
    "FRENCH",
    "HISTORY",
    "GEOGRAPHY",
    "SVT",
    "PHYSICS_CHEMISTRY",
    "ENGLISH",
    "EMC",
)

SUBJECT_LABELS = {
    "FRENCH": "Français",
    "HISTORY": "Histoire",
    "GEOGRAPHY": "Géographie",
    "SVT": "SVT",
    "PHYSICS_CHEMISTRY": "Physique-Chimie",
    "ENGLISH": "Anglais",
    "EMC": "EMC",
}


@dataclass(frozen=True, slots=True)
class Cm2PublicationCandidate:
    production_version_id: int
    chapter_code: str
    subject_code: str
    slot: str
    decision: str | None
    score: int
    reasons: tuple[str, ...]


def cm2_minimum_structural_gates_passed(item: dict[str, Any]) -> bool:
    """CM2 chapter-minimum policy: structural + alignment + executability (answer gate relaxed)."""
    if item.get("hard_gates_passed"):
        return True
    checks = item.get("automated_checks") or item.get("hard_gates") or {}
    subject = str(item.get("subject") or item.get("subject_code") or "")
    if subject == "ENGLISH":
        required = ("skill_alignment", "executability", "duplicate_safety")
    else:
        required = ("structural_validity", "skill_alignment", "executability", "duplicate_safety")
    return all(checks.get(name) for name in required)


def assess_cm2_relaxed_eligibility(
    item: dict[str, Any],
    *,
    allow_rejected: bool = True,
    accept_all_warnings: bool = True,
    skip_teacher_review: bool = True,
) -> tuple[bool, tuple[str, ...]]:
    """CM2 campaign policy: HIGH + WARNING + TEACHER (no human gate) + optional REJECTED."""
    reasons: list[str] = []
    if not item.get("cm2_draft_fallback") and not is_authoritative_ai_review(item):
        reasons.append("Authoritative AI review evidence is missing.")
    if not cm2_minimum_structural_gates_passed(item):
        reasons.append("Minimum structural gates failed.")

    decision = ai_prevalidation_decision(item)
    if decision is None and not item.get("cm2_draft_fallback"):
        reasons.append("Missing AI prevalidation decision.")
        return False, tuple(reasons)
    if decision is None:
        decision = "AI_REJECTED"

    if decision == "AI_PREVALIDATED_HIGH":
        return (not reasons, tuple(reasons))

    if decision == "AI_PREVALIDATED_WITH_WARNING":
        if accept_all_warnings:
            return (not reasons, tuple(reasons))
        eligibility = assess_publication_eligibility(
            item,
            required_decision="AI_PREVALIDATED_HIGH",
            allow_non_blocking_warning=True,
            campaign=PUBLICATION_CAMPAIGN,
            review_campaign=PRIMARY_REVIEW_CAMPAIGN,
        )
        if not eligibility.eligible:
            reasons.extend(eligibility.reasons)
        return (not reasons, tuple(reasons))

    if decision == "TEACHER_REVIEW_REQUIRED" and skip_teacher_review:
        return (not reasons, tuple(reasons))

    if item.get("cm2_draft_fallback") and decision == "AI_REJECTED":
        return (not reasons, tuple(reasons))

    if is_ai_rejected(item) and allow_rejected:
        if item.get("cm2_draft_fallback"):
            return (not reasons, tuple(reasons))
        review = item.get("ai_pedagogical_review") or {}
        if int(review.get("executability", 0)) >= 70 and int(review.get("skill_alignment", 0)) >= 60:
            return (not reasons, tuple(reasons))
        reasons.append("Rejected candidate below CM2 relaxed quality floor.")

    if not reasons:
        reasons.append(f"Decision {decision} not eligible under CM2 relaxed policy.")
    return False, tuple(reasons)


def candidate_priority_score(item: dict[str, Any]) -> int:
    decision = ai_prevalidation_decision(item) or ""
    review = item.get("ai_pedagogical_review") or {}
    decision_weight = {
        "AI_PREVALIDATED_HIGH": 1000,
        "AI_PREVALIDATED_WITH_WARNING": 850,
        "TEACHER_REVIEW_REQUIRED": 700,
        "AI_REJECTED": 300,
    }.get(decision, 0)
    warning = classify_warning_severity(item)
    warning_bonus = 20 if warning == "NON_BLOCKING_WARNING" else 0
    return (
        decision_weight
        + warning_bonus
        + int(review.get("answer_correctness", 0))
        + int(review.get("skill_alignment", 0))
        + int(review.get("executability", 0)) // 2
    )


def published_chapters(
    connection: duckdb.DuckDBPyConnection,
    *,
    grade_code: str,
    subject_code: str,
) -> set[str]:
    rows = connection.execute(
        """
        SELECT DISTINCT cc.stable_code
        FROM production_learning_catalog alc
        JOIN subjects sub ON sub.id = alc.subject_id
        JOIN curriculum_chapters cc ON cc.id = alc.chapter_id
        WHERE alc.grade_code = ? AND sub.code = ?
        """,
        [grade_code, subject_code],
    ).fetchall()
    return {str(row[0]) for row in rows}


def curriculum_chapters(
    connection: duckdb.DuckDBPyConnection,
    *,
    grade_code: str,
    subject_code: str,
) -> set[str]:
    rows = connection.execute(
        """
        SELECT DISTINCT cc.stable_code
        FROM curriculum_chapters cc
        JOIN school_levels sl ON sl.id = cc.grade_level_id
        JOIN subjects sub ON sub.id = cc.subject_id
        WHERE sl.code = ? AND sub.code = ? AND cc.status = 'approved'
        """,
        [grade_code, subject_code],
    ).fetchall()
    return {str(row[0]) for row in rows}


def _slot_name(item: dict[str, Any], default: str) -> str:
    return str(item.get("target_slot") or item.get("content_type") or default)


def _chapter_code(item: dict[str, Any]) -> str:
    return str(item.get("chapter") or item.get("chapter_code") or "")


def _subject_items(bundles: list[dict[str, Any]], subject_code: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for bundle in bundles:
        for slot in ("practice", "assessment"):
            item = bundle.get(slot)
            if item is None or item.get("grade") != GRADE:
                continue
            if str(item.get("subject")) != subject_code:
                continue
            items.append(item)
    return items


def plan_cm2_subject_chapters(
    bundles: list[dict[str, Any]],
    *,
    subject_code: str,
    database_path: Path,
    already_published_version_ids: set[int] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select minimum candidates to cover unpublished chapters for one CM2 subject."""
    repository = DuckDBContentQualityRepository(database_path)
    published_ids = already_published_version_ids or {
        int(item["source_version_id"])
        for item in repository.list_ai_controlled_publications(campaign_id=PUBLICATION_CAMPAIGN)
    }

    connection = duckdb.connect(str(database_path))
    try:
        published = published_chapters(connection, grade_code=GRADE, subject_code=subject_code)
        expected = curriculum_chapters(connection, grade_code=GRADE, subject_code=subject_code)
    finally:
        connection.close()
        reset_v2_connections()

    missing_chapters = sorted(expected - published)
    items = _subject_items(bundles, subject_code)
    by_chapter: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        chapter = _chapter_code(item)
        if chapter:
            by_chapter.setdefault(chapter, []).append(item)

    selected: list[Cm2PublicationCandidate] = []
    blocked: list[dict[str, Any]] = []

    for chapter_code in missing_chapters:
        chapter_items = sorted(
            by_chapter.get(chapter_code, []),
            key=lambda row: (
                0 if _slot_name(row, "practice") in {"practice", "guided_practice"} else 1,
                -candidate_priority_score(row),
            ),
        )
        chosen: Cm2PublicationCandidate | None = None
        for item in chapter_items:
            production_version_id = int(item["version_id"])
            if production_version_id in published_ids:
                continue
            eligible, reasons = assess_cm2_relaxed_eligibility(item)
            if not eligible:
                blocked.append(
                    {
                        "chapter": chapter_code,
                        "version_id": production_version_id,
                        "decision": ai_prevalidation_decision(item),
                        "reasons": list(reasons),
                    }
                )
                continue
            chosen = Cm2PublicationCandidate(
                production_version_id=production_version_id,
                chapter_code=chapter_code,
                subject_code=subject_code,
                slot=_slot_name(item, "practice"),
                decision=ai_prevalidation_decision(item),
                score=candidate_priority_score(item),
                reasons=reasons,
            )
            break
        if chosen is not None:
            selected.append(chosen)

    candidate_ids = {row.production_version_id for row in selected}
    available_drafts = repository.available_draft_source_ids(candidate_ids)
    live_hashes = _current_production_draft_hashes(database_path, candidate_ids)

    eligible_candidates: list[dict[str, Any]] = []
    for row in selected:
        item = _find_item(bundles, row.production_version_id, by_production=True)
        if item is None:
            blocked.append({"chapter": row.chapter_code, "reasons": ["bundle item missing"]})
            continue
        if row.production_version_id not in available_drafts:
            blocked.append({"chapter": row.chapter_code, "reasons": ["production draft unavailable"]})
            continue
        expected_hash = str(item.get("production_draft_hash") or item.get("source_hash") or "")
        live_hash = live_hashes.get(row.production_version_id, "")
        if expected_hash and live_hash and expected_hash != live_hash:
            blocked.append({"chapter": row.chapter_code, "reasons": ["production draft hash mismatch"]})
            continue
        eligible_candidates.append(
            {
                "version_id": row.production_version_id,
                "skill": item.get("skill_code") or item.get("skill"),
                "slot": row.slot,
                "decision": row.decision,
                "chapter": row.chapter_code,
                "provenance": build_publication_provenance(
                    item,
                    publication_campaign=PUBLICATION_CAMPAIGN,
                ),
            }
        )

    manifest = build_primary_execution_manifest(bundles, eligible_candidates)
    report = {
        "grade": GRADE,
        "subject_code": subject_code,
        "subject_label": SUBJECT_LABELS.get(subject_code, subject_code),
        "curriculum_chapters": len(expected),
        "published_chapters_before": len(published),
        "missing_chapters_before": missing_chapters,
        "selected_chapters": [row.chapter_code for row in selected],
        "manifest_count": len(manifest),
        "blocked": blocked,
        "eligible_candidates": eligible_candidates,
    }
    return manifest, report


def execute_cm2_relaxed_publication(
    repository: DuckDBContentQualityRepository,
    *,
    manifest: list[dict[str, Any]],
    bundles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Publish CM2 manifest without requiring AI_PREVALIDATED_HIGH only."""
    published: list[dict[str, Any]] = []
    for row in manifest:
        version_id = int(row["production_candidate_version_id"])
        found = _find_item(bundles, version_id, by_production=True)
        if found is None:
            raise RuntimeError(f"Execution item missing for version {version_id}")
        item = dict(found)
        item["cm2_relaxed_publication"] = True
        item["publication_campaign"] = PUBLICATION_CAMPAIGN
        eligible, reasons = assess_cm2_relaxed_eligibility(item)
        if not eligible:
            raise RuntimeError(f"Version {version_id} no longer eligible: {reasons[0] if reasons else 'unknown'}")

        exercise_id: int | None = None
        for attempt in range(LOCK_RETRY_ATTEMPTS):
            try:
                exercise_id = repository.approve_for_ai_controlled_publication(
                    item=item,
                    review_model=str(row.get("review_model", DEFAULT_REVIEW_MODEL)),
                    review_pipeline=str(row.get("review_pipeline", AI_REVIEW_PIPELINE_VERSION)),
                    reason="Publication CM2 campagne complète (politique assouplie LCAI-0018D).",
                )
                break
            except duckdb.IOException:
                if attempt >= LOCK_RETRY_ATTEMPTS - 1:
                    raise
                time.sleep(LOCK_RETRY_DELAY_SECONDS)
        if exercise_id is None:
            raise RuntimeError(f"Publication failed for version {version_id}")

        persisted = repository.read_human_decision(version_id)
        if persisted is None or persisted.get("review_status") != "APPROVED":
            raise RuntimeError(f"Publication verification failed for version {version_id}")
        if not persisted.get("production_enabled"):
            raise RuntimeError(f"Production gate not enabled for version {version_id}")
        published.append(
            {
                "version_id": version_id,
                "exercise_id": exercise_id,
                "skill_code": row.get("skill_code"),
                "chapter": row.get("chapter"),
                "ai_decision": ai_prevalidation_decision(item),
                "published_version_id": persisted.get("published_version_id"),
            }
        )
    return published


def load_bundles(database_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    bundles, loader_meta = load_primary_publication_bundles()
    return bundles, loader_meta


def _load_mapping_by_code() -> dict[str, dict[str, Any]]:
    from services.content.primary_draft_import import load_version_mapping_by_code

    return load_version_mapping_by_code()


def _load_quality_by_code() -> dict[str, dict[str, Any]]:
    from services.content.primary_ai_review import load_quality_index_by_code

    return load_quality_index_by_code()


def _build_draft_fallback_item(quality_row: dict[str, Any], mapping: dict[str, Any]) -> dict[str, Any]:
    gates = dict(quality_row.get("hard_gates") or {})
    production_version_id = int(mapping["production_version_id"])
    slot = str(quality_row.get("content_type") or "practice")
    confidence = float(quality_row.get("confidence") or 0.6)
    return {
        "version_id": production_version_id,
        "production_candidate_version_id": production_version_id,
        "isolated_version_id": int(mapping["isolated_version_id"]),
        "code": str(quality_row["code"]),
        "content_business_key": str(mapping.get("content_business_key") or quality_row["code"]),
        "grade": str(quality_row["grade"]),
        "subject": str(quality_row["subject"]),
        "chapter": str(quality_row["chapter"]),
        "skill_code": str(quality_row["skill"]),
        "skill": str(quality_row["skill"]),
        "content_type": slot,
        "target_slot": slot,
        "answer_kind": str(quality_row.get("answer_kind") or "open_response"),
        "choices": [],
        "expected_answer": quality_row.get("expected_answer") or "Open response assessed with success criteria.",
        "hard_gates_passed": all(gates.values()) if gates else False,
        "hard_gates": gates,
        "automated_checks": gates,
        "candidate_score": int(confidence * 100),
        "recommended_decision": "KEEP_FOR_REVIEW",
        "review_campaign": PRIMARY_REVIEW_CAMPAIGN,
        "publication_campaign": PUBLICATION_CAMPAIGN,
        "cm2_draft_fallback": True,
        "cm2_relaxed_publication": True,
        "ai_prevalidation_decision": "AI_REJECTED",
        "production_draft_hash": str(mapping.get("target_hash") or mapping.get("source_hash") or ""),
        "source_hash": str(mapping.get("source_hash") or ""),
    }


def plan_cm2_draft_fallback_subject(
    *,
    subject_code: str,
    database_path: Path,
    already_published_version_ids: set[int] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Plan chapter-minimum publication from quality+mappings when AI bundles are absent."""
    repository = DuckDBContentQualityRepository(database_path)
    published_ids = already_published_version_ids or {
        int(item["source_version_id"])
        for item in repository.list_ai_controlled_publications(campaign_id=PUBLICATION_CAMPAIGN)
    }
    connection = duckdb.connect(str(database_path))
    try:
        published = published_chapters(connection, grade_code=GRADE, subject_code=subject_code)
        expected = curriculum_chapters(connection, grade_code=GRADE, subject_code=subject_code)
    finally:
        connection.close()
        reset_v2_connections()

    missing_chapters = sorted(expected - published)
    quality_by_code = _load_quality_by_code()
    mapping_by_code = _load_mapping_by_code()
    by_chapter: dict[str, list[dict[str, Any]]] = {}
    for code, quality_row in quality_by_code.items():
        if quality_row.get("grade") != GRADE or quality_row.get("subject") != subject_code:
            continue
        mapping = mapping_by_code.get(code)
        if mapping is None:
            continue
        chapter = str(quality_row.get("chapter") or "")
        item = _build_draft_fallback_item(quality_row, mapping)
        by_chapter.setdefault(chapter, []).append(item)

    selected_items: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for chapter_code in missing_chapters:
        candidates = sorted(by_chapter.get(chapter_code, []), key=lambda row: -candidate_priority_score(row))
        chosen: dict[str, Any] | None = None
        for item in candidates:
            version_id = int(item["version_id"])
            if version_id in published_ids:
                continue
            eligible, reasons = assess_cm2_relaxed_eligibility(item)
            if eligible:
                chosen = item
                break
            blocked.append({"chapter": chapter_code, "version_id": version_id, "reasons": list(reasons)})
        if chosen is not None:
            selected_items.append(chosen)

    candidate_ids = {int(item["version_id"]) for item in selected_items}
    available_drafts = repository.available_draft_source_ids(candidate_ids)
    eligible_candidates: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    for item in selected_items:
        version_id = int(item["version_id"])
        if version_id not in available_drafts:
            blocked.append({"chapter": item["chapter"], "version_id": version_id, "reasons": ["draft unavailable"]})
            continue
        eligible_candidates.append(
            {
                "version_id": version_id,
                "skill": item.get("skill_code"),
                "slot": item.get("content_type"),
                "chapter": item.get("chapter"),
                "provenance": build_publication_provenance(item, publication_campaign=PUBLICATION_CAMPAIGN),
            }
        )
        manifest.append(
            {
                "production_candidate_version_id": version_id,
                "isolated_candidate_version_id": int(item.get("isolated_version_id") or version_id),
                "stable_business_key": item.get("content_business_key"),
                "grade": GRADE,
                "subject": subject_code,
                "chapter": item.get("chapter"),
                "skill_code": item.get("skill_code"),
                "content_type": item.get("content_type"),
                "ai_decision": "DRAFT_FALLBACK",
                "review_model": DEFAULT_REVIEW_MODEL,
                "review_pipeline": AI_REVIEW_PIPELINE_VERSION,
                "review_campaign": PRIMARY_REVIEW_CAMPAIGN,
                "publication_campaign": PUBLICATION_CAMPAIGN,
            }
        )

    report = {
        "grade": GRADE,
        "subject_code": subject_code,
        "subject_label": SUBJECT_LABELS.get(subject_code, subject_code),
        "source": "draft_fallback",
        "curriculum_chapters": len(expected),
        "published_chapters_before": len(published),
        "missing_chapters_before": missing_chapters,
        "selected_chapters": [str(item["chapter"]) for item in selected_items],
        "manifest_count": len(manifest),
        "blocked": blocked,
        "eligible_candidates": eligible_candidates,
    }
    return manifest, selected_items, report


def execute_cm2_draft_fallback_publication(
    repository: DuckDBContentQualityRepository,
    *,
    manifest: list[dict[str, Any]],
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    item_by_version = {int(item["version_id"]): item for item in items}
    published: list[dict[str, Any]] = []
    for row in manifest:
        version_id = int(row["production_candidate_version_id"])
        item = dict(item_by_version[version_id])
        item["cm2_relaxed_publication"] = True
        item["publication_campaign"] = PUBLICATION_CAMPAIGN
        eligible, reasons = assess_cm2_relaxed_eligibility(item)
        if not eligible:
            raise RuntimeError(f"Version {version_id} no longer eligible: {reasons[0] if reasons else 'unknown'}")
        exercise_id: int | None = None
        for attempt in range(LOCK_RETRY_ATTEMPTS):
            try:
                exercise_id = repository.approve_for_ai_controlled_publication(
                    item=item,
                    review_model=str(row.get("review_model", DEFAULT_REVIEW_MODEL)),
                    review_pipeline=str(row.get("review_pipeline", AI_REVIEW_PIPELINE_VERSION)),
                    reason="Publication CM2 draft fallback (hors revue IA bundle — LCAI-0018D).",
                )
                break
            except duckdb.IOException:
                if attempt >= LOCK_RETRY_ATTEMPTS - 1:
                    raise
                time.sleep(LOCK_RETRY_DELAY_SECONDS)
        if exercise_id is None:
            raise RuntimeError(f"Publication failed for version {version_id}")
        persisted = repository.read_human_decision(version_id)
        if persisted is None or persisted.get("review_status") != "APPROVED":
            raise RuntimeError(f"Publication verification failed for version {version_id}")
        published.append(
            {
                "version_id": version_id,
                "exercise_id": exercise_id,
                "skill_code": row.get("skill_code"),
                "chapter": row.get("chapter"),
                "ai_decision": "DRAFT_FALLBACK",
                "published_version_id": persisted.get("published_version_id"),
            }
        )
    return published
