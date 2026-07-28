"""LCAI-0012E primary handoff adapter and post-AI analysis."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from services.content.ai_pedagogical_review import deduplicate_candidates
from services.content.ai_review_calibration import is_ai_prevalidated_decision
from services.content.primary_integration import load_prepared_candidates

CAMPAIGN_ID = "LCAI-0012E-PRIMARY"
HANDOFF_PATH = Path("resources/content/integration/lcai_0012e_ai_review_handoff.jsonl")
AUTHORITATIVE_AUDIT_PATH = Path("resources/content/quality/lcai_0012e_ai_pedagogical_review_authoritative.jsonl")
CALIBRATED_AUDIT_PATH = Path("resources/content/quality/lcai_0012e_ai_pedagogical_review_calibrated.jsonl")
SUMMARY_PATH = Path("resources/content/quality/lcai_0012e_ai_pedagogical_review_summary.json")
COMBINED_PATH = Path("resources/content/integration/lcai_0012e_ai_review_combined.json")
TEACHER_QUEUE_PATH = Path("resources/content/quality/lcai_0012e_teacher_review_queue.json")
ALTERNATE_QUEUE_PATH = Path("resources/content/quality/lcai_0012e_alternate_review_queue.json")
QUALITY_RESULTS_PATH = Path("resources/content/quality/lcai_0012e_quality_results.json")
CURRICULUM_RESOLUTION_PATH = Path("resources/content/integration/lcai_0012e_5e_curriculum_resolution_v1.json")
CURRICULUM_APPENDIX_PATH = Path("docs/phase2/LCAI-0012E_UNRESOLVED_CURRICULUM_APPENDIX.md")

PRIMARY_GRADES = frozenset({"FR-CM1", "FR-CM2", "FR-6E", "FR-5E"})

_CURRICULUM_RECOMMENDATIONS: dict[str, str] = {
    "WRITING-PLAN": "ADD_CURRICULUM_SKILL",
    "SOCIETY-CITIES": "MAP_EXISTING",
    "MATTER-CHANGE": "MAP_EXISTING",
    "PLANET-DATA": "MAP_EXISTING",
    "PLANET-PHENOMENON": "MAP_EXISTING",
    "CULTURE-COMPARE": "ADD_CURRICULUM_SKILL",
}


def load_handoff_rows(path: Path | None = None) -> list[dict[str, Any]]:
    source = path or HANDOFF_PATH
    rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        if row.get("grade") not in PRIMARY_GRADES:
            raise ValueError(f"Out-of-scope grade in handoff: {row.get('grade')}")
    return rows


def handoff_to_review_item(row: dict[str, Any]) -> dict[str, Any]:
    gates = dict((row.get("quality_metadata") or {}).get("hard_gates") or {})
    slot = str(row.get("content_type", ""))
    if slot == "guided_practice":
        slot = "practice"
    return {
        "version_id": int(row["candidate_version_id"]),
        "campaign_id": str(row.get("campaign_id", CAMPAIGN_ID)),
        "grade": str(row["grade"]),
        "subject": str(row["subject"]),
        "chapter": str(row["chapter"]),
        "skill_code": str(row["skill_code"]),
        "skill": str(row["skill_code"]),
        "content_type": slot,
        "target_slot": slot,
        "question": str(row["question"]),
        "choices": list(row.get("choices") or []),
        "expected_answer": row.get("expected_answer"),
        "explanation": str(row.get("explanation", "")),
        "answer_kind": str(row.get("answer_kind", "open_response")),
        "hard_gates_passed": all(bool(v) for v in gates.values()) if gates else True,
        "automated_checks": gates,
        "candidate_score": int(float((row.get("quality_metadata") or {}).get("confidence", 0.6)) * 100),
        "recommended_decision": str((row.get("quality_metadata") or {}).get("decision", "REVIEW")),
        "quality_metadata": row.get("quality_metadata"),
    }


def load_handoff_candidates(path: Path | None = None) -> list[dict[str, Any]]:
    return deduplicate_candidates([handoff_to_review_item(row) for row in load_handoff_rows(path)])


def load_quality_index_by_code(path: Path | None = None) -> dict[str, dict[str, Any]]:
    source = path or QUALITY_RESULTS_PATH
    if not source.exists():
        return {}
    rows = json.loads(source.read_text(encoding="utf-8"))
    return {str(row["code"]): row for row in rows}


def prepared_record_to_review_item(
    record: dict[str, Any],
    *,
    quality: dict[str, Any] | None = None,
    rejected_from_version_id: int | None = None,
) -> dict[str, Any]:
    """Convert a prepared corpus record into a calibrated review item."""
    candidate_data = record["candidate_data"]
    answer = candidate_data.get("answer", {})
    target = candidate_data.get("target", {})
    quality = quality or {}
    gates = dict(quality.get("hard_gates") or {})
    slot = str(record.get("content_type", ""))
    if slot == "guided_practice":
        slot = "practice"
    version_id = int(
        quality.get("version_id")
        or candidate_data.get("version_id")
        or record.get("version_id")
        or 0
    )
    item = {
        "version_id": version_id,
        "code": str(record["code"]),
        "campaign_id": CAMPAIGN_ID,
        "grade": str(record.get("grade") or target.get("grade_code")),
        "subject": str(record.get("subject") or target.get("subject_code")),
        "chapter": str(record.get("chapter") or target.get("chapter_code")),
        "skill_code": str(record.get("skill") or target.get("primary_skill_code")),
        "skill": str(record.get("skill") or target.get("primary_skill_code")),
        "content_type": slot,
        "target_slot": slot,
        "question": str(candidate_data.get("prompt", "")),
        "choices": list(answer.get("options", [])),
        "expected_answer": answer.get("expected"),
        "explanation": str(candidate_data.get("explanation", "")),
        "answer_kind": str(record.get("answer_kind", answer.get("kind", "open_response"))),
        "hard_gates_passed": all(bool(v) for v in gates.values()) if gates else True,
        "automated_checks": gates,
        "candidate_score": int(float(quality.get("confidence", 0.6)) * 100),
        "recommended_decision": str(quality.get("decision", "REVIEW")),
        "quality_metadata": {
            "decision": quality.get("decision", "REVIEW"),
            "confidence": quality.get("confidence", 0.6),
            "hard_gates": gates,
            "reasons": quality.get("reasons", []),
        },
        "is_alternate_review": rejected_from_version_id is not None,
    }
    if rejected_from_version_id is not None:
        item["rejected_from_version_id"] = int(rejected_from_version_id)
        item["alternate_lineage"] = {
            "rejected_version_id": int(rejected_from_version_id),
            "alternate_code": str(record["code"]),
        }
    return item


def validate_handoff_population(path: Path | None = None) -> dict[str, Any]:
    rows = load_handoff_rows(path)
    items = load_handoff_candidates(path)
    by_grade = Counter(row["grade"] for row in rows)
    by_subject = Counter(row["subject"] for row in rows)
    required = {
        "candidate_version_id",
        "grade",
        "subject",
        "chapter",
        "skill_code",
        "content_type",
        "question",
        "expected_answer",
        "explanation",
    }
    missing_fields = [idx for idx, row in enumerate(rows) if required - set(row)]
    return {
        "expected": 731,
        "handoff_rows": len(rows),
        "deduplicated_candidates": len(items),
        "unique_version_ids": len({row["candidate_version_id"] for row in rows}),
        "by_grade": dict(by_grade),
        "by_subject": dict(by_subject),
        "missing_required_fields": missing_fields,
        "valid": len(rows) == 731 and len(items) == 731 and not missing_fields,
    }


def build_primary_skill_bundles(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in candidates:
        key = (str(item["grade"]), str(item["skill_code"]))
        bundle = grouped.setdefault(
            key,
            {
                "grade": item["grade"],
                "subject": item["subject"],
                "skill_code": item["skill_code"],
                "chapter": item["chapter"],
                "practice": None,
                "assessment": None,
            },
        )
        slot = str(item.get("target_slot") or item["content_type"])
        if slot == "guided_practice":
            slot = "practice"
        if slot not in {"practice", "assessment"}:
            continue
        current = bundle.get(slot)
        if current is None or int(item.get("candidate_score", 0)) > int(current.get("candidate_score", 0)):
            bundle[slot] = item
    return list(grouped.values())


def classify_skill_pair(bundle: dict[str, Any]) -> str:
    practice = bundle.get("practice")
    assessment = bundle.get("assessment")
    if practice is None or assessment is None:
        return "ONLY_ONE_SLOT_AVAILABLE"
    pd = (practice or {}).get("ai_prevalidation_decision")
    ad = (assessment or {}).get("ai_prevalidation_decision")
    if pd == "AI_REJECTED" or ad == "AI_REJECTED":
        return "BLOCKED_BY_REJECTION"
    p_pre = is_ai_prevalidated_decision(str(pd) if pd else None)
    a_pre = is_ai_prevalidated_decision(str(ad) if ad else None)
    p_teacher = pd == "TEACHER_REVIEW_REQUIRED"
    a_teacher = ad == "TEACHER_REVIEW_REQUIRED"
    if p_pre and a_pre:
        return "BOTH_AI_PREVALIDATED"
    if (p_pre and a_teacher) or (a_pre and p_teacher):
        return "ONE_AI_ONE_TEACHER"
    if p_teacher and a_teacher:
        return "BOTH_TEACHER"
    return "ONE_AI_ONE_TEACHER"


def skill_pair_metrics(bundles: list[dict[str, Any]]) -> dict[str, Any]:
    overall = Counter(classify_skill_pair(bundle) for bundle in bundles)
    by_grade: dict[str, Counter[str]] = defaultdict(Counter)
    by_subject: dict[str, Counter[str]] = defaultdict(Counter)
    by_content_type: dict[str, Counter[str]] = defaultdict(Counter)
    for bundle in bundles:
        state = classify_skill_pair(bundle)
        by_grade[str(bundle["grade"])][state] += 1
        by_subject[str(bundle["subject"])][state] += 1
        for slot in ("practice", "assessment"):
            item = bundle.get(slot)
            if item is None:
                continue
            slot_type = str(item.get("target_slot") or item.get("content_type") or slot)
            by_content_type[slot_type][state] += 1
    return {
        "overall": dict(overall),
        "by_grade": {grade: dict(counter) for grade, counter in sorted(by_grade.items())},
        "by_subject": {subject: dict(counter) for subject, counter in sorted(by_subject.items())},
        "by_content_type": {ctype: dict(counter) for ctype, counter in sorted(by_content_type.items())},
    }


def _prepared_alternates_index() -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    records, _ = load_prepared_candidates()
    index: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record.get("grade") not in PRIMARY_GRADES:
            continue
        skill = str(record.get("skill") or record["candidate_data"]["target"]["primary_skill_code"])
        slot = str(record.get("content_type", ""))
        if slot == "guided_practice":
            slot = "practice"
        code = str(record["code"])
        index[(skill, slot, str(record["grade"]))].append({"code": code, "record": record})
    return index


def find_alternate_for_rejected(
    item: dict[str, Any],
    *,
    excluded_codes: set[str],
    reviewed_version_ids: set[int],
) -> dict[str, Any] | None:
    """Search prepared corpus for alternate same skill/slot not yet reviewed."""
    index = _prepared_alternates_index()
    quality_index = load_quality_index_by_code()
    skill = str(item.get("skill_code") or item["skill"])
    slot = str(item.get("target_slot") or item["content_type"])
    grade = str(item["grade"])
    rejected_code = str(item.get("code", ""))
    for alt in index.get((skill, slot, grade), []):
        code = alt["code"]
        if code in excluded_codes or code == rejected_code:
            continue
        rec = alt["record"]
        quality = quality_index.get(code, {})
        vid = int(quality.get("version_id") or rec["candidate_data"].get("version_id") or rec.get("version_id") or 0)
        if vid > 0 and vid in reviewed_version_ids:
            continue
        return {"code": code, "record": rec, "quality": quality, "version_id": vid}
    return None


def build_alternate_review_queue(
    enriched: list[dict[str, Any]],
    *,
    reviewed_version_ids: set[int],
) -> tuple[list[dict[str, Any]], int, int]:
    """Identify alternates for rejected candidates and build review queue."""
    quality_index = load_quality_index_by_code()
    queue: list[dict[str, Any]] = []
    alternates_found = 0
    replacement_required = 0
    reviewed_codes: set[str] = set()
    for item in enriched:
        if item.get("ai_prevalidation_decision") != "AI_REJECTED":
            continue
        alt = find_alternate_for_rejected(
            item,
            excluded_codes=reviewed_codes,
            reviewed_version_ids=reviewed_version_ids,
        )
        if alt is None:
            item["replacement_required"] = True
            replacement_required += 1
            continue
        alternates_found += 1
        reviewed_codes.add(str(alt["code"]))
        record = alt["record"]
        quality = alt.get("quality") or quality_index.get(str(alt["code"]), {})
        review_item = prepared_record_to_review_item(
            record,
            quality=quality,
            rejected_from_version_id=int(item["version_id"]),
        )
        if review_item["version_id"] <= 0:
            review_item["version_id"] = int(quality.get("version_id") or 0)
        item["alternate_queued"] = str(alt["code"])
        item["alternate_version_id"] = review_item["version_id"]
        queue.append(review_item)
    return queue, alternates_found, replacement_required


def compute_post_ai_generation_gap(
    bundles: list[dict[str, Any]],
    *,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Recompute generation need after AI review — pedagogically usable slots only."""
    missing_practice = 0
    missing_assessment = 0
    replacement_required = 0
    rejected_without_alternate = 0
    teacher_blocked_practice = 0
    teacher_blocked_assessment = 0
    fact_check_blocked = 0
    by_grade: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for bundle in bundles:
        grade = str(bundle["grade"])
        practice = bundle.get("practice") or {}
        assessment = bundle.get("assessment") or {}
        p_dec = str(practice.get("ai_prevalidation_decision") or "")
        a_dec = str(assessment.get("ai_prevalidation_decision") or "")
        p_ok = is_ai_prevalidated_decision(p_dec)
        a_ok = is_ai_prevalidated_decision(a_dec)
        p_reject = p_dec == "AI_REJECTED"
        a_reject = a_dec == "AI_REJECTED"
        p_teacher = p_dec == "TEACHER_REVIEW_REQUIRED"
        a_teacher = a_dec == "TEACHER_REVIEW_REQUIRED"

        if practice.get("fact_check_required"):
            fact_check_blocked += 1
            by_grade[grade]["fact_check_blocked"] += 1
        if assessment.get("fact_check_required"):
            fact_check_blocked += 1
            by_grade[grade]["fact_check_blocked"] += 1

        if p_reject:
            if practice.get("replacement_required"):
                rejected_without_alternate += 1
                replacement_required += 1
                by_grade[grade]["replacement_required"] += 1
            elif not is_ai_prevalidated_decision(p_dec):
                replacement_required += 1
                by_grade[grade]["replacement_required"] += 1
        elif p_teacher and practice:
            teacher_blocked_practice += 1
            by_grade[grade]["teacher_blocked_practice"] += 1
        elif not p_ok and practice:
            missing_practice += 1
            by_grade[grade]["missing_practice"] += 1
        elif practice is None:
            missing_practice += 1
            by_grade[grade]["missing_practice"] += 1

        if a_reject:
            if assessment.get("replacement_required"):
                rejected_without_alternate += 1
                replacement_required += 1
                by_grade[grade]["replacement_required"] += 1
            elif not is_ai_prevalidated_decision(a_dec):
                replacement_required += 1
                by_grade[grade]["replacement_required"] += 1
        elif a_teacher and assessment:
            teacher_blocked_assessment += 1
            by_grade[grade]["teacher_blocked_assessment"] += 1
        elif not a_ok and assessment:
            missing_assessment += 1
            by_grade[grade]["missing_assessment"] += 1
        elif assessment is None:
            missing_assessment += 1
            by_grade[grade]["missing_assessment"] += 1

    genuinely_absent = missing_practice + missing_assessment
    total = genuinely_absent + replacement_required
    pre_ai_path = Path("resources/content/quality/lcai_0012e_slot_coverage.json")
    pre_ai = {}
    if pre_ai_path.exists():
        pre_ai = json.loads(pre_ai_path.read_text(encoding="utf-8")).get("generation_requirements", {})
    return {
        "missing_practice_after_ai": missing_practice,
        "missing_assessment_after_ai": missing_assessment,
        "rejected_without_alternate": rejected_without_alternate,
        "teacher_blocked_practice": teacher_blocked_practice,
        "teacher_blocked_assessment": teacher_blocked_assessment,
        "teacher_blocked_slots": teacher_blocked_practice + teacher_blocked_assessment,
        "fact_check_blocked_slots": fact_check_blocked,
        "replacement_required": replacement_required,
        "genuinely_absent_content": genuinely_absent,
        "total_generation_required": total,
        "by_grade": {grade: dict(values) for grade, values in sorted(by_grade.items())},
        "pre_ai_slot_gap": pre_ai,
        "categories": {
            "A_genuinely_absent": genuinely_absent,
            "B_rejected_needing_replacement": replacement_required,
            "C_awaiting_human_or_fact_check": (
                teacher_blocked_practice + teacher_blocked_assessment + fact_check_blocked
            ),
        },
    }


