"""LCAI-0012E — CM1/CM2/6e/5e prepared-content integration primitives."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from domain.content.factory import (
    AnswerKind,
    AnswerSpecification,
    CanonicalContentType,
    CurriculumTarget,
    GeneratedContentCandidate,
    GenerationProvenance,
    PedagogicalIntent,
    normalized_content_fingerprint,
)
from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository
from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from services.content.approval_acceleration import (
    automatic_resolution_possible,
    candidate_score,
    classify_review,
)
from services.content.approval_coverage import coverage_impact, tier
from services.content.expansion import (
    ContentSlot,
    build_slot_quality_index,
    coverage_gaps,
    generation_gaps,
    required_slots,
    slot_has_usable_candidate,
    slot_index_key,
)
from services.content.quality import AuditDecision, GateResult, promotion_eligible, qcm_issues, structural_issues

PRIMARY_GRADES = ("FR-CM1", "FR-CM2", "FR-6E", "FR-5E")
GRADE_DIRS = {
    "FR-CM1": "cm1",
    "FR-CM2": "cm2",
    "FR-6E": "6e",
    "FR-5E": "5e",
}
IMPORT_AUTHOR = "lcai-0012e-primary-import"
REVIEW_CAMPAIGN = "LCAI-0012E-PRIMARY"
PIPELINE_VERSION = "lcai-0012e-primary-v1"
INTEGRATION_INVENTORY = Path("resources/content/integration/lcai_0012e_preintegration_inventory_v1.json")


def discover_candidate_files(root: Path | None = None) -> list[Path]:
    base = root or Path("resources/content")
    files: list[Path] = []
    for grade_dir in GRADE_DIRS.values():
        files.extend(sorted((base / grade_dir).glob("lcai_*_candidates_v1.json")))
    return files


def load_integration_statuses() -> dict[str, dict[str, Any]]:
    if not INTEGRATION_INVENTORY.exists():
        return {}
    payload = json.loads(INTEGRATION_INVENTORY.read_text(encoding="utf-8"))
    items = payload.get("candidate_inventory") or payload.get("candidates") or []
    return {str(item["code"]): item for item in items}


def candidate_from_record(data: dict[str, Any]) -> GeneratedContentCandidate:
    answer = data["answer"]
    kind = AnswerKind(answer["kind"])
    computed = answer.get("independently_computed") if kind is AnswerKind.NUMERIC else None
    target = data["target"]
    provenance = data["provenance"]
    return GeneratedContentCandidate(
        code=data["code"],
        title=data["title"],
        instructions=data["instructions"],
        prompt=data["prompt"],
        answer=AnswerSpecification(
            kind,
            answer["expected"],
            tuple(answer.get("options", ())),
            answer.get("tolerance"),
            computed,
        ),
        explanation=data["explanation"],
        target=CurriculumTarget(
            target["program_code"],
            target["grade_code"],
            target["subject_code"],
            target["chapter_code"],
            target["primary_skill_code"],
            target.get("subskill_code"),
            tuple(target.get("secondary_skill_codes", ())),
        ),
        content_type=CanonicalContentType(data["content_type"]),
        pedagogical_intent=PedagogicalIntent(data["pedagogical_intent"]),
        difficulty=int(data["difficulty"]),
        provenance=GenerationProvenance(
            provenance["generator_type"],
            provenance["generator_identifier"],
            provenance["specification_version"],
            provenance["template_version"],
            provenance["curriculum_version"],
            datetime.fromisoformat(provenance["generated_at"]),
            provenance.get("latency_ms"),
            provenance.get("usage", {}),
        ),
        hints=tuple(data.get("hints", ())),
        feedback=data.get("feedback", {}),
        family_code=data.get("family_code"),
        variant_role=data.get("variant_role"),
        misconception_target=data.get("misconception_target"),
        language_code=data.get("language_code", "fr-FR"),
        metadata=data.get("metadata", {}),
    )


def load_prepared_candidates(root: Path | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load accepted candidates from grade JSON packs with source traceability."""
    records: list[dict[str, Any]] = []
    by_file: dict[str, int] = {}
    for path in discover_candidate_files(root):
        payload = json.loads(path.read_text(encoding="utf-8"))
        count = 0
        for item in payload.get("accepted_candidates", []):
            candidate_data = dict(item["candidate_data"])
            candidate_data["source_ticket"] = "LCAI-0012E"
            candidate_data["source_file"] = path.name
            records.append(
                {
                    "code": str(item["code"]),
                    "grade": str(item.get("grade") or payload.get("grade_code")),
                    "subject": str(item.get("subject") or payload.get("subject_code")),
                    "chapter": str(item["chapter"]),
                    "skill": str(item["skill"]),
                    "content_type": str(item["content_type"]),
                    "difficulty": int(item["difficulty"]),
                    "answer_kind": str(item.get("answer_kind", candidate_data["answer"]["kind"])),
                    "source_file": path.name,
                    "candidate_data": candidate_data,
                }
            )
            count += 1
        by_file[path.name] = count
    meta = {
        "files": len(by_file),
        "candidates": len(records),
        "by_file": by_file,
        "unique_codes": len({item["code"] for item in records}),
    }
    return records, meta


