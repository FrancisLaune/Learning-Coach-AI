"""LCAI-0012D4 Wave 2 — Tier 3 corrective progression with minimal human review."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from domain.content.factory import CanonicalContentType
from services.content.approval_coverage import coverage_impact, normalized_type, tier
from services.content.ai_review_calibration import is_ai_prevalidated_decision
from services.content.d4_wave1 import (
    build_queue_record,
    classify_wave1_human_review,
    prepare_ranked_records,
)
from services.content.expansion import (
    ContentSlot,
    build_slot_quality_index,
    generation_gaps,
    is_usable_quality_record,
    slot_has_usable_candidate,
)

PIPELINE_VERSION = "lcai-0012d4-wave2-v1"
REVIEW_CAMPAIGN = "LCAI-0012D4-WAVE2"
REVIEW_QUEUE_STATUS_ACTIVE = "ACTIVE"
WAVE_BAND_TIER3 = "TIER3_CORRECTIVE"
LOT_SIZE_DEFAULT = 50
PRODUCTION_SLOTS = ("practice", "assessment")


def is_technically_blocked_item(item: dict[str, Any]) -> bool:
    return classify_wave1_human_review(item)["classification"] == "TECHNICALLY_BLOCKED"


def subject_tier1_ratios(coverage_rows: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, int] = defaultdict(int)
    tier1: dict[str, int] = defaultdict(int)
    for row in coverage_rows:
        subject = str(row["subject"])
        totals[subject] += 1
        if tier(int(row["approved_practice"]) > 0, int(row["approved_assessment"]) > 0) == 1:
            tier1[subject] += 1
    return {subject: tier1[subject] / totals[subject] for subject in totals}


def _interleave_grades(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grade3 = [row for row in rows if row["grade"] == "FR-3E"]
    grade4 = [row for row in rows if row["grade"] == "FR-4E"]
    output: list[dict[str, Any]] = []
    index = 0
    while index < max(len(grade3), len(grade4)):
        if index < len(grade3):
            output.append(grade3[index])
        if index < len(grade4):
            output.append(grade4[index])
        index += 1
    return output


def load_wave2_assigned_skills(quality_dir: Path, *, before_lot: int) -> set[str]:
    """Return skill codes already assigned to previous Wave-2 lots."""
    assigned: set[str] = set()
    for lot_number in range(1, before_lot):
        skills_path = quality_dir / f"lcai_0012d4_wave2_lot{lot_number}_skills.json"
        if not skills_path.exists():
            continue
        payload = json.loads(skills_path.read_text(encoding="utf-8"))
        for row in payload if isinstance(payload, list) else payload.get("skills", []):
            assigned.add(str(row.get("skill") or row.get("skill_code")))
    return assigned


def select_wave2_lot_skills(
    coverage_rows: list[dict[str, Any]],
    *,
    lot_number: int = 1,
    lot_size: int = LOT_SIZE_DEFAULT,
    exclude_skills: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Select Tier-3 skills for one Wave-2 lot with subject and grade balance."""
    ratios = subject_tier1_ratios(coverage_rows)
    excluded = exclude_skills or set()
    tier3_rows = [
        row
        for row in coverage_rows
        if tier(int(row["approved_practice"]) > 0, int(row["approved_assessment"]) > 0) == 3
        and str(row["skill"]) not in excluded
    ]
    subjects = sorted(
        {str(row["subject"]) for row in tier3_rows},
        key=lambda subject: (ratios.get(subject, 1.0), 1 if subject == "MATHEMATICS" else 0, subject),
    )
    ordered: list[dict[str, Any]] = []
    for subject in subjects:
        subject_rows = [row for row in tier3_rows if row["subject"] == subject]
        ordered.extend(_interleave_grades(subject_rows))
    start = (lot_number - 1) * lot_size
    end = start + lot_size
    return ordered[start:end]


def _slot_decision_closed(status: str | None) -> bool:
    return status in {"APPROVED", "REJECTED"}


