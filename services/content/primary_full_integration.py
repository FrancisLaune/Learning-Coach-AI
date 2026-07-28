"""LCAI-0012E full isolated import, QC, coverage and AI-review handoff."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from domain.content.factory import CanonicalContentType
from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository
from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from services.content.expansion import ContentSlot
from services.content.primary_integration import (
    PRIMARY_GRADES,
    audit_draft_quality,
    audit_prepared_resources,
    build_primary_review_queue,
    candidate_from_record,
    candidate_sources_from_records,
    import_prepared_candidates,
    load_integration_statuses,
    load_prepared_candidates,
    load_valid_curriculum_keys,
    validate_target_key,
)
from services.content.primary_skill_correction import apply_skill_corrections, repair_qcm_duplicate_choices
from services.content.quality import qcm_issues

FULL_ISOLATED_DB = Path("data/learning_coach_v2_0012e_full_test.duckdb")
AI_HANDOFF_CAMPAIGN = "LCAI-0012E-PRIMARY"
PRACTICE_SLOT = ContentSlot(CanonicalContentType.PRACTICE, 2)
ASSESSMENT_SLOT = ContentSlot(CanonicalContentType.ASSESSMENT, 2)


def prepare_corrected_records(
    *,
    database_path: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records, _ = load_prepared_candidates()
    corrected, correction_report = apply_skill_corrections(records, database_path=database_path)
    qcm_repairs: list[dict[str, Any]] = []
    output: list[dict[str, Any]] = []
    for record in corrected:
        item = dict(record)
        repair = repair_qcm_duplicate_choices(item["candidate_data"])
        if repair["changed"]:
            item["candidate_data"] = repair["candidate_data"]
        qcm_repairs.append({"code": record["code"], "status": repair["status"], "changed": repair["changed"]})
        output.append(item)
    validation = audit_prepared_resources(
        DuckDBContentFactoryRepository(database_path),
        output,
        integration_statuses=load_integration_statuses(),
    )
    return output, {
        "skill_corrections": correction_report,
        "qcm_repairs": qcm_repairs,
        "validation": {
            "curriculum_valid": validation["curriculum_valid"],
            "curriculum_mapping_errors": len(validation["curriculum_mapping_errors"]),
            "malformed_records": len(validation["malformed_records"]),
        },
    }


def filter_importable_records(records: list[dict[str, Any]], *, database_path: Path | None = None) -> list[dict[str, Any]]:
    valid_keys = load_valid_curriculum_keys(database_path)
    statuses = load_integration_statuses()
    importable: list[dict[str, Any]] = []
    for record in records:
        status = statuses.get(record["code"], {}).get("integration_status")
        if status == "BLOCKED":
            answer = record["candidate_data"].get("answer", {})
            if answer.get("kind") in {"single_choice", "multiple_choice"}:
                issues = [issue for issue in qcm_issues(record["candidate_data"], None) if issue != "choices_not_persisted"]
                if issues:
                    continue
        candidate = candidate_from_record(record["candidate_data"])
        if validate_target_key(candidate.target, valid_keys):
            continue
        importable.append(record)
    return importable


def compute_skill_slot_coverage(
    quality_results: list[dict[str, Any]],
    *,
    database_path: Path | None = None,
    usable_decisions: frozenset[str] = frozenset({"PASS", "REVIEW"}),
) -> dict[str, Any]:
    """Per-skill slot coverage with explicit non-double-counted generation formula."""
    factory = DuckDBContentFactoryRepository(database_path)
    rows = factory.active_skill_coverage(grade_codes=PRIMARY_GRADES)
    quality_by_skill: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: {"practice": [], "assessment": []})

    for result in quality_results:
        if result["decision"] not in usable_decisions:
            continue
        slot = str(result.get("content_type", ""))
        if slot == "guided_practice":
            slot = "practice"
        if slot in {"practice", "assessment"}:
            quality_by_skill[str(result["skill"])][slot].append(result)

    skill_states: list[dict[str, Any]] = []
    missing_both = 0
    missing_practice_only = 0
    missing_assessment_only = 0

    def _best(slot: str, skill: str) -> dict[str, Any] | None:
        items = quality_by_skill[skill][slot]
        if not items:
            return None
        best = max(items, key=lambda item: (item["decision"] == "PASS", float(item.get("confidence", 0))))
        return {
            "code": best["code"],
            "version_id": best["version_id"],
            "decision": best["decision"],
            "score": best.get("confidence"),
        }

    for row in rows:
        skill = row.target.primary_skill_code
        practice_ok = bool(quality_by_skill[skill]["practice"])
        assessment_ok = bool(quality_by_skill[skill]["assessment"])
        if practice_ok and assessment_ok:
            state = "BOTH_CANDIDATES_AVAILABLE"
        elif practice_ok:
            state = "PRACTICE_ONLY"
            missing_assessment_only += 1
        elif assessment_ok:
            state = "ASSESSMENT_ONLY"
            missing_practice_only += 1
        else:
            state = "NO_CANDIDATE"
            missing_both += 1
        skill_states.append(
            {
                "grade": row.target.grade_code,
                "subject": row.target.subject_code,
                "skill": skill,
                "state": state,
                "best_practice": _best("practice", skill),
                "best_assessment": _best("assessment", skill),
                "draft_practice": row.draft.get(PRACTICE_SLOT, 0),
                "draft_assessment": row.draft.get(ASSESSMENT_SLOT, 0),
            }
        )

    by_grade: dict[str, dict[str, int]] = {}
    for grade in PRIMARY_GRADES:
        grade_skills = [s for s in skill_states if s["grade"] == grade]
        by_grade[grade] = {
            "skills": len(grade_skills),
            "both_candidates": sum(1 for s in grade_skills if s["state"] == "BOTH_CANDIDATES_AVAILABLE"),
            "practice_only": sum(1 for s in grade_skills if s["state"] == "PRACTICE_ONLY"),
            "assessment_only": sum(1 for s in grade_skills if s["state"] == "ASSESSMENT_ONLY"),
            "no_candidate": sum(1 for s in grade_skills if s["state"] == "NO_CANDIDATE"),
            "new_practice_required": sum(
                1 for s in grade_skills if s["state"] in {"ASSESSMENT_ONLY", "NO_CANDIDATE"}
            ),
            "new_assessment_required": sum(
                1 for s in grade_skills if s["state"] in {"PRACTICE_ONLY", "NO_CANDIDATE"}
            ),
        }

    by_subject: dict[str, dict[str, int]] = {}
    for grade, subject in sorted({(s["grade"], s["subject"]) for s in skill_states}):
        subject_skills = [s for s in skill_states if s["grade"] == grade and s["subject"] == subject]
        by_subject[f"{grade}|{subject}"] = {
            "skills": len(subject_skills),
            "both_candidates": sum(1 for s in subject_skills if s["state"] == "BOTH_CANDIDATES_AVAILABLE"),
            "practice_only": sum(1 for s in subject_skills if s["state"] == "PRACTICE_ONLY"),
            "assessment_only": sum(1 for s in subject_skills if s["state"] == "ASSESSMENT_ONLY"),
            "no_candidate": sum(1 for s in subject_skills if s["state"] == "NO_CANDIDATE"),
            "new_practice_required": sum(
                1 for s in subject_skills if s["state"] in {"ASSESSMENT_ONLY", "NO_CANDIDATE"}
            ),
            "new_assessment_required": sum(
                1 for s in subject_skills if s["state"] in {"PRACTICE_ONLY", "NO_CANDIDATE"}
            ),
        }

    total_new = (2 * missing_both) + missing_practice_only + missing_assessment_only
    return {
        "skills": skill_states,
        "by_grade": by_grade,
        "by_subject": by_subject,
        "generation_requirements": {
            "skills_missing_both": missing_both,
            "skills_missing_practice_only": missing_practice_only,
            "skills_missing_assessment_only": missing_assessment_only,
            "total_new_contents_required": total_new,
            "formula": "2*missing_both + missing_practice_only + missing_assessment_only",
        },
    }


def build_ai_review_handoff(
    quality_results: list[dict[str, Any]],
    review_queue: dict[str, Any],
    *,
    candidates: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    selected_codes = {
        item["active_candidate"]["code"]
        for item in review_queue.get("queue", [])
        if item.get("active_candidate")
    }
    handoff: list[dict[str, Any]] = []
    for result in quality_results:
        if result["code"] not in selected_codes or result["decision"] == "REJECT":
            continue
        source = candidates[result["code"]]
        answer = source.get("answer", {})
        handoff.append(
            {
                "candidate_version_id": result["version_id"],
                "campaign_id": AI_HANDOFF_CAMPAIGN,
                "grade": result["grade"],
                "subject": result["subject"],
                "chapter": result["chapter"],
                "skill_code": result["skill"],
                "content_type": result.get("content_type"),
                "question": result.get("prompt", source.get("prompt")),
                "choices": list(answer.get("options", [])),
                "expected_answer": answer.get("expected"),
                "explanation": result.get("explanation", source.get("explanation")),
                "answer_kind": result.get("answer_kind", answer.get("kind")),
                "quality_metadata": {
                    "decision": result["decision"],
                    "confidence": result.get("confidence"),
                    "hard_gates": result.get("hard_gates"),
                    "reasons": result.get("reasons"),
                },
            }
        )
    return handoff


def run_full_isolated_integration(
    db_path: Path,
    *,
    apply_qcm: bool = True,
    prove_idempotency: bool = True,
) -> dict[str, Any]:
    corrected, prep = prepare_corrected_records(database_path=db_path)
    importable = filter_importable_records(corrected, database_path=db_path)
    factory = DuckDBContentFactoryRepository(db_path)
    quality_repo = DuckDBContentQualityRepository(db_path)

    first_import = import_prepared_candidates(factory, importable, include_review=True)
    print(f"[LCAI-0012E] first_import={first_import['counters']}", flush=True)
    second_import = (
        import_prepared_candidates(factory, importable, include_review=True) if prove_idempotency else None
    )
    if second_import:
        print(f"[LCAI-0012E] second_import={second_import['counters']}", flush=True)

    candidates = candidate_sources_from_records(importable)
    quality_payload = audit_draft_quality(quality_repo, factory, candidates, apply_qcm=apply_qcm)
    print(f"[LCAI-0012E] quality={quality_payload['decisions']}", flush=True)
    coverage_rows = [
        {
            "grade": row.target.grade_code,
            "subject": row.target.subject_code,
            "chapter": row.target.chapter_code,
            "skill": row.target.primary_skill_code,
            "skill_name": row.skill_label,
            "approved_practice": sum(
                c for slot, c in row.approved.items() if slot.content_type.value in {"practice", "guided_practice"}
            ),
            "approved_assessment": sum(c for slot, c in row.approved.items() if slot.content_type.value == "assessment"),
        }
        for row in factory.active_skill_coverage(grade_codes=PRIMARY_GRADES)
    ]
    slot_coverage = compute_skill_slot_coverage(quality_payload["results"], database_path=db_path)
    review_queue = build_primary_review_queue(quality_payload["results"], candidates, coverage_rows)
    ai_handoff = build_ai_review_handoff(quality_payload["results"], review_queue, candidates=candidates)

    return {
        "database": str(db_path),
        "production_db_modified": False,
        "preparation": prep,
        "importable_count": len(importable),
        "import_first": first_import["counters"],
        "import_second": second_import["counters"] if second_import else None,
        "quality": quality_payload["decisions"],
        "slot_coverage": slot_coverage,
        "review_queue_size": review_queue["queue_size"],
        "ai_handoff_count": len(ai_handoff),
        "quality_results": quality_payload["results"],
        "review_queue": review_queue,
        "ai_handoff": ai_handoff,
        "duplicates": quality_payload["duplicates"],
    }


def write_full_integration_artifacts(payload: dict[str, Any], root: Path | None = None) -> None:
    base = root or Path(".")
    integration = base / "resources/content/integration"
    quality = base / "resources/content/quality"
    integration.mkdir(parents=True, exist_ok=True)
    quality.mkdir(parents=True, exist_ok=True)

    (integration / "lcai_0012e_skill_corrections_v1.json").write_text(
        json.dumps(payload["preparation"]["skill_corrections"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {k: v for k, v in payload.items() if k not in {"quality_results", "review_queue", "ai_handoff", "duplicates"}}
    (integration / "lcai_0012e_full_integration_summary_v1.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (quality / "lcai_0012e_quality_results.json").write_text(
        json.dumps(payload["quality_results"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (quality / "lcai_0012e_review_queue.json").write_text(
        json.dumps(payload["review_queue"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (quality / "lcai_0012e_slot_coverage.json").write_text(
        json.dumps(payload["slot_coverage"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (integration / "lcai_0012e_ai_review_handoff.jsonl").open("w", encoding="utf-8") as handle:
        for item in payload["ai_handoff"]:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
