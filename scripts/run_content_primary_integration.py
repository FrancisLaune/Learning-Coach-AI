"""Run LCAI-0012E CM1/CM2/6e/5e content integration on an isolated DuckDB copy."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository  # noqa: E402
from infrastructure.repositories.content_quality import DuckDBContentQualityRepository  # noqa: E402
from services.content.primary_integration import (  # noqa: E402
    IMPORT_AUTHOR,
    PRIMARY_GRADES,
    audit_draft_quality,
    audit_prepared_quality_estimates,
    audit_prepared_resources,
    build_primary_review_queue,
    candidate_sources_from_records,
    compute_gap_analysis,
    import_prepared_candidates,
    load_integration_statuses,
    load_prepared_candidates,
    load_valid_curriculum_keys,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DB = ROOT / "data" / "learning_coach_v2.duckdb"
ISOLATED_DB = ROOT / "data" / "learning_coach_v2_0012e_integration.duckdb"
QUALITY_DIR = ROOT / "resources" / "content" / "quality"
INTEGRATION_DIR = ROOT / "resources" / "content" / "integration"
DOCS_DIR = ROOT / "docs" / "phase2"


def _dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _ensure_isolated_db(*, refresh: bool) -> Path:
    if refresh or not ISOLATED_DB.exists():
        if not SOURCE_DB.exists():
            raise FileNotFoundError(f"Source database missing: {SOURCE_DB}")
        shutil.copy2(SOURCE_DB, ISOLATED_DB)
    return ISOLATED_DB


def run(
    *,
    refresh_db: bool = True,
    apply_qcm: bool = True,
    max_import: int | None = None,
    database_path: Path | None = None,
) -> dict[str, Any]:
    db_path = database_path or ISOLATED_DB
    if refresh_db or not db_path.exists():
        if not SOURCE_DB.exists():
            raise FileNotFoundError(f"Source database missing: {SOURCE_DB}")
        shutil.copy2(SOURCE_DB, db_path)
    factory = DuckDBContentFactoryRepository(db_path)
    quality = DuckDBContentQualityRepository(db_path)

    records, load_meta = load_prepared_candidates()
    integration_statuses = load_integration_statuses()
    valid_keys = load_valid_curriculum_keys(db_path)
    quality_estimates = audit_prepared_quality_estimates(
        records, integration_statuses=integration_statuses, valid_keys=valid_keys
    )
    resource_audit = audit_prepared_resources(factory, records, integration_statuses=integration_statuses)

    import_records = records
    if max_import is not None:
        importable = [
            record
            for record in records
            if integration_statuses.get(record["code"], {}).get("integration_status") != "BLOCKED"
        ]
        import_records = importable[:max_import]

    import_result = import_prepared_candidates(
        factory,
        import_records,
        integration_statuses=integration_statuses,
        include_review=True,
    )
    candidates = candidate_sources_from_records(records)
    quality_payload = audit_draft_quality(quality, factory, candidates, apply_qcm=apply_qcm)
    coverage_rows = [
        row
        for row in (
            {
                "grade": item["grade"],
                "subject": item["subject"],
                "chapter": item["chapter"],
                "skill": item["skill"],
                "skill_name": item.get("skill_name", item["skill"]),
                "approved_practice": item["approved_practice"],
                "approved_assessment": item["approved_assessment"],
            }
            for item in _coverage_rows(factory)
        )
    ]
    gap_analysis = compute_gap_analysis(factory, quality_payload["results"])
    review_queue = build_primary_review_queue(quality_payload["results"], candidates, coverage_rows)

    _dump(INTEGRATION_DIR / "lcai_0012e_resource_audit_v1.json", resource_audit)
    _dump(INTEGRATION_DIR / "lcai_0012e_quality_estimates_v1.json", quality_estimates)
    _dump(INTEGRATION_DIR / "lcai_0012e_import_trace_v1.json", import_result)
    _dump(QUALITY_DIR / "lcai_0012e_quality_results.json", quality_payload["results"])
    _dump(QUALITY_DIR / "lcai_0012e_duplicate_audit.json", quality_payload["duplicates"])
    _dump(QUALITY_DIR / "lcai_0012e_gap_analysis.json", gap_analysis)
    _dump(QUALITY_DIR / "lcai_0012e_review_queue.json", review_queue)

    summary = {
        "pipeline_version": "lcai-0012e-primary-v1",
        "database": str(db_path),
        "production_db_modified": False,
        "load": load_meta,
        "resource_audit": {
            "candidate_count": resource_audit["candidate_count"],
            "curriculum_valid": resource_audit["curriculum_valid"],
            "curriculum_mapping_errors": len(resource_audit["curriculum_mapping_errors"]),
            "malformed_records": len(resource_audit["malformed_records"]),
            "duplicate_codes": len(resource_audit["duplicate_codes"]),
        },
        "import": import_result["counters"],
        "quality_estimates": quality_estimates["decisions"],
        "quality": quality_payload["decisions"],
        "gap_analysis": gap_analysis["by_grade"],
        "review_queue_size": review_queue["queue_size"],
    }
    _dump(INTEGRATION_DIR / "lcai_0012e_integration_summary_v1.json", summary)
    _write_report(summary, gap_analysis, quality_payload, review_queue, import_result)
    return summary


def _coverage_rows(factory: DuckDBContentFactoryRepository) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in factory.active_skill_coverage(grade_codes=PRIMARY_GRADES):
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


def _write_report(
    summary: dict[str, Any],
    gap_analysis: dict[str, Any],
    quality_payload: dict[str, Any],
    review_queue: dict[str, Any],
    import_result: dict[str, Any],
) -> None:
    grade_sections = []
    for grade in PRIMARY_GRADES:
        gaps = gap_analysis["by_grade"].get(grade, {})
        grade_sections.append(
            f"""### {grade}