def _existing_exercise_codes(database_path: Path | None) -> set[str]:
    connection = connect_v2(database_path, read_only=True)
    try:
        rows = connection.execute("SELECT code FROM exercises").fetchall()
    finally:
        connection.close()
    return {str(row[0]) for row in rows}


def load_valid_curriculum_keys(database_path: Path | None = None) -> set[tuple[str, str, str, str, str]]:
    """Load authoritative curriculum placement keys in one query."""
    connection = connect_v2(database_path, read_only=True)
    try:
        rows = connection.execute(
            """
            SELECT p.code, sl.code, su.code, cc.stable_code, s.code
            FROM curriculum_skill_details csd
            JOIN curriculum_chapters cc ON cc.id=csd.chapter_id
            JOIN programs p ON p.id=cc.program_id
            JOIN school_levels sl ON sl.id=cc.grade_level_id
            JOIN subjects su ON su.id=cc.subject_id
            JOIN skills s ON s.id=csd.skill_id
            WHERE csd.status='approved' AND cc.status='approved'
              AND sl.code IN (SELECT unnest(?))
            """,
            [list(PRIMARY_GRADES)],
        ).fetchall()
    finally:
        connection.close()
    return {(str(r[0]), str(r[1]), str(r[2]), str(r[3]), str(r[4])) for r in rows}


def validate_target_key(
    target: CurriculumTarget,
    valid_keys: set[tuple[str, str, str, str, str]],
) -> tuple[str, ...]:
    key = (
        target.program_code,
        target.grade_code,
        target.subject_code,
        target.chapter_code,
        target.primary_skill_code,
    )
    if key not in valid_keys:
        return ("Unknown or inconsistent Program/Grade/Subject/Chapter/Skill target",)
    return ()


