"""LCAI-0012E controlled publication planning for CM1–5e primary grades."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from domain.content.pedagogical_review import AI_REVIEW_PIPELINE_VERSION
from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository
from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from services.content.ai_controlled_publication import (
    DEFAULT_REVIEW_MODEL,
    plan_controlled_publication,
    projected_tier1_after_publication,
    summarize_decisions,
)
from services.content.approval_coverage import coverage_impact, tier
from services.content.d4_review import ai_prevalidation_decision
from services.content.grade_appropriateness import apply_grade_assessment
from services.content.primary_ai_review import (
    AUTHORITATIVE_AUDIT_PATH,
    COMBINED_PATH,
    QUALITY_RESULTS_PATH,
    SUMMARY_PATH,
)
from services.content.primary_ai_review import (
    CAMPAIGN_ID as PRIMARY_REVIEW_CAMPAIGN,
)
from services.content.primary_draft_import import (
    IMPORT_CAMPAIGN,
    load_version_mapping,
    load_version_mapping_by_code,
    load_version_mapping_index,
    reconcile_review_counts,
    validate_review_linkage,
)
from services.content.primary_integration import PRIMARY_GRADES

PUBLICATION_CAMPAIGN = "LCAI-0012E-CM1-5E-PUBLICATION-V1"
REVIEW_ARTIFACT = "resources/content/quality/lcai_0012e_ai_pedagogical_review_authoritative.jsonl"
MANIFEST_PATH = Path("resources/content/quality/lcai_0012e_ai_controlled_publication_manifest.json")
DRY_RUN_PATH = Path("resources/content/quality/lcai_0012e_ai_controlled_publication_dry_run.json")
UNRESOLVED_CURRICULUM_EXCLUDED = 18

GRADE_LABELS = {
    "FR-CM1": "CM1",
    "FR-CM2": "CM2",
    "FR-6E": "6e",
    "FR-5E": "5e",
}


def _quality_index_by_isolated_version() -> dict[int, dict[str, Any]]:
    rows = json.loads(QUALITY_RESULTS_PATH.read_text(encoding="utf-8"))
    return {int(row["version_id"]): row for row in rows}


def _repair_grade_assessment(item: dict[str, Any]) -> dict[str, Any]:
    audit = item.get("ai_pedagogical_review") or {}
    ai_grade_score = int(audit.get("grade_appropriateness", 0))
    if (
        str(audit.get("expected_answer_match", "")) in {"CORRECT", "ACCEPTABLE_VARIANT"}
        and str(audit.get("confidence", "")) == "HIGH"
    ):
        ai_grade_score = max(ai_grade_score, 85)
    return apply_grade_assessment(item, ai_grade_score=ai_grade_score)


def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    updated = _repair_grade_assessment(dict(item))
    updated["review_campaign"] = str(
        updated.get("review_campaign") or updated.get("campaign_id") or PRIMARY_REVIEW_CAMPAIGN
    )
    updated["publication_campaign"] = PUBLICATION_CAMPAIGN
    updated["skill"] = str(updated.get("skill_code") or updated.get("skill", ""))
    return updated


def apply_production_mapping(
    item: dict[str, Any],
    *,
    mapping_index: dict[int, dict[str, Any]],
    mapping_by_code: dict[str, dict[str, Any]],
    quality_by_version: dict[int, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    isolated_version_id = int(item["version_id"])
    quality_row = quality_by_version.get(isolated_version_id, {})
    business_key = str(quality_row.get("code") or item.get("code") or "")
    mapping = mapping_index.get(isolated_version_id)
    if mapping is None and business_key:
        mapping = mapping_by_code.get(business_key)
    if mapping is None:
        return item, None
    production_version_id = int(mapping["production_version_id"])
    mapped = dict(item)
    mapped["isolated_version_id"] = isolated_version_id
    mapped["production_candidate_version_id"] = production_version_id
    mapped["version_id"] = production_version_id
    mapped["content_business_key"] = str(mapping.get("content_business_key") or business_key)
    mapped["code"] = str(mapped.get("code") or mapped["content_business_key"] or business_key)
    mapped["source_hash"] = mapping.get("source_hash")
    mapped["production_draft_hash"] = mapping.get("target_hash")
    mapped["import_campaign"] = mapping.get("campaign")
    return mapped, mapping


def load_primary_publication_bundles(
    *,
    combined_path: Path | None = None,
    database_path: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = json.loads((combined_path or COMBINED_PATH).read_text(encoding="utf-8"))
    mapping_index = load_version_mapping_index()
    mapping_by_code = load_version_mapping_by_code()
    quality_by_version = _quality_index_by_isolated_version()
    bundles: list[dict[str, Any]] = []
    unmapped: list[int] = []
    for bundle in payload.get("skills", []):
        updated = dict(bundle)
        for slot in ("practice", "assessment"):
            item = updated.get(slot)
            if item is None:
                continue
            normalized = _normalize_item(item)
            mapped, mapping = apply_production_mapping(
                normalized,
                mapping_index=mapping_index,
                mapping_by_code=mapping_by_code,
                quality_by_version=quality_by_version,
            )
            if mapping is None and ai_prevalidation_decision(normalized) == "AI_PREVALIDATED_HIGH":
                unmapped.append(int(normalized["version_id"]))
            updated[slot] = mapped
        bundles.append(updated)
    return bundles, {
        "combined_path": str(combined_path or COMBINED_PATH),
        "authoritative_audit_path": str(AUTHORITATIVE_AUDIT_PATH),
        "summary_path": str(SUMMARY_PATH),
        "mapping_records": len(load_version_mapping()),
        "unmapped_ai_high_isolated_ids": unmapped,
    }


def verify_review_completion(summary_path: Path | None = None) -> dict[str, Any]:
    summary = json.loads((summary_path or SUMMARY_PATH).read_text(encoding="utf-8"))
    population = summary.get("population", {})
    decisions = summary.get("decisions", {})
    workload = summary.get("workload", {})
    expected = int(population.get("expected", 0))
    reviewed = int(population.get("reviewed", 0))
    remaining = int(population.get("remaining", 1))
    complete = bool(population.get("main_campaign_complete")) and remaining == 0 and expected > 0
    return {
        "complete": complete,
        "expected_candidates": expected,
        "reviewed_candidates": reviewed,
        "remaining_candidates": remaining,
        "decisions": decisions,
        "teacher_cases": int(decisions.get("TEACHER_REVIEW_REQUIRED", 0)),
        "fact_check_cases": int(decisions.get("FACT_CHECK_REQUIRED", 0)),
        "ai_rejected_cases": int(decisions.get("AI_REJECTED", 0)),
        "warning_cases": int(decisions.get("AI_PREVALIDATED_WITH_WARNING", 0)),
        "high_cases": int(decisions.get("AI_PREVALIDATED_HIGH", 0)),
        "alternates_queued": int(workload.get("alternates_queued", 0)),
        "alternates_reviewed": int(workload.get("alternates_reviewed", 0)),
        "replacement_required": int(workload.get("replacement_required", 0)),
        "unresolved_curriculum_excluded": int(
            summary.get("unresolved_curriculum_excluded", UNRESOLVED_CURRICULUM_EXCLUDED)
        ),
        "review_campaign_id": str(summary.get("campaign_id", PRIMARY_REVIEW_CAMPAIGN)),
        "publication_campaign_id": PUBLICATION_CAMPAIGN,
        "count_reconciliation": reconcile_review_counts(),
    }


def verify_import_state(database_path: Path) -> dict[str, Any]:
    repository = DuckDBContentQualityRepository(database_path)
    mapping = load_version_mapping()
    mapping_index = load_version_mapping_index()
    production_ids = {int(entry["production_version_id"]) for entry in mapping}
    available_drafts = repository.available_draft_source_ids(production_ids)

    connection = connect_v2(database_path, read_only=True)
    try:
        draft_rows = connection.execute(
            """
            SELECT cv.id, cv.status, cpg.production_enabled
            FROM content_versions cv
            LEFT JOIN content_production_gates cpg ON cpg.content_version_id=cv.id
            WHERE cv.id IN ({ids})
            """.format(ids=",".join(str(item) for item in sorted(production_ids)))
        ).fetchall()
        approved_count = connection.execute(
            """
            SELECT COUNT(*) FROM content_versions cv
            WHERE cv.id IN ({ids}) AND cv.status='approved'
            """.format(ids=",".join(str(item) for item in sorted(production_ids)))
        ).fetchone()[0]
    finally:
        connection.close()

    draft_only = all(str(row[1]) == "draft" for row in draft_rows)
    gates_disabled = all(row[2] in (None, False) for row in draft_rows)
    linkage = validate_review_linkage(database_path=database_path)
    ambiguous = [
        isolated_id for isolated_id, entry in mapping_index.items() if int(entry["production_version_id"]) <= 0
    ]
    return {
        "import_campaign": IMPORT_CAMPAIGN,
        "mapping_records": len(mapping),
        "production_draft_ids_expected": len(production_ids),
        "production_drafts_found": len(draft_rows),
        "production_drafts_available": len(available_drafts),
        "lifecycle_draft_only": draft_only,
        "production_gates_disabled": gates_disabled,
        "approved_versions_from_import": int(approved_count),
        "mapping_complete": len(mapping) >= 1293 and not ambiguous,
        "mapping_ambiguous_count": len(ambiguous),
        "unresolved_curriculum_excluded": UNRESOLVED_CURRICULUM_EXCLUDED,
        "review_linkage": linkage,
        "pass": (
            len(available_drafts) == len(production_ids)
            and draft_only
            and gates_disabled
            and int(approved_count) == 0
            and linkage["ai_high_unresolved"] == 0
            and not ambiguous
        ),
    }


def primary_coverage_rows(database_path: Path | None = None) -> list[dict[str, Any]]:
    repository = DuckDBContentFactoryRepository(database_path)
    output: list[dict[str, Any]] = []
    for row in repository.active_skill_coverage(grade_codes=PRIMARY_GRADES):
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
                "skill_name": row.skill_label,
                "approved_practice": practice,
                "approved_assessment": assessment,
            }
        )
    return output


def tier_counts_by_grade(coverage_rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    by_grade: dict[str, dict[str, int]] = {}
    for grade_code in PRIMARY_GRADES:
        label = GRADE_LABELS[grade_code]
        rows = [row for row in coverage_rows if row["grade"] == grade_code]
        by_grade[label] = {
            "tier1": sum(tier(int(r["approved_practice"]) > 0, int(r["approved_assessment"]) > 0) == 1 for r in rows),
            "tier2": sum(tier(int(r["approved_practice"]) > 0, int(r["approved_assessment"]) > 0) == 2 for r in rows),
            "tier3": sum(tier(int(r["approved_practice"]) > 0, int(r["approved_assessment"]) > 0) == 3 for r in rows),
            "total_active_skills": len(rows),
        }
    return by_grade


def attach_coverage_impacts(
    bundles: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    coverage = {str(row["skill"]): row for row in coverage_rows}
    updated: list[dict[str, Any]] = []
    for bundle in bundles:
        skill = str(bundle.get("skill_code") or bundle.get("skill", ""))
        cov = coverage.get(skill, {})
        new_bundle = dict(bundle)
        for slot in ("practice", "assessment"):
            item = new_bundle.get(slot)
            if item is None:
                continue
            slot_name = str(item.get("target_slot") or item.get("content_type") or slot)
            enriched = dict(item)
            enriched["coverage_impact"] = coverage_impact(cov, slot_name) if cov else {}
            new_bundle[slot] = enriched
        updated.append(new_bundle)
    return updated


def _current_production_draft_hashes(database_path: Path, version_ids: set[int]) -> dict[int, str]:
    if not version_ids:
        return {}
    repository = DuckDBContentQualityRepository(database_path)
    inventory = {int(item["version_id"]): item for item in repository.draft_inventory(grade_codes=PRIMARY_GRADES)}
    return {
        version_id: str(inventory[version_id].get("payload_hash") or inventory[version_id].get("target_hash") or "")
        for version_id in version_ids
        if version_id in inventory
    }


def build_primary_execution_manifest(
    bundles: list[dict[str, Any]],
    eligible_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    eligible_production_ids = {int(candidate["version_id"]) for candidate in eligible_candidates}
    manifest: list[dict[str, Any]] = []
    for bundle in bundles:
        for slot in ("practice", "assessment"):
            item = bundle.get(slot)
            if item is None:
                continue
            production_version_id = int(item["version_id"])
            if production_version_id not in eligible_production_ids:
                continue
            review = item.get("ai_pedagogical_review") or {}
            impact = item.get("coverage_impact") or {}
            current = impact.get("current") or {}
            potential = impact.get("potential") or {}
            manifest.append(
                {
                    "production_candidate_version_id": production_version_id,
                    "isolated_candidate_version_id": int(item.get("isolated_version_id") or production_version_id),
                    "stable_business_key": item.get("content_business_key"),
                    "grade": item.get("grade"),
                    "subject": item.get("subject"),
                    "chapter": item.get("chapter"),
                    "skill_code": item.get("skill_code") or item.get("skill"),
                    "content_type": item.get("target_slot") or item.get("content_type"),
                    "ai_decision": ai_prevalidation_decision(item),
                    "confidence": review.get("confidence") or item.get("ai_prevalidation_confidence"),
                    "review_model": review.get("reviewer_model", DEFAULT_REVIEW_MODEL),
                    "review_pipeline": review.get("ai_review_pipeline_version", AI_REVIEW_PIPELINE_VERSION),
                    "review_campaign": item.get("review_campaign"),
                    "publication_campaign": PUBLICATION_CAMPAIGN,
                    "review_artifact": REVIEW_ARTIFACT,
                    "source_hash": item.get("source_hash"),
                    "production_draft_hash": item.get("production_draft_hash"),
                    "current_production_state": {
                        "practice_approved": current.get("practice_approved"),
                        "assessment_approved": current.get("assessment_approved"),
                        "tier": current.get("tier"),
                    },
                    "projected_production_state": {
                        "practice_approved": potential.get("practice_approved"),
                        "assessment_approved": potential.get("assessment_approved"),
                        "tier": potential.get("tier"),
                    },
                    "review_idempotency_key": review.get("review_idempotency_key"),
                    "grade_assessment_status": (item.get("grade_assessment") or {}).get("status"),
                }
            )
    manifest.sort(
        key=lambda row: (
            str(row["grade"]),
            str(row["subject"]),
            str(row["skill_code"]),
            str(row["content_type"]),
            int(row["production_candidate_version_id"]),
        )
    )
    return manifest


def _bundle_skill(bundle: dict[str, Any]) -> str:
    return str(bundle.get("skill_code") or bundle.get("skill") or "")


def _skill_lookup_by_version(bundles: list[dict[str, Any]]) -> dict[int, str]:
    lookup: dict[int, str] = {}
    for bundle in bundles:
        skill = _bundle_skill(bundle)
        for slot in ("practice", "assessment"):
            item = bundle.get(slot)
            if item is None:
                continue
            lookup[int(item["version_id"])] = skill
    return lookup


def _enrich_eligible_candidates(
    eligible_candidates: list[dict[str, Any]],
    *,
    skill_by_version: dict[int, str],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for candidate in eligible_candidates:
        updated = dict(candidate)
        version_id = int(updated["version_id"])
        skill = str(updated.get("skill") or skill_by_version.get(version_id) or "")
        updated["skill"] = skill
        enriched.append(updated)
    return enriched


def _already_published_version_ids(
    repository: DuckDBContentQualityRepository,
    *,
    campaign_id: str,
) -> set[int]:
    return {
        int(item["source_version_id"]) for item in repository.list_ai_controlled_publications(campaign_id=campaign_id)
    }


def plan_primary_controlled_publication(
    bundles: list[dict[str, Any]],
    *,
    database_path: Path,
    coverage_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = coverage_rows or primary_coverage_rows(database_path)
    enriched_bundles = attach_coverage_impacts(bundles, rows)
    plan = plan_controlled_publication(
        enriched_bundles,
        required_decision="AI_PREVALIDATED_HIGH",
        campaign=PUBLICATION_CAMPAIGN,
        review_campaign=PRIMARY_REVIEW_CAMPAIGN,
    )
    skill_by_version = _skill_lookup_by_version(enriched_bundles)
    plan["eligible_candidates"] = _enrich_eligible_candidates(
        plan["eligible_candidates"],
        skill_by_version=skill_by_version,
    )
    repository = DuckDBContentQualityRepository(database_path)
    already_published = _already_published_version_ids(repository, campaign_id=PUBLICATION_CAMPAIGN)

    candidate_production_ids = {int(candidate["version_id"]) for candidate in plan["eligible_candidates"]}
    available_drafts = repository.available_draft_source_ids(candidate_production_ids)
    live_hashes = _current_production_draft_hashes(database_path, candidate_production_ids)

    eligible_candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    unresolved_mappings: list[int] = []
    hash_mismatches: list[int] = []

    for candidate in plan["eligible_candidates"]:
        production_version_id = int(candidate["version_id"])
        item = _find_item(enriched_bundles, production_version_id, by_production=True)
        if item is None:
            blocked.append({"version_id": production_version_id, "reasons": ["bundle item missing"]})
            continue
        isolated_version_id = int(item.get("isolated_version_id") or production_version_id)
        if item.get("isolated_version_id") is None:
            unresolved_mappings.append(isolated_version_id)
            blocked.append(
                {
                    "production_version_id": production_version_id,
                    "isolated_version_id": isolated_version_id,
                    "reasons": ["missing production mapping"],
                }
            )
            continue
        expected_hash = str(item.get("production_draft_hash") or item.get("source_hash") or "")
        live_hash = live_hashes.get(production_version_id, "")
        if expected_hash and live_hash and expected_hash != live_hash:
            hash_mismatches.append(production_version_id)
            blocked.append(
                {
                    "production_version_id": production_version_id,
                    "isolated_version_id": isolated_version_id,
                    "reasons": ["production draft hash mismatch"],
                    "expected_hash": expected_hash,
                    "live_hash": live_hash,
                }
            )
            continue
        if production_version_id in already_published:
            continue
        if production_version_id not in available_drafts:
            blocked.append(
                {
                    "production_version_id": production_version_id,
                    "isolated_version_id": isolated_version_id,
                    "skill": candidate.get("skill"),
                    "slot": candidate.get("slot"),
                    "reasons": ["production draft unavailable in database"],
                }
            )
            continue
        eligible_candidates.append(dict(candidate))

    eligible_candidates = _enrich_eligible_candidates(
        eligible_candidates,
        skill_by_version=skill_by_version,
    )

    eligible_ids = {int(item["version_id"]) for item in eligible_candidates}
    practice_count = sum(1 for item in eligible_candidates if str(item.get("slot")) in {"practice", "guided_practice"})
    assessment_count = sum(1 for item in eligible_candidates if str(item.get("slot")) == "assessment")

    complete_skill_pairs = 0
    practice_only_skill_slots = 0
    assessment_only_skill_slots = 0
    for bundle in enriched_bundles:
        practice = bundle.get("practice")
        assessment = bundle.get("assessment")
        practice_eligible = practice is not None and int(practice["version_id"]) in eligible_ids
        assessment_eligible = assessment is not None and int(assessment["version_id"]) in eligible_ids
        if practice_eligible and assessment_eligible:
            complete_skill_pairs += 1
        elif practice_eligible:
            practice_only_skill_slots += 1
        elif assessment_eligible:
            assessment_only_skill_slots += 1

    tier_projection = projected_tier1_after_publication(rows, eligible_candidates)
    projected_by_grade = _project_tier_counts_by_grade(rows, eligible_candidates)
    current_by_grade = tier_counts_by_grade(rows)

    warning_excluded = 0
    fact_check_excluded = 0
    for bundle in enriched_bundles:
        for slot in ("practice", "assessment"):
            item = bundle.get(slot)
            if item is None:
                continue
            decision = ai_prevalidation_decision(item)
            if decision == "AI_PREVALIDATED_WITH_WARNING":
                warning_excluded += 1
            if item.get("fact_check_required"):
                fact_check_excluded += 1

    replacement_required = sum(1 for item in plan["rejected"] if item.get("replacement_required"))
    unique_final_candidates = sum(
        1
        for bundle in enriched_bundles
        for slot in ("practice", "assessment")
        if (item := bundle.get(slot)) is not None
    )

    return {
        "bundles": enriched_bundles,
        "plan": plan,
        "eligible_candidates": eligible_candidates,
        "eligible_candidate_count": len(eligible_candidates),
        "eligible_practice": practice_count,
        "eligible_assessment": assessment_count,
        "complete_skill_pairs": complete_skill_pairs,
        "practice_only_skill_slots": practice_only_skill_slots,
        "assessment_only_skill_slots": assessment_only_skill_slots,
        "partial_skill_pairs": practice_only_skill_slots + assessment_only_skill_slots,
        "already_published": len(already_published),
        "duplicates_skipped": len(already_published),
        "blocked": blocked + plan["blocked"],
        "blocked_count": len(blocked) + len(plan["blocked"]),
        "teacher_excluded": len(plan["teacher"]),
        "fact_check_excluded": fact_check_excluded,
        "warning_excluded": warning_excluded,
        "rejected_excluded": len(plan["rejected"]),
        "replacement_required": replacement_required,
        "unresolved_production_draft_mappings": len(unresolved_mappings),
        "hash_mismatch_count": len(hash_mismatches),
        "unique_final_candidates": unique_final_candidates,
        "tier_projection": tier_projection,
        "current_coverage_by_grade": current_by_grade,
        "projected_coverage_by_grade": projected_by_grade,
        "coverage_delta_by_grade": _coverage_delta(current_by_grade, projected_by_grade),
        "decisions": summarize_decisions(enriched_bundles),
    }


def _coverage_delta(
    current: dict[str, dict[str, int]],
    projected: dict[str, dict[str, int]],
) -> dict[str, dict[str, int]]:
    delta: dict[str, dict[str, int]] = {}
    for grade in current:
        delta[grade] = {
            key: int(projected[grade].get(key, 0)) - int(current[grade].get(key, 0))
            for key in ("tier1", "tier2", "tier3")
        }
    return delta


def _project_tier_counts_by_grade(
    coverage_rows: list[dict[str, Any]],
    eligible_candidates: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    by_skill_slot: dict[str, set[str]] = {}
    for candidate in eligible_candidates:
        skill = str(candidate["skill"])
        slot = str(candidate["slot"])
        if slot == "guided_practice":
            slot = "practice"
        by_skill_slot.setdefault(skill, set()).add(slot)

    projected_rows: list[dict[str, Any]] = []
    for row in coverage_rows:
        skill = str(row["skill"])
        practice = int(row["approved_practice"]) > 0
        assessment = int(row["approved_assessment"]) > 0
        slots = by_skill_slot.get(skill, set())
        practice = practice or "practice" in slots
        assessment = assessment or "assessment" in slots
        projected_rows.append(
            {
                "grade": row["grade"],
                "skill": skill,
                "approved_practice": int(practice),
                "approved_assessment": int(assessment),
            }
        )
    return tier_counts_by_grade(projected_rows)


def _find_item(
    bundles: list[dict[str, Any]],
    version_id: int,
    *,
    by_production: bool = False,
) -> dict[str, Any] | None:
    for bundle in bundles:
        for slot in ("practice", "assessment"):
            item = bundle.get(slot)
            if item is None:
                continue
            if by_production and int(item["version_id"]) == version_id:
                return item
            if not by_production and int(item.get("isolated_version_id") or item["version_id"]) == version_id:
                return item
    return None


def build_primary_publication_report(
    *,
    review_status: dict[str, Any],
    import_status: dict[str, Any],
    preparation: dict[str, Any],
    execute: bool,
) -> dict[str, Any]:
    return {
        "mode": "EXECUTE" if execute else "DRY_RUN",
        "campaign": PUBLICATION_CAMPAIGN,
        "review_campaign": PRIMARY_REVIEW_CAMPAIGN,
        "required_decision": "AI_PREVALIDATED_HIGH",
        "import_status": import_status,
        "review_status": review_status,
        "count_reconciliation": review_status.get("count_reconciliation"),
        "unique_final_candidates": preparation["unique_final_candidates"],
        "eligible_candidate_count": preparation["eligible_candidate_count"],
        "eligible_practice": preparation["eligible_practice"],
        "eligible_assessment": preparation["eligible_assessment"],
        "complete_skill_pairs": preparation["complete_skill_pairs"],
        "practice_only_skill_slots": preparation["practice_only_skill_slots"],
        "assessment_only_skill_slots": preparation["assessment_only_skill_slots"],
        "partial_skill_pairs": preparation["partial_skill_pairs"],
        "already_published": preparation["already_published"],
        "duplicates_skipped": preparation["duplicates_skipped"],
        "blocked_count": preparation["blocked_count"],
        "teacher_excluded": preparation["teacher_excluded"],
        "fact_check_excluded": preparation["fact_check_excluded"],
        "warning_excluded": preparation["warning_excluded"],
        "rejected_excluded": preparation["rejected_excluded"],
        "replacement_required": preparation["replacement_required"],
        "unresolved_curriculum_excluded": review_status["unresolved_curriculum_excluded"],
        "unresolved_production_draft_mappings": preparation["unresolved_production_draft_mappings"],
        "hash_mismatch_count": preparation["hash_mismatch_count"],
        "decisions": preparation["decisions"],
        "tier_projection": preparation["tier_projection"],
        "current_coverage_by_grade": preparation["current_coverage_by_grade"],
        "projected_coverage_by_grade": preparation["projected_coverage_by_grade"],
        "coverage_delta_by_grade": preparation["coverage_delta_by_grade"],
        "blocked": preparation["blocked"][:20],
        "production_db_modified": False,
        "published": [],
    }