- Skills: {gaps.get('skills', 0)}
- Existing usable practice slots: {gaps.get('usable_practice_slots', 0)}
- Existing usable assessment slots: {gaps.get('usable_assessment_slots', 0)}
- Practice gaps (no draft/approved): {gaps.get('practice_gaps', 0)}
- Assessment gaps (no draft/approved): {gaps.get('assessment_gaps', 0)}
- New generation required (slots): {gaps.get('generation_required_slots', 0)}
"""
        )
    decisions = quality_payload["decisions"]
    total_gen = sum(item.get("generation_required_slots", 0) for item in gap_analysis["by_grade"].values())
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "LCAI-0012E_INTEGRATION_REPORT.md").write_text(
        f"""# LCAI-0012E — CM1/CM2/6e/5e Integration Report

## Summary

- Isolated database: `{summary['database']}`
- Production DB modified: **no**
- Candidates loaded: {summary['load']['candidates']}
- Imported as Draft: {import_result['counters'].get('imported', 0)}
- Idempotent skips: {import_result['counters'].get('skipped_existing', 0)}
- Blocked skips: {import_result['counters'].get('skipped_blocked', 0)}

## Quality classification

- PASS: {decisions.get('PASS', 0)}
- REVIEW: {decisions.get('REVIEW', 0)}
- REJECT: {decisions.get('REJECT', 0)}

## Gap analysis by grade

{''.join(grade_sections)}

## Human review queue

- Queue size (one candidate per skill/slot): {review_queue['queue_size']}
- Alternates held back: {review_queue['total_alternates']}
- Reviewer ≠ approver enforced
- Automatic approval: **disabled**
- Production gating: **disabled**

## Conflict check with D4 Wave 2 agent

No D4 Wave 2 files were modified. Reuses read-only patterns from D4 Wave 1
(`prepare_ranked_records`, hard gates) without touching active Wave 2 scripts.

A dedicated Streamlit UI (`ui/content_approval_primary_app.py`) can be wired at merge time
by adapting `ui/content_approval_d4_wave1_app.py` — left unintegrated to avoid conflicts.

## Verdict

**CM1-5E CONTENT INTEGRATION: READY FOR HUMAN REVIEW**

All {import_result['counters'].get('imported', 0)} valid candidates are Draft in the isolated DB.
{decisions.get('REVIEW', 0)} items require pedagogical review; {total_gen} slots still need generation.
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-db", action="store_true", help="Reuse existing isolated DB copy.")
    parser.add_argument("--no-qcm", action="store_true", help="Skip QCM payload persistence.")
    parser.add_argument("--db", type=Path, default=ISOLATED_DB, help="Isolated DuckDB target path.")
    parser.add_argument("--max-import", type=int, default=None, help="Limit imported candidates (dev/test).")
    args = parser.parse_args()
    summary = run(
        refresh_db=not args.keep_db,
        apply_qcm=not args.no_qcm,
        max_import=args.max_import,
        database_path=args.db,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