def audit_prepared_resources(
    repository: DuckDBContentFactoryRepository,
    records: list[dict[str, Any]],
    *,
    integration_statuses: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Phase 1 — validate prepared JSON against authoritative V2 curriculum."""
    integration_statuses = integration_statuses or load_integration_statuses()
    valid_keys = load_valid_curriculum_keys(repository.database_path)
    codes: dict[str, list[str]] = defaultdict(list)
    malformed: list[dict[str, Any]] = []
    curriculum_errors: list[dict[str, Any]] = []
    missing_skills: Counter[str] = Counter()
    by_grade: dict[str, Counter[str]] = {grade: Counter() for grade in PRIMARY_GRADES}
    by_subject: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    content_types: Counter[str] = Counter()
    answer_kinds: Counter[str] = Counter()

    for record in records:
        code = record["code"]
        codes[code].append(record["source_file"] if "source_file" in record else "unknown")
        grade = record["grade"]
        subject = record["subject"]
        by_grade.setdefault(grade, Counter())
        by_grade[grade]["candidates"] += 1
        by_subject[(grade, subject)]["candidates"] += 1
        content_types[record["content_type"]] += 1
        answer_kinds[record["answer_kind"]] += 1

        try:
            candidate = candidate_from_record(record["candidate_data"])
        except (KeyError, TypeError, ValueError) as exc:
            malformed.append({"code": code, "error": str(exc)})
            continue

        errors = validate_target_key(candidate.target, valid_keys)
        if errors:
            curriculum_errors.append({"code": code, "errors": list(errors)})
            missing_skills[candidate.target.primary_skill_code] += 1

    duplicate_codes = {code: files for code, files in codes.items() if len(files) > 1}
    skills_by_grade: dict[str, set[str]] = defaultdict(set)
    for record in records:
        skills_by_grade[record["grade"]].add(record["skill"])

    inventory_mismatches: list[dict[str, Any]] = []
    for code, status in integration_statuses.items():
        matching = [item for item in records if item["code"] == code]
        if not matching and status.get("integration_status") != "BLOCKED":
            inventory_mismatches.append({"code": code, "issue": "missing_from_json"})
        elif matching and status.get("integration_status") == "BLOCKED":
            inventory_mismatches.append({"code": code, "issue": "blocked_still_in_json"})

    return {
        "pipeline_version": PIPELINE_VERSION,
        "grades": list(PRIMARY_GRADES),
        "candidate_count": len(records),
        "unique_codes": len(codes),
        "duplicate_codes": duplicate_codes,
        "malformed_records": malformed,
        "curriculum_mapping_errors": curriculum_errors,
        "inventory_mismatches": inventory_mismatches,
        "skills_by_grade": {grade: len(values) for grade, values in skills_by_grade.items()},
        "content_types": dict(content_types),
        "answer_kinds": dict(answer_kinds),
        "by_grade": {grade: dict(counter) for grade, counter in by_grade.items()},
        "by_subject": {
            f"{grade}|{subject}": dict(counter) for (grade, subject), counter in sorted(by_subject.items())
        },
        "curriculum_valid": not curriculum_errors and not malformed,
    }


def audit_prepared_quality_estimates(
    records: list[dict[str, Any]],
    *,
    integration_statuses: dict[str, dict[str, Any]] | None = None,
    valid_keys: set[tuple[str, str, str, str, str]] | None = None,
) -> dict[str, Any]:
    """Estimate PASS/REVIEW/REJECT from prepared JSON before or without DB import."""
    integration_statuses = integration_statuses or load_integration_statuses()
    decisions: Counter[str] = Counter()
    details: list[dict[str, Any]] = []
    prompts: dict[str, list[str]] = defaultdict(list)

    for record in records:
        code = record["code"]
        status = integration_statuses.get(code, {}).get("integration_status", "IMPORT_WITH_REVIEW")
        if status == "BLOCKED":
            decisions["REJECT"] += 1
            details.append({"code": code, "decision": "REJECT", "reason": "blocked_preintegration"})
            continue
        try:
            candidate = candidate_from_record(record["candidate_data"])
        except (KeyError, TypeError, ValueError):
            decisions["REJECT"] += 1
            details.append({"code": code, "decision": "REJECT", "reason": "malformed"})
            continue
        if valid_keys is not None and validate_target_key(candidate.target, valid_keys):
            decisions["CORRECTION_REQUIRED"] += 1
            details.append({"code": code, "decision": "CORRECTION_REQUIRED", "reason": "invalid_curriculum_mapping"})
            continue
        prompts[str(record["candidate_data"]["prompt"])].append(code)
        answer = record["candidate_data"]["answer"]
        qcm_issues_list: tuple[str, ...] = ()
        if answer["kind"] in {"single_choice", "multiple_choice"}:
            qcm_issues_list = qcm_issues(record["candidate_data"], None)
        if qcm_issues_list:
            decisions["REJECT"] += 1
            details.append({"code": code, "decision": "REJECT", "reason": "qcm_structure"})
            continue
        if status == "READY_TO_IMPORT_DRAFT":
            decisions["PASS"] += 1
            details.append({"code": code, "decision": "PASS", "reason": "ready_to_import"})
        else:
            decisions["REVIEW"] += 1
            details.append({"code": code, "decision": "REVIEW", "reason": "import_with_review"})

    duplicate_blocked = {code for codes in prompts.values() if len(codes) > 1 for code in codes}
    if duplicate_blocked:
        for code in duplicate_blocked:
            decisions["PASS"] -= sum(1 for item in details if item["code"] == code and item["decision"] == "PASS")
            decisions["REVIEW"] -= sum(1 for item in details if item["code"] == code and item["decision"] == "REVIEW")
            decisions["REJECT"] += 1
            for item in details:
                if item["code"] == code:
                    item["decision"] = "REJECT"
                    item["reason"] = "duplicate_prompt"

    return {"decisions": dict(decisions), "details_count": len(details)}


def import_prepared_candidates(
    repository: DuckDBContentFactoryRepository,
    records: list[dict[str, Any]],
    *,
    integration_statuses: dict[str, dict[str, Any]] | None = None,
    include_review: bool = True,
) -> dict[str, Any]:
    """Phase 3 — deterministic, idempotent Draft import."""
    integration_statuses = integration_statuses or load_integration_statuses()
    valid_keys = load_valid_curriculum_keys(repository.database_path)
    existing_codes = _existing_exercise_codes(repository.database_path)
    trace: list[dict[str, Any]] = []
    counters = Counter(
        imported=0,
        skipped_existing=0,
        skipped_blocked=0,
        skipped_invalid=0,
        failed=0,
    )

    for record in records:
        code = record["code"]
        status = integration_statuses.get(code, {}).get("integration_status", "IMPORT_WITH_REVIEW")
        if status == "BLOCKED":
            answer = record["candidate_data"].get("answer", {})
            if answer.get("kind") in {"single_choice", "multiple_choice"}:
                issues = [issue for issue in qcm_issues(record["candidate_data"], None) if issue != "choices_not_persisted"]
                if issues:
                    counters["skipped_blocked"] += 1
                    trace.append({"code": code, "result": "SKIPPED_BLOCKED", "status": status})
                    continue
            else:
                counters["skipped_blocked"] += 1
                trace.append({"code": code, "result": "SKIPPED_BLOCKED", "status": status})
                continue
        if status == "IMPORT_WITH_REVIEW" and not include_review:
            counters["skipped_blocked"] += 1
            trace.append({"code": code, "result": "SKIPPED_REVIEW_ONLY", "status": status})
            continue
        if code in existing_codes:
            counters["skipped_existing"] += 1
            trace.append({"code": code, "result": "SKIPPED_EXISTING"})
            continue
        try:
            candidate = candidate_from_record(record["candidate_data"])
            errors = validate_target_key(candidate.target, valid_keys)
            if errors:
                counters["skipped_invalid"] += 1
                trace.append({"code": code, "result": "SKIPPED_INVALID", "errors": list(errors)})
                continue
            repository.persist_draft(candidate, IMPORT_AUTHOR)
            existing_codes.add(code)
            counters["imported"] += 1
            trace.append({"code": code, "result": "PERSISTED_DRAFT", "status": status})
        except Exception as exc:  # noqa: BLE001 — import trace must capture all failures
            counters["failed"] += 1
            trace.append({"code": code, "result": "FAILED", "error": str(exc)})

    return {
        "pipeline_version": PIPELINE_VERSION,
        "author": IMPORT_AUTHOR,
        "counters": dict(counters),
        "trace": trace,
    }


def _duplicate_audit(
    items: list[dict[str, Any]],
    candidates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    exact: dict[str, list[str]] = defaultdict(list)
    normalized: dict[str, list[str]] = defaultdict(list)
    by_skill: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        exact[item["prompt"]].append(item["code"])
        normalized[normalized_content_fingerprint(item["prompt"])].append(item["code"])
        by_skill[item["skill"]].append(item)
    exact_groups = [codes for codes in exact.values() if len(codes) > 1]
    normalized_groups = [codes for codes in normalized.values() if len(codes) > 1]
    near: list[dict[str, Any]] = []
    for skill_items in by_skill.values():
        for index, left in enumerate(skill_items):
            left_text = normalized_content_fingerprint(left["prompt"])
            for right in skill_items[index + 1 :]:
                right_text = normalized_content_fingerprint(right["prompt"])
                if left_text == right_text:
                    continue
                similarity = SequenceMatcher(None, left_text, right_text).ratio()
                if similarity < 0.88:
                    continue
                left_candidate = candidates[left["code"]]
                right_candidate = candidates[right["code"]]
                intentional = bool(
                    left_candidate.get("family_code")
                    and left_candidate.get("family_code") == right_candidate.get("family_code")
                    and left_candidate.get("variant_role") != right_candidate.get("variant_role")
                )
                near.append(
                    {
                        "left": left["code"],
                        "right": right["code"],
                        "similarity": round(similarity, 4),
                        "decision": "KEEP" if intentional else "REVIEW",
                    }
                )
    return {
        "exact_groups": exact_groups,
        "normalized_groups": normalized_groups,
        "near_groups": near,
        "blocking_codes": sorted({code for group in exact_groups + normalized_groups for code in group}),
    }


def audit_draft_quality(
    quality_repository: DuckDBContentQualityRepository,
    factory_repository: DuckDBContentFactoryRepository,
    candidates: dict[str, dict[str, Any]],
    *,
    apply_qcm: bool = False,
) -> dict[str, Any]:
    """Phase 4 — run LCAI-0012D hard gates on imported primary-grade Drafts."""
    inventory = quality_repository.draft_inventory(grade_codes=PRIMARY_GRADES)
    qcm_results: list[dict[str, Any]] = []
    for item in inventory:
        candidate = candidates.get(item["code"])
        if candidate is None:
            continue
        if candidate["answer"]["kind"] not in {"single_choice", "multiple_choice"}:
            continue
        if apply_qcm:
            try:
                quality_repository.persist_qcm_execution_payload(item, candidate)
            except ValueError:
                # Expected label not aligned with options — leave unpersisted for qcm_issues().
                pass
        persisted = quality_repository.qcm_execution_payload(item["content_id"])
        issues = qcm_issues(candidate, persisted)
        qcm_results.append(
            {
                "code": item["code"],
                "content_id": item["content_id"],
                "kind": candidate["answer"]["kind"],
                "choices": len(candidate["answer"].get("options", [])),
                "issues": issues,
                "production_ready": not issues,
            }
        )

    duplicates = _duplicate_audit(inventory, candidates)
    duplicate_blocked = set(duplicates["blocking_codes"])
    qcm_by_code = {item["code"]: item for item in qcm_results}
    results: list[dict[str, Any]] = []

    for item in inventory:
        candidate = candidates.get(item["code"])
        structure = structural_issues(item, candidate)
        qcm = qcm_by_code.get(item["code"])
        answer_kind = str((candidate or {}).get("answer", {}).get("kind", "unknown"))
        decision = AuditDecision.REVIEW
        confidence = 0.6
        reasons: list[str] = ["Independent pedagogical review is still required."]
        if structure or (qcm and qcm["issues"]) or item["code"] in duplicate_blocked:
            decision = AuditDecision.REJECT
            confidence = 1.0
            reasons.extend(structure)
            if qcm:
                reasons.extend(qcm["issues"])
        independently_computed = (candidate or {}).get("answer", {}).get("independently_computed")
        answer_correct = independently_computed is not None or answer_kind in {
            "single_choice",
            "multiple_choice",
            "boolean",
        }
        if not answer_correct and answer_kind in {"exact_text", "numeric"}:
            answer_correct = independently_computed is not None
        gates = GateResult(
            structural_validity=not structure,
            answer_correctness=answer_correct,
            skill_alignment=not any("skill" in issue for issue in structure),
            grade_appropriateness=True,
            executability=not (qcm and qcm["issues"]),
            duplicate_safety=item["code"] not in duplicate_blocked,
        )
        if gates.passed and answer_kind in {"single_choice", "multiple_choice", "exact_text", "numeric", "boolean"}:
            review_reasons = classify_review(
                {
                    "subject": item["subject"],
                    "prompt": item["prompt"],
                    "explanation": item["explanation"],
                    "hard_gates": {
                        "structural_validity": gates.structural_validity,
                        "answer_correctness": gates.answer_correctness,
                        "skill_alignment": gates.skill_alignment,
                        "grade_appropriateness": gates.grade_appropriateness,
                        "executability": gates.executability,
                        "duplicate_safety": gates.duplicate_safety,
                    },
                },
                candidate or {"answer": {"kind": answer_kind}},
            )
            if automatic_resolution_possible(
                {
                    "decision": decision.value,
                    "subject": item["subject"],
                    "hard_gates": {
                        "structural_validity": gates.structural_validity,
                        "answer_correctness": gates.answer_correctness,
                        "skill_alignment": gates.skill_alignment,
                        "executability": gates.executability,
                        "duplicate_safety": gates.duplicate_safety,
                    },
                },
                candidate or {"answer": {"kind": answer_kind}},
                review_reasons,
            ):
                decision = AuditDecision.PASS
                confidence = 0.85
                reasons = ["Automated hard gates and deterministic verification passed."]
        eligible = promotion_eligible(decision, confidence, gates)
        results.append(
            {
                "content_id": item["content_id"],
                "version_id": item["version_id"],
                "code": item["code"],
                "grade": item["grade"],
                "subject": item["subject"],
                "chapter": item["chapter"],
                "skill": item["skill"],
                "difficulty": item["difficulty"],
                "prompt": item["prompt"],
                "explanation": item["explanation"],
                "content_type": (candidate or {}).get("content_type"),
                "answer_kind": answer_kind,
                "structural_pass": not structure,
                "structural_issues": structure,
                "hard_gates": {
                    "structural_validity": gates.structural_validity,
                    "answer_correctness": gates.answer_correctness,
                    "skill_alignment": gates.skill_alignment,
                    "grade_appropriateness": gates.grade_appropriateness,
                    "executability": gates.executability,
                    "duplicate_safety": gates.duplicate_safety,
                },
                "decision": decision.value,
                "confidence": confidence,
                "reasons": reasons,
                "approval_candidate": eligible,
            }
        )

    decisions = Counter(item["decision"] for item in results)
    return {
        "pipeline_version": PIPELINE_VERSION,
        "inventory_count": len(inventory),
        "results": results,
        "decisions": dict(decisions),
        "qcm": qcm_results,
        "duplicates": duplicates,
    }


def _coverage_rows(factory_repository: DuckDBContentFactoryRepository) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in factory_repository.active_skill_coverage(grade_codes=PRIMARY_GRADES):
        practice = sum(
            count for slot, count in row.approved.items() if slot.content_type.value in {"practice", "guided_practice"}
        )
        assessment = sum(count for slot, count in row.approved.items() if slot.content_type.value == "assessment")
        draft_practice = sum(
            count
            for slot, count in row.draft.items()
            if slot.content_type.value in {"practice", "guided_practice"}
        )
        draft_assessment = sum(
            count for slot, count in row.draft.items() if slot.content_type.value == "assessment"
        )
        output.append(
            {
                "grade": row.target.grade_code,
                "subject": row.target.subject_code,
                "chapter": row.target.chapter_code,
                "skill": row.target.primary_skill_code,
                "skill_name": row.skill_label,
                "approved_practice": practice,
                "approved_assessment": assessment,
                "draft_practice": draft_practice,
                "draft_assessment": draft_assessment,
            }
        )
    return output


def compute_gap_analysis(
    factory_repository: DuckDBContentFactoryRepository,
    quality_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Phase 5 — skills / practice / assessment gaps per grade and subject."""
    coverage_rows = factory_repository.active_skill_coverage(grade_codes=PRIMARY_GRADES)
    quality_index = build_slot_quality_index(quality_results)
    by_grade: dict[str, dict[str, Any]] = {}
    by_subject: dict[str, dict[str, Any]] = {}

    for grade in PRIMARY_GRADES:
        grade_rows = [row for row in coverage_rows if row.target.grade_code == grade]
        total_skills = len(grade_rows)
        practice_gaps = 0
        assessment_gaps = 0
        usable_practice = 0
        usable_assessment = 0
        generation_required = 0
        for skill in grade_rows:
            practice_slot = ContentSlot(CanonicalContentType.PRACTICE, 2)
            assessment_slot = ContentSlot(CanonicalContentType.ASSESSMENT, 2)
            has_practice = skill.count(practice_slot) > 0
            has_assessment = skill.count(assessment_slot) > 0
            if not has_practice:
                practice_gaps += 1
            if not has_assessment:
                assessment_gaps += 1
            practice_usable = slot_has_usable_candidate(skill, practice_slot, quality_index)
            assessment_usable = slot_has_usable_candidate(skill, assessment_slot, quality_index)
            if practice_usable:
                usable_practice += 1
            if assessment_usable:
                usable_assessment += 1
            for slot in (practice_slot, assessment_slot):
                if not slot_has_usable_candidate(skill, slot, quality_index):
                    generation_required += 1
        by_grade[grade] = {
            "skills": total_skills,
            "practice_gaps": practice_gaps,
            "assessment_gaps": assessment_gaps,
            "usable_practice_slots": usable_practice,
            "usable_assessment_slots": usable_assessment,
            "generation_required_slots": generation_required,
        }

    subjects_seen: set[tuple[str, str]] = set()
    for row in coverage_rows:
        subjects_seen.add((row.target.grade_code, row.target.subject_code))
    for grade, subject in sorted(subjects_seen):
        subject_rows = [
            row for row in coverage_rows if row.target.grade_code == grade and row.target.subject_code == subject
        ]
        practice_gaps = sum(
            1
            for row in subject_rows
            if row.count(ContentSlot(CanonicalContentType.PRACTICE, 2)) == 0
        )
        assessment_gaps = sum(
            1
            for row in subject_rows
            if row.count(ContentSlot(CanonicalContentType.ASSESSMENT, 2)) == 0
        )
        generation_required = sum(
            1
            for row in subject_rows
            for slot in (ContentSlot(CanonicalContentType.PRACTICE, 2), ContentSlot(CanonicalContentType.ASSESSMENT, 2))
            if not slot_has_usable_candidate(row, slot, quality_index)
        )
        key = f"{grade}|{subject}"
        by_subject[key] = {
            "skills": len(subject_rows),
            "practice_gaps": practice_gaps,
            "assessment_gaps": assessment_gaps,
            "generation_required_slots": generation_required,
        }

    raw_gaps = coverage_gaps(coverage_rows)
    gen_gaps = generation_gaps(coverage_rows, quality_index)
    return {
        "pipeline_version": PIPELINE_VERSION,
        "by_grade": by_grade,
        "by_subject": by_subject,
        "coverage_gaps_total": len(raw_gaps),
        "generation_gaps_total": len(gen_gaps),
        "generation_gaps_sample": [
            {
                "grade": gap.skill.target.grade_code,
                "subject": gap.skill.target.subject_code,
                "skill": gap.skill.target.primary_skill_code,
                "content_type": gap.slot.content_type.value,
                "difficulty": gap.slot.difficulty,
            }
            for gap in gen_gaps[:20]
        ],
    }


def _rank_key(result: dict[str, Any], source: dict[str, Any]) -> tuple[Any, ...]:
    gates = result["hard_gates"]
    hard_gates_passed = all(gates.values())
    decision = str(result["decision"])
    score = int(result.get("_score", 0))
    deterministic = source.get("answer", {}).get("independently_computed") is not None
    return (
        not hard_gates_passed,
        not gates.get("structural_validity", False),
        not deterministic,
        not gates.get("skill_alignment", False),
        not gates.get("answer_correctness", False),
        not gates.get("executability", False),
        not gates.get("duplicate_safety", False),
        {"PASS": 0, "REVIEW": 1, "REJECT": 2}.get(decision, 3),
        -score,
        str(result["code"]),
    )


def build_primary_review_queue(
    quality_results: list[dict[str, Any]],
    candidates: dict[str, dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Phase 6 — one best candidate per skill/slot, French-first review strategy."""
    near_codes = set()
    coverage = {str(row["skill"]): row for row in coverage_rows}
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for result in quality_results:
        if result["decision"] == "REJECT":
            continue
        skill = str(result["skill"])
        slot = str(result.get("content_type", ""))
        if slot not in {"practice", "assessment", "guided_practice"}:
            continue
        if slot == "guided_practice":
            slot = "practice"
        cov = coverage.get(skill, {})
        missing_coverage = (slot == "practice" and int(cov.get("approved_practice", 0)) == 0) or (
            slot == "assessment" and int(cov.get("approved_assessment", 0)) == 0
        )
        source = candidates[result["code"]]
        review_reasons = classify_review(result, source, near_duplicate=result["code"] in near_codes)
        decision = str(result["decision"])
        if decision == "REVIEW" and automatic_resolution_possible(result, source, review_reasons):
            decision = "PASS"
        hard_gates = all(result["hard_gates"].values())
        score = candidate_score(
            result,
            source,
            decision=decision,
            missing_coverage=missing_coverage,
            near_duplicate=result["code"] in near_codes,
        )
        enriched = dict(result)
        enriched["_score"] = score
        grouped[(skill, slot)].append(
            {
                "version_id": result["version_id"],
                "code": result["code"],
                "grade": result["grade"],
                "subject": result["subject"],
                "chapter": result["chapter"],
                "skill_code": skill,
                "skill_name": cov.get("skill_name", skill),
                "target_slot": slot,
                "content_type": slot,
                "candidate_score": score,
                "recommended_decision": "APPROVE" if decision == "PASS" else "REVIEW",
                "quality_result": decision,
                "hard_gates_passed": hard_gates,
                "automated_checks": result["hard_gates"],
                "quality_reason": "; ".join(result.get("reasons", [])),
                "coverage_impact": coverage_impact(cov, slot) if cov else {},
                "current_tier": tier(int(cov.get("approved_practice", 0)) > 0, int(cov.get("approved_assessment", 0)) > 0),
                "review_campaign": REVIEW_CAMPAIGN,
                "review_queue_status": "ACTIVE",
            }
        )

    targets: list[dict[str, Any]] = []
    for (skill, slot), records in grouped.items():
        ranked = sorted(
            records,
            key=lambda item: _rank_key(
                {
                    **item,
                    "code": item["code"],
                    "decision": item["quality_result"],
                    "hard_gates": item["automated_checks"],
                },
                candidates[item["code"]],
            ),
        )
        if not ranked:
            continue
        best = ranked[0]
        cov = coverage.get(skill, {})
        targets.append(
            {
                "skill": skill,
                "skill_name": cov.get("skill_name", skill),
                "grade": best["grade"],
                "subject": best["subject"],
                "chapter": best["chapter"],
                "selected_slot": slot,
                "missing_slot_label": "Entraînement" if slot == "practice" else "Évaluation",
                "current_tier": best["current_tier"],
                "active_candidate": best,
                "alternate_count": max(0, len(ranked) - 1),
                "alternates": ranked[1:5],
            }
        )

    def _queue_order(item: dict[str, Any]) -> tuple[Any, ...]:
        subject_priority = 0 if item["subject"] != "MATHEMATICS" else 1
        tier_priority = {3: 0, 2: 1, 1: 2}.get(int(item["current_tier"]), 3)
        return (tier_priority, subject_priority, item["grade"], item["subject"], item["skill"])

    queue = sorted(targets, key=_queue_order)
    for rank, item in enumerate(queue, 1):
        item["review_rank"] = rank

    return {
        "pipeline_version": PIPELINE_VERSION,
        "review_campaign": REVIEW_CAMPAIGN,
        "queue_size": len(queue),
        "total_alternates": sum(item["alternate_count"] for item in queue),
        "queue": queue,
        "policy": {
            "reviewer_approver_distinct": True,
            "automatic_approval": False,
            "production_enabled": False,
            "ui_language": "fr-FR",
            "one_candidate_per_skill_slot": True,
        },
    }


def candidate_sources_from_records(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(record["code"]): record["candidate_data"] for record in records}