def select_best_reviewable_candidate(
    candidates: list[dict[str, Any]],
    review_statuses: dict[int, str],
) -> tuple[dict[str, Any] | None, int]:
    """Return the best human-reviewable candidate, skipping blocked items."""
    for index, candidate in enumerate(candidates):
        version_id = int(candidate["version_id"])
        status = review_statuses.get(version_id)
        if _slot_decision_closed(status):
            continue
        if candidate["recommended_decision"] == "REJECT":
            continue
        if not candidate["hard_gates_passed"]:
            continue
        if is_technically_blocked_item(candidate):
            continue
        remaining = sum(
            1
            for item in candidates[index + 1 :]
            if not _slot_decision_closed(review_statuses.get(int(item["version_id"])))
            and item["recommended_decision"] != "REJECT"
            and item["hard_gates_passed"]
            and not is_technically_blocked_item(item)
        )
        return dict(candidate), remaining
    return None, 0


def select_best_existing_candidate(
    candidates: list[dict[str, Any]],
    review_statuses: dict[int, str],
) -> tuple[dict[str, Any] | None, int]:
    """Return the best pending candidate and remaining alternate count."""
    for candidate in candidates:
        version_id = int(candidate["version_id"])
        status = review_statuses.get(version_id)
        if _slot_decision_closed(status):
            continue
        if candidate["recommended_decision"] == "REJECT":
            continue
        if not candidate["hard_gates_passed"]:
            continue
        remaining = sum(
            1
            for item in candidates[candidates.index(candidate) + 1 :]
            if not _slot_decision_closed(review_statuses.get(int(item["version_id"])))
            and item["recommended_decision"] != "REJECT"
            and item["hard_gates_passed"]
        )
        return dict(candidate), remaining
    return None, 0


