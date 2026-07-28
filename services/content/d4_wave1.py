"""LCAI-0012D4 Wave 1 — minimum best-candidate selection for Tier-1 coverage."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from services.content.approval_acceleration import (
    automatic_resolution_possible,
    candidate_score,
    classify_review,
)
from services.content.approval_coverage import coverage_impact, normalized_type, tier

PIPELINE_VERSION = "lcai-0012d4-wave1-v1"
REVIEW_CAMPAIGN = "LCAI-0012D4-WAVE1"
REVIEW_QUEUE_STATUS_ACTIVE = "ACTIVE"
WAVE_BAND_TIER2 = "TIER2_COMPLETION"
WAVE_BAND_G2 = "G2_EXISTING"
WAVE_BAND_FINAL = "FINAL_COMPLETION"
AUTHORIZED_WAVE_BANDS = frozenset({WAVE_BAND_TIER2, WAVE_BAND_G2, WAVE_BAND_FINAL})
AUTHORIZED_CANDIDATE_SOURCES = frozenset({"existing", "generated"})
PEDAGOGICAL_ATTENTION_THRESHOLD = 80
PEDAGOGICAL_WARNING_FR = "⚠ Ce contenu nécessite une attention pédagogique renforcée."

WAVE1_REVIEW_ITEM_REQUIRED_KEYS = (
    "version_id",
    "grade",
    "subject",
    "chapter",
    "skill_code",
    "target_slot",
    "candidate_score",
    "recommended_decision",
    "quality_result",
    "hard_gates_passed",
    "automated_checks",
    "quality_reason",
    "coverage_impact",
    "current_tier",
    "projected_tier",
    "alternate_count",
    "candidate_source",
    "review_campaign",
    "review_queue_status",
)


def wave1_rank_key(result: dict[str, Any], source: dict[str, Any], *, near_duplicate: bool) -> tuple[Any, ...]:
    """Rank Wave-1 candidates using the D4 priority stack (best first)."""
    gates = result["hard_gates"]
    hard_gates_passed = all(value for key, value in gates.items() if key != "grade_appropriateness")
    decision = str(result.get("_wave1_decision", result["decision"]))
    score = int(result.get("_wave1_score", 0))
    explanation_len = len(str(result.get("explanation", "")).strip())
    deterministic = source["answer"].get("independently_computed") is not None
    return (
        not hard_gates_passed,
        not gates.get("structural_validity", False),
        not deterministic,
        not gates.get("skill_alignment", False),
        not gates.get("answer_correctness", False),
        not gates.get("executability", False),
        not gates.get("duplicate_safety", False),
        not gates.get("grade_appropriateness", False),
        -explanation_len,
        {"PASS": 0, "REVIEW": 1, "REJECT": 2}.get(decision, 3),
        -score,
        str(result["code"]),
    )


def _slot_missing(coverage: dict[str, Any]) -> str | None:
    practice = int(coverage["approved_practice"]) > 0
    assessment = int(coverage["approved_assessment"]) > 0
    if practice and assessment:
        return None
    if practice:
        return "assessment"
    if assessment:
        return "practice"
    return None


def _best_exploitable(candidates: list[dict[str, Any]], slot: str) -> dict[str, Any] | None:
    eligible = [
        item
        for item in candidates
        if item["content_type"] == slot and item["recommended_decision"] == "APPROVE" and item["hard_gates_passed"]
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda item: int(item["candidate_score"]))


def classify_wave1_skills(coverage_rows: list[dict[str, Any]], queue_records: list[dict[str, Any]]) -> dict[str, str]:
    """Return wave band per skill: TIER2_COMPLETION, G2_EXISTING or empty if out of scope."""
    by_skill: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in queue_records:
        by_skill[str(record["skill"])].append(record)

    bands: dict[str, str] = {}
    for row in coverage_rows:
        skill = str(row["skill"])
        practice = int(row["approved_practice"]) > 0
        assessment = int(row["approved_assessment"]) > 0
        current = tier(practice, assessment)
        if current == 1:
            continue
        if current == 2:
            bands[skill] = WAVE_BAND_TIER2
            continue
        missing = _slot_missing(row)
        if missing is None:
            continue
        exploitable_slot = "assessment" if missing == "practice" else "practice"
        if _best_exploitable(by_skill.get(skill, []), exploitable_slot) is not None:
            bands[skill] = WAVE_BAND_G2
    return bands


def build_queue_record(
    result: dict[str, Any],
    source: dict[str, Any],
    *,
    decision: str,
    score: int,
    hard_gates: bool,
    reasons: tuple[str, ...] | list[str],
    missing_coverage: bool,
) -> dict[str, Any]:
    slot = normalized_type(str(result["content_type"]))
    return {
        "content_id": result["content_id"],
        "version_id": result["version_id"],
        "author": next(
            str(item)
            for item in (
                source.get("provenance", {}).get("generator_identifier"),
                "generated-content-author",
            )
            if item
        ),
        "code": result["code"],
        "grade": result["grade"],
        "subject": result["subject"],
        "chapter": result["chapter"],
        "skill": result["skill"],
        "skill_name": result.get("skill_name", result["skill"]),
        "content_type": slot,
        "missing_slot": slot,
        "difficulty": result["difficulty"],
        "question": result["prompt"],
        "choices": result.get("choices", []),
        "expected_answer": result["stored_answer"],
        "answer_kind": source["answer"]["kind"],
        "explanation": result["explanation"],
        "automated_checks": result["hard_gates"],
        "deterministic_verification": source["answer"].get("independently_computed"),
        "quality_result": decision,
        "quality_reason": list(reasons),
        "candidate_score": score,
        "hard_gates_passed": hard_gates,
        "missing_coverage": missing_coverage,
        "recommended_decision": (
            "APPROVE"
            if decision == "PASS" and hard_gates and score >= 80
            else "REJECT"
            if decision == "REJECT"
            else "KEEP_FOR_REVIEW"
        ),
        "pipeline_version": PIPELINE_VERSION,
        "original_lcai_0012d_decision": result["decision"],
        "d4_wave1_selected": False,
    }


def prepare_ranked_records(
    results: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    coverage: dict[str, dict[str, Any]],
    *,
    near_codes: set[str],
    resolved: set[str],
) -> dict[str, list[dict[str, Any]]]:
    """Build full ranked queue records keyed by (skill, slot)."""
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        skill = str(result["skill"])
        if skill not in coverage:
            continue
        source = sources[result["code"]]
        slot = normalized_type(str(result["content_type"]))
        if slot not in {"practice", "assessment"}:
            continue
        cov = coverage[skill]
        decision = "PASS" if result["code"] in resolved else str(result["decision"])
        review_reasons = classify_review(result, source, near_duplicate=result["code"] in near_codes)
        if decision == "REVIEW" and automatic_resolution_possible(result, source, review_reasons):
            decision = "PASS"
        hard_gates = all(value for key, value in result["hard_gates"].items() if key != "grade_appropriateness")
        missing_coverage = (slot == "practice" and int(cov["approved_practice"]) == 0) or (
            slot == "assessment" and int(cov["approved_assessment"]) == 0
        )
        score = candidate_score(
            result,
            source,
            decision=decision,
            missing_coverage=missing_coverage,
            near_duplicate=result["code"] in near_codes,
        )
        reasons = (
            ("Vérification mathématique indépendante validée.",)
            if result["code"] in resolved
            else tuple(str(item) for item in result.get("reasons", ()))
        )
        enriched = dict(result)
        enriched["_wave1_decision"] = decision
        enriched["_wave1_score"] = score
        record = build_queue_record(
            enriched,
            source,
            decision=decision,
            score=score,
            hard_gates=hard_gates,
            reasons=reasons,
            missing_coverage=missing_coverage,
        )
        grouped[(skill, slot)].append(record)

    output: dict[str, list[dict[str, Any]]] = {}
    for key, records in grouped.items():
        ranked = sorted(
            records,
            key=lambda item: wave1_rank_key(
                {
                    **item,
                    "prompt": item["question"],
                    "hard_gates": item["automated_checks"],
                    "decision": item["quality_result"],
                    "_wave1_decision": item["quality_result"],
                    "_wave1_score": item["candidate_score"],
                },
                sources[item["code"]],
                near_duplicate=False,
            ),
        )
        output[f"{key[0]}|{key[1]}"] = ranked
    return output


def build_wave1_targets(
    coverage_rows: list[dict[str, Any]],
    ranked_by_skill_slot: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Select one target per Tier-2 and G2 skill with ordered alternates."""
    targets: list[dict[str, Any]] = []
    for row in coverage_rows:
        skill = str(row["skill"])
        practice = int(row["approved_practice"]) > 0
        assessment = int(row["approved_assessment"]) > 0
        current = tier(practice, assessment)
        if current == 1:
            continue
        if current == 2:
            selected_slot = "practice" if not practice else "assessment"
            band = WAVE_BAND_TIER2
        else:
            selected_slot = None
            for slot in ("practice", "assessment"):
                slot_candidates = ranked_by_skill_slot.get(f"{skill}|{slot}", [])
                if any(
                    item["recommended_decision"] == "APPROVE" and item["hard_gates_passed"] for item in slot_candidates
                ):
                    selected_slot = slot
                    break
            if selected_slot is None:
                continue
            band = WAVE_BAND_G2
        candidates = ranked_by_skill_slot.get(f"{skill}|{selected_slot}", [])
        if not candidates:
            continue
        targets.append(
            {
                "skill": skill,
                "skill_name": row.get("skill_name", skill),
                "grade": row["grade"],
                "subject": row["subject"],
                "chapter": row["chapter"],
                "wave_band": band,
                "selected_slot": selected_slot,
                "missing_slot_label": "Entraînement" if selected_slot == "practice" else "Évaluation",
                "complement_slot": "assessment" if selected_slot == "practice" else "practice",
                "current_tier": current,
                "candidates": candidates,
            }
        )
    return targets


