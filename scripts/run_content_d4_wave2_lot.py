"""Execute one LCAI-0012D4 Wave-2 lot: select, generate missing slots, build human queue."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository  # noqa: E402
from infrastructure.repositories.content_quality import DuckDBContentQualityRepository  # noqa: E402
from scripts.run_content_approval_acceleration import _review_taxonomy  # noqa: E402
from scripts.run_content_expansion import (  # noqa: E402
    _load_local_openai_settings,
    execute,
    plan,
)
from scripts.run_content_quality_audit import _candidate_sources  # noqa: E402
from services.content.d4_wave2 import (  # noqa: E402
    LOT_SIZE_DEFAULT,
    audit_wave2_queue,
    build_wave2_human_queue,
    build_wave2_lot_plan,
    evaluate_generated_candidate,
    prepare_ranked_records,
    projected_tier1_after_lot,
    select_wave2_lot_skills,
)

ROOT = Path(__file__).resolve().parents[1]
QUALITY = ROOT / "resources" / "content" / "quality"
EXPANSION = ROOT / "resources" / "content" / "expansion"


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
                "skill_name": row.skill_label,
                "approved_practice": practice,
                "approved_assessment": assessment,
            }
        )
    return output


def _dump(name: str, value: Any) -> None:
    QUALITY.mkdir(parents=True, exist_ok=True)
    (QUALITY / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _lot_output_path(lot_number: int) -> Path:
    return EXPANSION / f"lcai_0012d4_wave2_lot{lot_number}_generation.jsonl"


def _ingest_generated_candidates(
    lot_plan: dict[str, Any],
    ranked: dict[str, list[dict[str, Any]]],
    output_path: Path,
    *,
    lot_number: int,
) -> list[dict[str, Any]]:
    """Attach previously persisted lot generations to the plan and ranked pool."""
    generated_candidates: list[dict[str, Any]] = []
    cached_path = QUALITY / f"lcai_0012d4_wave2_lot{lot_number}_generated_candidates.json"
    if cached_path.exists():
        generated_candidates = json.loads(cached_path.read_text(encoding="utf-8"))
        for generated in generated_candidates:
            record = generated["queue_record"]
            key = f"{generated['skill']}|{generated['slot']}"
            ranked.setdefault(key, []).insert(0, record)
            for target in lot_plan["slot_targets"]:
                if target["skill"] != generated["skill"]:
                    continue
                if target["slot"] != generated["slot"]:
                    continue
                if target["candidate"] is None:
                    target["candidate"] = record
                    target["candidate_source"] = "generated"
                    target["needs_generation"] = False
                    target["alternate_count"] = 0
        return generated_candidates
    if not output_path.exists():
        return generated_candidates
    inventory = {item["code"]: item for item in DuckDBContentQualityRepository().draft_inventory()}
    for line in output_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("final_result") != "PERSISTED_DRAFT":
            continue
        code = next(
            attempt["candidate"]["code"]
            for attempt in record["attempts"]
            if attempt.get("result") == "PASS"
        )
        evaluated = evaluate_generated_candidate(record, inventory[code])
        if evaluated is None:
            continue
        slot = str(evaluated["content_type"])
        generated_candidates.append(
            {
                "skill": record["skill"],
                "slot": slot,
                "queue_record": evaluated,
                "gap_key": record["gap_key"],
            }
        )
        key = f"{record['skill']}|{slot}"
        ranked.setdefault(key, []).insert(0, evaluated)
    for generated in generated_candidates:
        for target in lot_plan["slot_targets"]:
            if target["skill"] != generated["skill"]:
                continue
            if target["slot"] != generated["slot"]:
                continue
            if target["candidate"] is None:
                target["candidate"] = generated["queue_record"]
                target["candidate_source"] = "generated"
                target["needs_generation"] = False
                target["alternate_count"] = 0
    return generated_candidates


def run(
    *,
    lot_number: int = 1,
    lot_size: int = LOT_SIZE_DEFAULT,
    generate: bool = False,
    workers: int = 4,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = json.loads((QUALITY / "lcai_0012d_quality_results.json").read_text(encoding="utf-8"))
    duplicates = json.loads((QUALITY / "lcai_0012d_duplicate_audit.json").read_text(encoding="utf-8"))
    sources = _candidate_sources()
    coverage_rows = _coverage_rows()
    coverage = {str(row["skill"]): row for row in coverage_rows}
    near_codes = {
        str(item[key])
        for item in duplicates["near_groups"]
        for key in ("left", "right")
        if item["decision"] == "REVIEW"
    }
    _, resolved = _review_taxonomy(results, sources, near_codes)
    review_statuses = DuckDBContentQualityRepository().approval_queue_review_statuses()
    active_skills = DuckDBContentFactoryRepository().active_skill_coverage()

    lot_skills = select_wave2_lot_skills(coverage_rows, lot_number=lot_number, lot_size=lot_size)
    lot_skill_codes = tuple(str(row["skill"]) for row in lot_skills)
    ranked = prepare_ranked_records(
        results,
        sources,
        coverage,
        near_codes=near_codes,
        resolved=resolved,
    )

    lot_plan = build_wave2_lot_plan(
        lot_skills,
        ranked,
        review_statuses,
        active_skills=active_skills,
        quality_results=results,
    )

    generation_metrics: dict[str, int] = {}
    output_path = _lot_output_path(lot_number)

    if generate and lot_plan["planned_gaps"]:
        gaps = plan(
            skills=lot_skill_codes,
            output=output_path,
            corrective=True,
        )
        if gaps:
            generation_metrics = execute(
                gaps,
                output=output_path,
                workers=workers,
                model=_load_local_openai_settings(),
            )

    generated_candidates = _ingest_generated_candidates(lot_plan, ranked, output_path, lot_number=lot_number)

    queue = build_wave2_human_queue(lot_plan, coverage, lot_number=lot_number)
    audit = audit_wave2_queue(queue)
    projection = projected_tier1_after_lot(coverage_rows, lot_skills, queue)

    existing_used = sum(1 for item in queue if item["candidate_source"] == "existing")
    generated_used = sum(1 for item in queue if item["candidate_source"] == "generated")
    generation_needed = len(lot_plan["generation_requests"])
    blocked = audit["technically_blocked"]

    summary = {
        "lot_number": lot_number,
        "lot_size": lot_size,
        "skills_in_lot": len(lot_skills),
        "existing_candidates_used": existing_used,
        "generated_candidates_used": generated_used,
        "generation_requests": generation_needed,
        "generation_executed": bool(generation_metrics),
        "generation_metrics": generation_metrics,
        "human_decisions_required": len(queue),
        "technically_blocked": blocked,
        "projection": projection,
        "subjects": sorted({row["subject"] for row in lot_skills}),
        "grades": sorted({row["grade"] for row in lot_skills}),
    }

    prefix = f"lcai_0012d4_wave2_lot{lot_number}"
    _dump(f"{prefix}_skills.json", lot_skills)
    _dump(f"{prefix}_plan.json", lot_plan)
    _dump(f"{prefix}_review_queue.json", queue)
    _dump(f"{prefix}_human_review_audit.json", audit)
    _dump(f"{prefix}_summary.json", summary)
    _dump(f"{prefix}_generated_candidates.json", generated_candidates)

    report = {
        **summary,
        "risks_or_blockers": [
            f"{blocked} candidats techniquement bloqués" if blocked else None,
            (
                f"{generation_needed} slots sans candidat exploitable"
                if generation_needed and not generate
                else None
            ),
            (
                "Génération demandée mais aucun Draft persisté"
                if generate and generation_needed and not generated_candidates
                else None
            ),
        ],
    }
    report["risks_or_blockers"] = [item for item in report["risks_or_blockers"] if item]
    return report


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Exécuter un lot Wave 2 D4.")
    parser.add_argument("--lot", type=int, default=1)
    parser.add_argument("--lot-size", type=int, default=LOT_SIZE_DEFAULT)
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    report = run(
        lot_number=args.lot,
        lot_size=args.lot_size,
        generate=args.generate,
        workers=args.workers,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