def build_wave2_lot_plan(
    lot_skills: list[dict[str, Any]],
    ranked_by_skill_slot: dict[str, list[dict[str, Any]]],
    review_statuses: dict[int, str],
    *,
    active_skills: tuple[Any, ...],
    quality_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Plan existing-candidate usage and generation gaps for one lot."""
    skill_codes = {str(row["skill"]) for row in lot_skills}
    skills_by_code = {str(row["skill"]): row for row in lot_skills}
    active_by_code = {row.target.primary_skill_code: row for row in active_skills}
    quality_index = build_slot_quality_index(quality_results)

    slot_targets: list[dict[str, Any]] = []
    generation_requests: list[dict[str, Any]] = []

    for row in lot_skills:
        skill = str(row["skill"])
        active = active_by_code[skill]
        for slot_name in PRODUCTION_SLOTS:
            candidates = ranked_by_skill_slot.get(f"{skill}|{slot_name}", [])
            selected, alternate_count = select_best_reviewable_candidate(candidates, review_statuses)
            slot = ContentSlot(
                CanonicalContentType.PRACTICE if slot_name == "practice" else CanonicalContentType.ASSESSMENT,
                2,
            )
            needs_generation = selected is None and not slot_has_usable_candidate(active, slot, quality_index)
            target = {
                "skill": skill,
                "skill_name": row.get("skill_name", skill),
                "grade": row["grade"],
                "subject": row["subject"],
                "chapter": row["chapter"],
                "slot": slot_name,
                "candidate": selected,
                "alternate_count": alternate_count,
                "candidate_source": "existing" if selected is not None else None,
                "needs_generation": needs_generation,
            }
            slot_targets.append(target)
            if needs_generation:
                generation_requests.append(
                    {
                        "skill": skill,
                        "grade": row["grade"],
                        "subject": row["subject"],
                        "chapter": row["chapter"],
                        "slot": slot_name,
                    }
                )

    all_gaps = generation_gaps(active_skills, quality_index)
    lot_gaps = [
        gap
        for gap in all_gaps
        if gap.skill.target.primary_skill_code in skill_codes
        and normalized_type(gap.slot.content_type.value) in PRODUCTION_SLOTS
    ]

    return {
        "lot_skills": lot_skills,
        "slot_targets": slot_targets,
        "generation_requests": generation_requests,
        "planned_gaps": [
            {
                "skill": gap.skill.target.primary_skill_code,
                "slot": normalized_type(gap.slot.content_type.value),
                "gap_key": "|".join(
                    (
                        gap.skill.target.grade_code,
                        gap.skill.target.subject_code,
                        gap.skill.target.chapter_code,
                        gap.skill.target.primary_skill_code,
                        gap.slot.content_type.value,
                        str(gap.slot.difficulty),
                    )
                ),
            }
            for gap in lot_gaps
        ],
        "skills_by_code": skills_by_code,
    }


def normalize_wave2_review_item(
    item: dict[str, Any],
    coverage_row: dict[str, Any],
    *,
    candidate_source: str,
    alternate_count: int = 0,
    wave2_rank: int | None = None,
    lot_number: int = 1,
) -> dict[str, Any]:
    """Normalize one Wave-2 review item with campaign metadata."""
    normalized = dict(item)
    skill = str(coverage_row["skill"])
    target_slot = normalized_type(str(normalized.get("target_slot") or normalized.get("content_type")))
    if "coverage_impact" not in normalized:
        normalized["coverage_impact"] = coverage_impact(coverage_row, target_slot)

    impact = normalized["coverage_impact"]
    normalized["version_id"] = int(normalized["version_id"])
    normalized["grade"] = str(normalized.get("grade", coverage_row["grade"]))
    normalized["subject"] = str(normalized.get("subject", coverage_row["subject"]))
    normalized["chapter"] = str(normalized.get("chapter", coverage_row["chapter"]))
    normalized["skill"] = skill
    normalized["skill_code"] = skill
    normalized["skill_name"] = str(normalized.get("skill_name", coverage_row.get("skill_name", skill)))
    normalized["target_slot"] = target_slot
    normalized["missing_slot"] = target_slot
    normalized["missing_slot_label"] = "Entraînement" if target_slot == "practice" else "Évaluation"
    normalized["candidate_score"] = int(normalized.get("candidate_score", 0))
    normalized["recommended_decision"] = str(normalized.get("recommended_decision", "KEEP_FOR_REVIEW"))
    normalized["quality_result"] = str(normalized.get("quality_result", normalized["recommended_decision"]))
    normalized["hard_gates_passed"] = bool(normalized.get("hard_gates_passed", False))
    normalized["automated_checks"] = dict(normalized.get("automated_checks", {}))
    normalized["quality_reason"] = list(normalized.get("quality_reason", ()))
    normalized["current_tier"] = int(impact["current"]["tier"])
    normalized["projected_tier"] = int(impact["potential"]["tier"])
    normalized["alternate_count"] = int(alternate_count)
    normalized["candidate_source"] = candidate_source
    normalized["review_campaign"] = REVIEW_CAMPAIGN
    normalized["review_queue_status"] = REVIEW_QUEUE_STATUS_ACTIVE
    normalized["wave_band"] = WAVE_BAND_TIER3
    normalized["lot_number"] = lot_number
    normalized["pipeline_version"] = PIPELINE_VERSION
    if wave2_rank is not None:
        normalized["wave2_rank"] = wave2_rank
    return normalized


def build_wave2_human_queue(
    lot_plan: dict[str, Any],
    coverage_by_skill: dict[str, dict[str, Any]],
    *,
    lot_number: int = 1,
) -> list[dict[str, Any]]:
    """Build the minimal Wave-2 human queue (one candidate per slot)."""
    queue: list[dict[str, Any]] = []
    for target in lot_plan["slot_targets"]:
        candidate = target.get("candidate")
        if candidate is None:
            continue
        if is_technically_blocked_item(candidate):
            continue
        coverage_row = coverage_by_skill[str(target["skill"])]
        queue.append(
            normalize_wave2_review_item(
                candidate,
                coverage_row,
                candidate_source=str(target["candidate_source"]),
                alternate_count=int(target["alternate_count"]),
                lot_number=lot_number,
            )
        )

    def queue_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
        impact = item["coverage_impact"]
        completes = 0 if impact["completes_tier_1"] else 1
        return (
            completes,
            1 if item["subject"] == "MATHEMATICS" else 0,
            -int(item["candidate_score"]),
            str(item["grade"]),
            str(item["subject"]),
            str(item["skill"]),
            0 if item["target_slot"] == "practice" else 1,
        )

    queue.sort(key=queue_sort_key)
    by_skill: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in queue:
        by_skill[str(item["skill"])].append(item)
    for items in by_skill.values():
        slots = {str(item["target_slot"]) for item in items}
        if slots == set(PRODUCTION_SLOTS):
            pass

    for rank, item in enumerate(queue, 1):
        item["wave2_rank"] = rank
        item["projected_tier1_if_approved"] = None

    return queue


def audit_wave2_queue(queue: list[dict[str, Any]]) -> dict[str, Any]:
    """Audit Wave-2 queue for human-review safety."""
    audits = [classify_wave1_human_review(item) for item in queue]
    blocked = sum(1 for audit in audits if audit["classification"] == "TECHNICALLY_BLOCKED")
    pedagogical = sum(1 for audit in audits if audit["classification"] == "REQUIRES_PEDAGOGICAL_JUDGEMENT")
    safe = sum(1 for audit in audits if audit["classification"] == "SAFE_FOR_HUMAN_REVIEW")
    return {
        "queue_size": len(queue),
        "technically_blocked": blocked,
        "requires_pedagogical_judgement": pedagogical,
        "safe_for_human_review": safe,
        "items": audits,
    }


def evaluate_generated_candidate(
    generation_record: dict[str, Any],
    inventory_item: dict[str, Any],
) -> dict[str, Any] | None:
    """Turn one persisted generation record into a Wave-2 queue candidate."""
    attempt = next((item for item in generation_record["attempts"] if item.get("result") == "PASS"), None)
    if attempt is None:
        return None
    candidate = attempt["candidate"]
    target = candidate.get("target") or candidate.get("curriculum_target") or {}
    source = {
        "code": candidate["code"],
        "content_type": candidate["content_type"],
        "target": target,
        "answer": candidate["answer"],
        "provenance": candidate.get("provenance", {}),
    }
    from services.content.grade_appropriateness import apply_grade_assessment

    hard_gates_map = {
        "structural_validity": True,
        "answer_correctness": True,
        "skill_alignment": True,
        "grade_appropriateness": True,
        "executability": True,
        "duplicate_safety": True,
    }
    provisional = {
        **inventory_item,
        "content_type": candidate["content_type"],
        "chapter": str(target.get("chapter_code") or inventory_item.get("chapter", "")),
        "skill": str(target.get("primary_skill_code") or inventory_item.get("skill", "")),
        "skill_code": str(target.get("primary_skill_code") or inventory_item.get("skill", "")),
        "grade": str(target.get("grade_code") or inventory_item.get("grade", "")),
        "automated_checks": hard_gates_map,
        "difficulty": inventory_item.get("difficulty", 2),
    }
    graded = apply_grade_assessment(provisional)
    hard_gates_map["grade_appropriateness"] = bool(graded["automated_checks"]["grade_appropriateness"])
    from services.content.approval_acceleration import candidate_score

    result = {
        **inventory_item,
        "content_type": candidate["content_type"],
        "decision": "REVIEW",
        "hard_gates": hard_gates_map,
        "reasons": ["Independent pedagogical review is still required."],
    }
    score = candidate_score(
        result,
        source,
        decision="REVIEW",
        missing_coverage=True,
        near_duplicate=False,
    )
    hard_gates_passed = all(hard_gates_map[key] for key in hard_gates_map if key != "grade_appropriateness")
    if not is_usable_quality_record({"decision": "REVIEW", "hard_gates": hard_gates_map}):
        return None
    queue_record = build_queue_record(
        result,
        source,
        decision="REVIEW",
        score=score,
        hard_gates=hard_gates_passed,
        reasons=("Independent pedagogical review is still required.",),
        missing_coverage=True,
    )
    queue_record["answer_kind"] = str(source["answer"].get("kind", queue_record.get("answer_kind", "open_response")))
    queue_record["pipeline_version"] = PIPELINE_VERSION
    audit = classify_wave1_human_review(queue_record)
    if audit["classification"] == "TECHNICALLY_BLOCKED":
        return None
    return queue_record


def projected_tier1_after_lot(
    coverage_rows: list[dict[str, Any]],
    lot_skills: list[dict[str, Any]],
    queue: list[dict[str, Any]],
) -> dict[str, int]:
    """Estimate Tier-1 potential if every queued slot in the lot is approved."""
    baseline = sum(
        tier(int(row["approved_practice"]) > 0, int(row["approved_assessment"]) > 0) == 1 for row in coverage_rows
    )
    lot_skill_codes = {str(row["skill"]) for row in lot_skills}
    by_skill: dict[str, set[str]] = defaultdict(set)
    for item in queue:
        if str(item["skill"]) not in lot_skill_codes:
            continue
        by_skill[str(item["skill"])].add(str(item["target_slot"]))
    completable = sum(1 for slots in by_skill.values() if slots == set(PRODUCTION_SLOTS))
    return {
        "baseline_tier1": baseline,
        "lot_queue_size": len(queue),
        "lot_skills_with_both_slots_ready": completable,
        "tier1_potential_if_all_lot_approvals": baseline + completable,
    }


def load_lot_review_queues(
    quality_dir: Path,
    *,
    lots: tuple[int, ...] = (1, 2),
) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for lot_number in lots:
        path = quality_dir / f"lcai_0012d4_wave2_lot{lot_number}_review_queue.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            queue.extend(payload)
    return queue


def build_skill_review_bundles(
    queue: list[dict[str, Any]],
    review_statuses: dict[int, str],
) -> list[dict[str, Any]]:
    """Group Wave-2 queue items into one bundle per Skill."""
    by_skill: dict[str, dict[str, Any]] = {}
    for item in queue:
        skill = str(item["skill"])
        bundle = by_skill.setdefault(
            skill,
            {
                "skill": skill,
                "skill_name": item.get("skill_name", skill),
                "grade": item["grade"],
                "subject": item["subject"],
                "chapter": item["chapter"],
                "lot_numbers": set(),
                "practice": None,
                "assessment": None,
            },
        )
        bundle["lot_numbers"].add(int(item.get("lot_number", 0)))
        slot = str(item.get("target_slot") or item.get("content_type") or item.get("missing_slot"))
        bundle[slot] = item
        bundle[f"{slot}_status"] = review_statuses.get(int(item["version_id"]))

    bundles: list[dict[str, Any]] = []
    for bundle in by_skill.values():
        bundle["lot_numbers"] = sorted(number for number in bundle["lot_numbers"] if number > 0)
        bundles.append(bundle)
    return bundles


def prioritize_skill_bundles(
    bundles: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Order skills for fast human review."""
    from services.content.d4_review import confidence_band

    ratios = subject_tier1_ratios(coverage_rows)

    def bundle_priority(bundle: dict[str, Any]) -> tuple[Any, ...]:
        practice_band = confidence_band(bundle.get("practice"))
        assessment_band = confidence_band(bundle.get("assessment"))
        bands = {practice_band, assessment_band}
        if bands <= {"high"}:
            tier = 0
        elif "blocked" in bands or "missing" in bands:
            tier = 3
        elif bands <= {"high", "pedagogical"}:
            tier = 1
        else:
            tier = 2
        return (
            tier,
            ratios.get(str(bundle["subject"]), 1.0),
            1 if bundle["subject"] == "MATHEMATICS" else 0,
            str(bundle["grade"]),
            str(bundle["subject"]),
            str(bundle["skill"]),
        )

    return sorted(bundles, key=bundle_priority)


def summarize_wave2_review_bundles(bundles: list[dict[str, Any]]) -> dict[str, int]:
    from services.content.d4_review import confidence_band

    summary = {
        "skills": len(bundles),
        "practice_candidates": 0,
        "assessment_candidates": 0,
        "technically_blocked": 0,
        "high_confidence_dual": 0,
        "mixed_review": 0,
        "pedagogical_dual": 0,
    }
    for bundle in bundles:
        practice = bundle.get("practice")
        assessment = bundle.get("assessment")
        if practice is not None:
            summary["practice_candidates"] += 1
        if assessment is not None:
            summary["assessment_candidates"] += 1
        for item in (practice, assessment):
            if item is not None and confidence_band(item) == "blocked":
                summary["technically_blocked"] += 1
        practice_band = confidence_band(practice)
        assessment_band = confidence_band(assessment)
        if practice_band == "high" and assessment_band == "high":
            summary["high_confidence_dual"] += 1
        elif practice_band == "pedagogical" and assessment_band == "pedagogical":
            summary["pedagogical_dual"] += 1
        elif {practice_band, assessment_band} <= {"high", "pedagogical"}:
            summary["mixed_review"] += 1
    return summary


def _bundle_closed(bundle: dict[str, Any], review_statuses: dict[int, str]) -> bool:
    closed = {"APPROVED", "REJECTED", "KEEP_REVIEW"}
    practice = bundle.get("practice")
    assessment = bundle.get("assessment")
    if practice is None or assessment is None:
        return False
    return (
        review_statuses.get(int(practice["version_id"])) in closed
        and review_statuses.get(int(assessment["version_id"])) in closed
    )


def filter_skill_bundles(
    bundles: list[dict[str, Any]],
    *,
    lot_number: int | None = None,
    grade: str | None = None,
    subject: str | None = None,
    status: str = "pending",
    pedagogical_warning: bool | None = None,
    dual_ready: bool | None = None,
    ai_prevalidation: str | None = None,
    fact_check_required: bool | None = None,
    review_statuses: dict[int, str] | None = None,
) -> list[dict[str, Any]]:
    from services.content.d4_review import can_dual_approve, requires_pedagogical_attention

    review_statuses = review_statuses or {}
    filtered: list[dict[str, Any]] = []
    for bundle in bundles:
        if lot_number is not None and lot_number not in bundle.get("lot_numbers", []):
            continue
        if grade is not None and bundle["grade"] != grade:
            continue
        if subject is not None and bundle["subject"] != subject:
            continue
        practice = bundle.get("practice")
        assessment = bundle.get("assessment")
        practice_status = review_statuses.get(int(practice["version_id"])) if practice else None
        assessment_status = review_statuses.get(int(assessment["version_id"])) if assessment else None
        if status == "pending" and _bundle_closed(bundle, review_statuses):
            continue
        if status == "completed" and not _bundle_closed(bundle, review_statuses):
            continue
        if pedagogical_warning is True and not any(
            item is not None and requires_pedagogical_attention(item) for item in (practice, assessment)
        ):
            continue
        if dual_ready is True and not can_dual_approve(
            practice,
            assessment,
            reviewer="reviewer",
            approver="approver",
            practice_pedagogical_confirmation=True,
            assessment_pedagogical_confirmation=True,
            practice_status=practice_status,
            assessment_status=assessment_status,
        ):
            continue
        if ai_prevalidation and ai_prevalidation != "Tous":
            slot_decisions = [
                str(item.get("ai_prevalidation_decision", "")) for item in (practice, assessment) if item is not None
            ]
            if ai_prevalidation == "Prévalidé par IA" and not all(
                is_ai_prevalidated_decision(decision) for decision in slot_decisions
            ):
                continue
            if ai_prevalidation == "Prévalidé IA — confiance élevée" and not all(
                decision == "AI_PREVALIDATED_HIGH" for decision in slot_decisions
            ):
                continue
            if ai_prevalidation == "Prévalidé IA avec réserve" and not any(
                decision == "AI_PREVALIDATED_WITH_WARNING" for decision in slot_decisions
            ):
                continue
            if ai_prevalidation == "Revue enseignant requise" and not any(
                decision == "TEACHER_REVIEW_REQUIRED" for decision in slot_decisions
            ):
                continue
            if ai_prevalidation == "Rejeté par IA" and not any(
                decision == "AI_REJECTED" for decision in slot_decisions
            ):
                continue
            if ai_prevalidation == "File prévalidée rapide" and not (
                len(slot_decisions) == 2 and all(is_ai_prevalidated_decision(decision) for decision in slot_decisions)
            ):
                continue
        if fact_check_required is True and not any(
            bool(item.get("fact_check_required")) for item in (practice, assessment) if item is not None
        ):
            continue
        filtered.append(bundle)
    return filtered


__all__ = [
    "LOT_SIZE_DEFAULT",
    "PIPELINE_VERSION",
    "REVIEW_CAMPAIGN",
    "WAVE_BAND_TIER3",
    "audit_wave2_queue",
    "build_wave2_human_queue",
    "build_wave2_lot_plan",
    "evaluate_generated_candidate",
    "load_wave2_assigned_skills",
    "prepare_ranked_records",
    "projected_tier1_after_lot",
    "select_wave2_lot_skills",
]