def active_candidate(
    target: dict[str, Any],
    review_statuses: dict[int, str],
    *,
    skipped: set[int] | None = None,
) -> dict[str, Any] | None:
    """Return the best pending candidate, skipping rejected or decided versions."""
    skipped = skipped or set()
    for candidate in target["candidates"]:
        version_id = int(candidate["version_id"])
        if version_id in skipped:
            continue
        status = review_statuses.get(version_id, "PENDING")
        if status in {"APPROVED", "REJECTED", "KEEP_REVIEW", "SKIPPED"}:
            continue
        return candidate
    return None


def build_active_wave1_queue(
    targets: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
    review_statuses: dict[int, str],
    *,
    skipped: set[int] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Materialize the Wave-1 review queue (max one candidate per skill)."""
    skipped = skipped or set()
    coverage_by_skill = {str(row["skill"]): row for row in coverage_rows}
    queue: list[dict[str, Any]] = []
    for target in targets:
        candidate = active_candidate(target, review_statuses, skipped=skipped)
        if candidate is None:
            continue
        item = dict(candidate)
        item["d4_wave1_selected"] = True
        item["wave_band"] = target["wave_band"]
        item["skill_name"] = target.get("skill_name", item["skill"])
        item["missing_slot"] = target["selected_slot"]
        item["missing_slot_label"] = target["missing_slot_label"]
        item["alternate_count"] = max(0, len(target["candidates"]) - 1)
        item["coverage_impact"] = coverage_impact(coverage_by_skill[str(item["skill"])], str(item["content_type"]))
        queue.append(item)

    queue = order_wave1_queue(queue)
    for rank, item in enumerate(queue, 1):
        item["wave1_rank"] = rank

    tier2_selected = sum(1 for item in queue if item["wave_band"] == WAVE_BAND_TIER2)
    g2_selected = sum(1 for item in queue if item["wave_band"] == WAVE_BAND_G2)
    summary = {
        "queue_size": len(queue),
        "tier2_selected": tier2_selected,
        "g2_selected": g2_selected,
        "projected_tier1_max": projected_tier1_totals(coverage_rows, targets),
    }
    return queue, summary


def order_wave1_queue(queue: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order Wave-1 queue: non-Math first, grade balance, Tier-1 impact, score."""
    tier2 = [item for item in queue if item["wave_band"] == WAVE_BAND_TIER2]
    g2 = [item for item in queue if item["wave_band"] == WAVE_BAND_G2]

    def band_sort(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items.sort(
            key=lambda item: (
                1 if item["subject"] == "MATHEMATICS" else 0,
                -int(item["candidate_score"]),
                str(item["skill"]),
            )
        )
        by_grade: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
        for item in items:
            by_grade[str(item["grade"])].append(item)
        ordered: list[dict[str, Any]] = []
        grades = sorted(by_grade)
        while any(by_grade.values()):
            for grade in grades:
                if by_grade[grade]:
                    ordered.append(by_grade[grade].popleft())
        return ordered

    return band_sort(tier2) + band_sort(g2)


def projected_tier1_totals(
    coverage_rows: list[dict[str, Any]],
    targets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Project Tier-1 totals for Wave-1 success metrics."""
    current = sum(
        tier(int(row["approved_practice"]) > 0, int(row["approved_assessment"]) > 0) == 1 for row in coverage_rows
    )
    tier2_skills = sum(1 for target in targets if target["wave_band"] == WAVE_BAND_TIER2)
    g2_skills = sum(1 for target in targets if target["wave_band"] == WAVE_BAND_G2)
    return {
        "baseline_tier1": current,
        "after_tier2_approvals": current + tier2_skills,
        "after_g2_existing_approvals": current + tier2_skills,
        "after_g2_complements": current + tier2_skills + g2_skills,
        "target_cap": 100,
    }


def coverage_snapshot(coverage_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize tier counts overall and by grade/subject."""
    tiers = {"tier1": 0, "tier2": 0, "tier3": 0}
    by_grade: dict[str, dict[str, int]] = defaultdict(lambda: {"tier1": 0, "tier2": 0, "tier3": 0})
    by_subject: dict[str, dict[str, int]] = defaultdict(lambda: {"tier1": 0, "tier2": 0, "tier3": 0})
    for row in coverage_rows:
        practice = int(row["approved_practice"]) > 0
        assessment = int(row["approved_assessment"]) > 0
        current = tier(practice, assessment)
        key = f"tier{current}"
        tiers[key] += 1
        by_grade[str(row["grade"])][key] += 1
        by_subject[str(row["subject"])][key] += 1
    return {
        "overall": dict(tiers),
        "by_grade": {grade: dict(values) for grade, values in sorted(by_grade.items())},
        "by_subject": {subject: dict(values) for subject, values in sorted(by_subject.items())},
    }


def g2_complement_plan(
    targets: list[dict[str, Any]],
    review_statuses: dict[int, str],
) -> list[dict[str, Any]]:
    """List G2 complements to generate only after the existing slot is approved."""
    plan: list[dict[str, Any]] = []
    for target in targets:
        if target["wave_band"] != WAVE_BAND_G2:
            continue
        approved_existing = any(
            review_statuses.get(int(candidate["version_id"])) == "APPROVED" for candidate in target["candidates"]
        )
        plan.append(
            {
                "skill": target["skill"],
                "skill_name": target.get("skill_name", target["skill"]),
                "grade": target["grade"],
                "subject": target["subject"],
                "chapter": target["chapter"],
                "generate_slot": target["complement_slot"],
                "ready_to_generate": approved_existing,
                "status": "READY" if approved_existing else "WAITING_FOR_EXISTING_APPROVAL",
            }
        )
    return plan


def is_authorized_wave1_review_candidate(item: dict[str, Any]) -> bool:
    """True when the item belongs to the active D4 Wave-1 human-review campaign."""
    if str(item.get("review_campaign")) != REVIEW_CAMPAIGN:
        return False
    if str(item.get("review_queue_status")) != REVIEW_QUEUE_STATUS_ACTIVE:
        return False
    if not item.get("version_id"):
        return False
    if str(item.get("wave_band", "")) not in AUTHORIZED_WAVE_BANDS:
        return False
    return str(item.get("candidate_source", "")) in AUTHORIZED_CANDIDATE_SOURCES


def eligible_for_explicit_pedagogical_confirmation(
    item: dict[str, Any],
    *,
    explicit_confirmation: bool,
) -> bool:
    """True when low-score approval is allowed via an authorized review campaign."""
    if not explicit_confirmation:
        return False
    if not is_authorized_wave1_review_candidate(item):
        return False
    if item.get("technically_blocked"):
        return False
    if str(item.get("recommended_decision")) == "REJECT":
        return False
    return bool(item.get("hard_gates_passed"))


def normalize_wave1_review_item(
    item: dict[str, Any],
    coverage_row: dict[str, Any],
    *,
    candidate_source: str = "existing",
    wave_band: str | None = None,
    alternate_count: int | None = None,
    projected_tier1_if_approved: int | None = None,
    wave1_rank: int | None = None,
) -> dict[str, Any]:
    """Ensure Wave-1 review items share one UI/approval schema."""
    normalized = dict(item)
    skill = str(coverage_row["skill"])
    practice = int(coverage_row["approved_practice"]) > 0
    missing_slot = str(
        normalized.get("missing_slot")
        or normalized.get("target_slot")
        or ("practice" if not practice else "assessment")
    )
    target_slot = normalized_type(missing_slot)
    if "coverage_impact" not in normalized:
        normalized["coverage_impact"] = coverage_impact(coverage_row, target_slot)

    impact = normalized["coverage_impact"]
    current = impact["current"]
    potential = impact["potential"]

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
    normalized["current_tier"] = int(current["tier"])
    normalized["projected_tier"] = int(potential["tier"])
    normalized["alternate_count"] = (
        int(alternate_count) if alternate_count is not None else int(normalized.get("alternate_count", 0))
    )
    normalized["candidate_source"] = candidate_source
    normalized["review_campaign"] = REVIEW_CAMPAIGN
    normalized["review_queue_status"] = REVIEW_QUEUE_STATUS_ACTIVE
    if wave_band is not None:
        normalized["wave_band"] = wave_band
    if projected_tier1_if_approved is not None:
        normalized["projected_tier1_if_approved"] = projected_tier1_if_approved
    if wave1_rank is not None:
        normalized["wave1_rank"] = wave1_rank
    return normalized


def normalize_wave1_review_queue(
    queue: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize every queue item using authoritative coverage rows."""
    coverage_by_skill = {str(row["skill"]): row for row in coverage_rows}
    normalized_queue: list[dict[str, Any]] = []
    for item in queue:
        skill = str(item.get("skill") or item.get("skill_code", ""))
        coverage_row = coverage_by_skill.get(skill)
        if coverage_row is None:
            raise KeyError(f"Missing coverage row for Wave-1 item skill={skill}")
        source = str(item.get("candidate_source", "existing"))
        normalized_queue.append(
            normalize_wave1_review_item(
                item,
                coverage_row,
                candidate_source=source,
                wave_band=str(item.get("wave_band")) if item.get("wave_band") else None,
                alternate_count=int(item.get("alternate_count", 0)),
                projected_tier1_if_approved=item.get("projected_tier1_if_approved"),
                wave1_rank=item.get("wave1_rank"),
            )
        )
    return normalized_queue


def assert_wave1_review_item_ready(item: dict[str, Any]) -> None:
    """Validate that a Wave-1 item can be rendered and approved by the UI."""
    missing = [key for key in WAVE1_REVIEW_ITEM_REQUIRED_KEYS if key not in item]
    if missing:
        raise AssertionError(f"Missing Wave-1 review fields: {', '.join(missing)}")
    impact = item["coverage_impact"]
    for key in ("current", "potential", "completes_tier_1", "improves_tier_2"):
        if key not in impact:
            raise AssertionError(f"Missing coverage_impact.{key}")


def append_final_generated_candidates(
    queue: list[dict[str, Any]],
    *,
    artifact_path: Path,
    review_statuses: dict[int, str],
    baseline_tier1: int,
    coverage_by_skill: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach corrective-generation candidates produced after Wave 1."""
    if not artifact_path.exists():
        return queue
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    audit = payload.get("audit", {})
    if audit.get("classification") == "TECHNICALLY_BLOCKED":
        return queue
    record = payload.get("queue_record")
    if not isinstance(record, dict):
        return queue
    version_id = int(record["version_id"])
    if review_statuses.get(version_id) == "APPROVED":
        return queue
    if any(int(item["version_id"]) == version_id for item in queue):
        return queue
    skill = str(record["skill"])
    coverage_row = coverage_by_skill[skill]
    item = normalize_wave1_review_item(
        record,
        coverage_row,
        candidate_source="generated",
        wave_band=WAVE_BAND_FINAL,
        alternate_count=0,
        projected_tier1_if_approved=baseline_tier1 + len(queue) + 1,
        wave1_rank=len(queue) + 1,
    )
    queue.append(item)
    return queue


def build_wave1_final_human_queue(
    coverage_rows: list[dict[str, Any]],
    ranked_by_skill_slot: dict[str, list[dict[str, Any]]],
    review_statuses: dict[int, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build the post-Wave-1 final queue for remaining Tier-2 completions."""
    baseline_tier1 = sum(
        tier(int(row["approved_practice"]) > 0, int(row["approved_assessment"]) > 0) == 1 for row in coverage_rows
    )
    queue: list[dict[str, Any]] = []
    for row in coverage_rows:
        practice = int(row["approved_practice"]) > 0
        assessment = int(row["approved_assessment"]) > 0
        if tier(practice, assessment) != 2:
            continue
        skill = str(row["skill"])
        missing_slot = "practice" if not practice else "assessment"
        candidates = ranked_by_skill_slot.get(f"{skill}|{missing_slot}", [])
        selected: dict[str, Any] | None = None
        for candidate in candidates:
            version_id = int(candidate["version_id"])
            if review_statuses.get(version_id) == "APPROVED":
                continue
            if candidate["recommended_decision"] == "REJECT":
                continue
            if not candidate["hard_gates_passed"]:
                continue
            selected = dict(candidate)
            break
        if selected is None:
            continue
        selected = normalize_wave1_review_item(
            selected,
            row,
            candidate_source="existing",
            wave_band=WAVE_BAND_FINAL,
            alternate_count=max(0, len(candidates) - 1),
            projected_tier1_if_approved=baseline_tier1 + len(queue) + 1,
            wave1_rank=len(queue) + 1,
        )
        queue.append(selected)
    summary = {
        "queue_size": len(queue),
        "baseline_tier1": baseline_tier1,
        "projected_tier1_if_all_approved": baseline_tier1 + len(queue),
    }
    return queue, summary


def requires_pedagogical_attention(item: dict[str, Any]) -> bool:
    """True when automated confidence is below the standard approval threshold."""
    return (
        int(item.get("candidate_score", 0)) < PEDAGOGICAL_ATTENTION_THRESHOLD
        or str(item.get("recommended_decision")) != "APPROVE"
    )


def pedagogical_attention_reason(item: dict[str, Any]) -> str:
    """French explanation for reduced automated confidence."""
    reasons: list[str] = []
    score = int(item.get("candidate_score", 0))
    if score < PEDAGOGICAL_ATTENTION_THRESHOLD:
        reasons.append(f"Score qualité {score}/100 (< {PEDAGOGICAL_ATTENTION_THRESHOLD}).")
    if str(item.get("recommended_decision")) != "APPROVE":
        reasons.append(f"Recommandation automatique : {item.get('recommended_decision')}.")
    for reason in item.get("quality_reason", ()):
        text = str(reason).strip()
        if text:
            reasons.append(text)
    gates = item.get("automated_checks", {})
    if gates.get("grade_appropriateness") is False:
        reasons.append("Pertinence du niveau scolaire non confirmée automatiquement.")
    return " ".join(reasons)


def classify_wave1_human_review(item: dict[str, Any]) -> dict[str, Any]:
    """Classify one Wave-1 candidate for human review safety."""
    gates = item.get("automated_checks", {})
    score = int(item.get("candidate_score", 0))
    recommendation = str(item.get("recommended_decision", ""))
    quality = str(item.get("quality_result", ""))
    answer_kind = str(item.get("answer_kind", ""))
    blockers: list[str] = []

    if not gates.get("structural_validity", False):
        blockers.append("Validité structurelle non confirmée.")
    if not gates.get("answer_correctness", False):
        blockers.append("Exactitude de la réponse non confirmée.")
    if not gates.get("skill_alignment", False):
        blockers.append("Alignement curriculaire ou compétence invalide.")
    if not gates.get("executability", False):
        blockers.append("Exercice non exécutable.")
    if recommendation == "REJECT" or quality == "REJECT":
        blockers.append("Rejet automatique.")
    if answer_kind in {"single_choice", "multiple_choice"}:
        choices = list(item.get("choices") or [])
        if not choices:
            blockers.append("Intégrité QCM invalide (choix manquants).")
        elif answer_kind == "single_choice" and str(item.get("expected_answer", "")) not in choices:
            blockers.append("Réponse attendue absente des choix QCM.")
    if (
        answer_kind in {"numeric", "math_expression"}
        and item.get("deterministic_verification") is None
        and not gates.get("answer_correctness", False)
    ):
        blockers.append("Vérification déterministe échouée ou absente.")

    if blockers:
        classification = "TECHNICALLY_BLOCKED"
        safety = " ; ".join(blockers)
    elif score >= PEDAGOGICAL_ATTENTION_THRESHOLD and recommendation == "APPROVE" and item.get("hard_gates_passed"):
        classification = "SAFE_FOR_HUMAN_REVIEW"
        safety = "Score élevé, recommandation APPROVE, barrières dures validées."
    else:
        classification = "REQUIRES_PEDAGOGICAL_JUDGEMENT"
        safety = pedagogical_attention_reason(item)

    return {
        "version_id": int(item["version_id"]),
        "grade": item.get("grade"),
        "subject": item.get("subject"),
        "skill": item.get("skill"),
        "content_type": item.get("content_type"),
        "quality_status": quality,
        "quality_score": score,
        "hard_gates": gates,
        "keep_for_review_reason": list(item.get("quality_reason", ())),
        "deterministic_verification": item.get("deterministic_verification"),
        "recommended_decision": recommendation,
        "score_gte_80": score >= PEDAGOGICAL_ATTENTION_THRESHOLD,
        "classification": classification,
        "human_approval_safe_because": safety,
    }


def audit_wave1_queue(queue: list[dict[str, Any]]) -> dict[str, Any]:
    """Audit the active Wave-1 queue for human review readiness."""
    entries = [classify_wave1_human_review(item) for item in queue]
    counts = {
        "SAFE_FOR_HUMAN_REVIEW": 0,
        "REQUIRES_PEDAGOGICAL_JUDGEMENT": 0,
        "TECHNICALLY_BLOCKED": 0,
    }
    score_buckets = {">=90": 0, "80-89": 0, "70-79": 0, "60-69": 0, "<60": 0}
    quality_status: dict[str, int] = defaultdict(int)
    by_grade: dict[str, int] = defaultdict(int)
    by_subject: dict[str, int] = defaultdict(int)
    by_type: dict[str, int] = defaultdict(int)

    for item, entry in zip(queue, entries, strict=True):
        counts[entry["classification"]] += 1
        score = int(entry["quality_score"])
        if score >= 90:
            score_buckets[">=90"] += 1
        elif score >= 80:
            score_buckets["80-89"] += 1
        elif score >= 70:
            score_buckets["70-79"] += 1
        elif score >= 60:
            score_buckets["60-69"] += 1
        else:
            score_buckets["<60"] += 1
        quality_status[str(entry["quality_status"])] += 1
        by_grade[str(item.get("grade", ""))] += 1
        by_subject[str(item.get("subject", ""))] += 1
        by_type[str(item.get("content_type", ""))] += 1

    skills = [str(item["skill"]) for item in queue]
    return {
        "queue_size": len(queue),
        "unique_skills": len(set(skills)),
        "duplicate_skills": len(skills) - len(set(skills)),
        "classifications": counts,
        "score_distribution": dict(score_buckets),
        "quality_status_distribution": dict(quality_status),
        "by_grade": dict(by_grade),
        "by_subject": dict(by_subject),
        "by_content_type": dict(by_type),
        "entries": entries,
    }