def _conceptual_group_key(skill_code: str) -> str:
    for key in _CURRICULUM_RECOMMENDATIONS:
        if key in skill_code.upper():
            return key
    return skill_code.rsplit("-", 1)[-1]


def build_curriculum_decision_appendix(path: Path | None = None) -> dict[str, Any]:
    source = path or CURRICULUM_RESOLUTION_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    groups: list[dict[str, Any]] = []
    for item in payload.get("group_analyses", []):
        skill = str(item["original_primary_skill_code"])
        group_key = _conceptual_group_key(skill)
        groups.append(
            {
                "conceptual_group": group_key,
                "grade": item["grade"],
                "subject": item["subject"],
                "original_skill_code": skill,
                "candidate_count": int(item.get("record_count", 0)),
                "intended_learning_objective": item.get("sample_prompt", "")[:160],
                "closest_v2_skills": list(item.get("candidate_matches") or []),
                "reason_unsafe_mapping": item.get("reason", ""),
                "recommendation": _CURRICULUM_RECOMMENDATIONS.get(group_key, "CURRICULUM_DECISION"),
            }
        )
    return {
        "total_excluded": 18,
        "curriculum_decision_records": 15,
        "spanish_compare_records": 3,
        "groups": groups,
    }


def write_curriculum_decision_appendix(path: Path | None = None) -> Path:
    appendix = build_curriculum_decision_appendix()
    target = path or CURRICULUM_APPENDIX_PATH
    lines = [
        "# LCAI-0012E — Unresolved Curriculum Decision Appendix",
        "",
        "These 18 records are excluded from AI review statistics.",
        "",
        f"- Curriculum-decision records: {appendix['curriculum_decision_records']}",
        f"- Spanish COMPARE (out-of-curriculum): {appendix['spanish_compare_records']}",
        "",
    ]
    for group in appendix["groups"]:
        lines.extend(
            [
                f"## {group['conceptual_group']}",
                "",
                f"- Grade: {group['grade']}",
                f"- Subject: {group['subject']}",
                f"- Original skill: `{group['original_skill_code']}`",
                f"- Candidate count: {group['candidate_count']}",
                f"- Intended objective: {group['intended_learning_objective']}",
                f"- Closest V2 skill(s): {', '.join(f'`{s}`' for s in group['closest_v2_skills'][:4])}",
                f"- Unsafe mapping reason: {group['reason_unsafe_mapping']}",
                f"- **Recommendation: {group['recommendation']}**",
                "",
            ]
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def build_teacher_queue(enriched: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from services.content.ai_review_calibration import analyze_escalation_reasons

    queue: list[dict[str, Any]] = []
    for item in enriched:
        decision = item.get("ai_prevalidation_decision")
        if decision != "TEACHER_REVIEW_REQUIRED" and not item.get("fact_check_required"):
            continue
        audit = item.get("ai_pedagogical_review") or {}
        analysis = analyze_escalation_reasons(
            item=item,
            audit=audit,
            original_decision=str(decision or "TEACHER_REVIEW_REQUIRED"),
        )
        queue.append(
            {
                "version_id": item["version_id"],
                "grade": item["grade"],
                "subject": item["subject"],
                "skill_code": item.get("skill_code"),
                "content_type": item.get("target_slot") or item.get("content_type"),
                "decision": decision,
                "fact_check_required": bool(item.get("fact_check_required")),
                "teacher_reason": analysis.concise_reason,
                "escalation_categories": list(analysis.all_reasons),
            }
        )
    return queue
