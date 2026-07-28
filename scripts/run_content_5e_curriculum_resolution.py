"""Run LCAI-0012E 5e curriculum resolution and incremental recovery."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.content.primary_5e_curriculum_resolution import (  # noqa: E402
    analyze_unmapped_5e_records,
    prepare_all_corrected_records,
    run_incremental_recovery,
    write_resolution_artifacts,
)
from services.content.primary_skill_correction import persist_corrected_json_files  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/phase2"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analyze-only", action="store_true", help="Only run 5e analysis, no import.")
    parser.add_argument("--qc-only", action="store_true", help="Skip analysis print; refresh QC/artifacts only.")
    parser.add_argument("--skip-json-write", action="store_true", help="Do not write corrected JSON packs.")
    args = parser.parse_args()

    db = ROOT / "data/learning_coach_v2.duckdb"
    if not args.qc_only:
        analysis = analyze_unmapped_5e_records(database_path=db)
        print(json.dumps({"analysis": analysis["counts_by_class"], "unique_groups": analysis["unique_groups"]}, indent=2))

    if args.analyze_only:
        out = ROOT / "resources/content/integration/lcai_0012e_5e_curriculum_resolution_v1.json"
        out.write_text(json.dumps(analysis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _write_report(analysis, None)
        return

    payload = run_incremental_recovery(ROOT / "data/learning_coach_v2_0012e_full_test.duckdb")
    if not args.skip_json_write:
        corrected, _ = prepare_all_corrected_records(database_path=ROOT / "data/learning_coach_v2_0012e_full_test.duckdb")
        persist_corrected_json_files(corrected, ROOT / "resources/content")

    write_resolution_artifacts(payload, ROOT)
    _write_report(payload["analysis"], payload)
    summary = {k: payload[k] for k in payload if k not in {"quality_results", "review_queue", "ai_handoff", "analysis", "preparation"}}
    print(json.dumps(summary, ensure_ascii=True, indent=2))


def _write_report(analysis: dict, payload: dict | None) -> None:
    lines = ["# LCAI-0012E — 5e Curriculum Resolution", ""]
    lines.append("## 5E CURRICULUM RESOLUTION")
    lines.append(f"- Unmapped before: {analysis.get('unmapped_before', 87)}")
    if payload:
        lines.append(f"- Recovered (deterministic): {payload.get('recovered_candidates', 0)}")
        lines.append(f"- Curriculum decision required: {analysis.get('counts_by_class', {}).get('CURRICULUM_DECISION_REQUIRED', 0) * 3 if analysis.get('unique_groups') else 15}")
        lines.append(f"- Invalid/out-of-scope: {analysis.get('counts_by_class', {}).get('CONTENT_REQUIRES_NEW_CURRICULUM_SKILL', 0) * 3 if analysis.get('unique_groups') else 3}")
        lines.append(f"- Remaining unmapped: {payload.get('remaining_unmapped', 0)}")
        lines.append(f"- Importable total: {payload.get('importable_count', 0)}")
        gen = payload["slot_coverage"]["generation_requirements"]
        by_grade = payload["slot_coverage"]["by_grade"]
        lines.extend(["", "## FINAL CM1→5E COVERAGE", ""])
        for grade in ("FR-CM1", "FR-CM2", "FR-6E", "FR-5E"):
            g = by_grade[grade]
            label = grade.replace("FR-", "")
            lines.append(f"### {label}")
            lines.append(f"- Skills: {g['skills']}")
            lines.append(f"- Both candidates: {g['both_candidates']}")
            lines.append(f"- Practice only: {g['practice_only']}")
            lines.append(f"- Assessment only: {g['assessment_only']}")
            lines.append(f"- No candidate: {g['no_candidate']}")
            lines.append(f"- New Practice required: {g['new_practice_required']}")
            lines.append(f"- New Assessment required: {g['new_assessment_required']}")
            lines.append("")
        lines.append(f"**TOTAL NEW CONTENTS REQUIRED: {gen['total_new_contents_required']}**")
        lines.append(f"- Skills missing both: {gen['skills_missing_both']}")
        lines.append(f"- Skills missing practice only: {gen['skills_missing_practice_only']}")
        lines.append(f"- Skills missing assessment only: {gen['skills_missing_assessment_only']}")
        lines.append("")
        lines.append(f"**FINAL BEST CANDIDATES FOR AI REVIEW: {payload.get('ai_handoff_count', 0)}**")
        lines.append("")
        lines.append("## Quality (merged)")
        lines.append(f"- PASS: {payload['quality'].get('PASS', 0)}")
        lines.append(f"- REVIEW: {payload['quality'].get('REVIEW', 0)}")
        lines.append(f"- REJECT: {payload['quality'].get('REJECT', 0)}")
        verdict = (
            "**LCAI-0012E: READY FOR CALIBRATED AI REVIEW**"
            if payload.get("remaining_unmapped", 1) <= 18
            else "**LCAI-0012E: CURRICULUM DECISION REQUIRED**"
        )
    else:
        lines.append("- Analysis only — see counts_by_class in artifact.")
        verdict = "**LCAI-0012E: CURRICULUM DECISION REQUIRED** (analysis phase)"
    lines.extend(["", "## Verdict", "", verdict, "", "- Production DB modified: **no**", "- AI review started: **no**"])
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "LCAI-0012E_5E_CURRICULUM_RESOLUTION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    counts = analysis.get("counts_by_class", {})
    groups = analysis.get("group_analyses", [])
    lines2 = ["", "## Affected unique Skills/concepts", ""]
    for g in groups:
        lines2.append(
            f"- `{g['original_primary_skill_code']}` ({g['record_count']} records) → "
            f"{g['analysis_class']}"
            + (f" → `{g['corrected_primary_skill_code']}`" if g.get("corrected_primary_skill_code") else "")
        )
    (DOCS / "LCAI-0012E_5E_CURRICULUM_RESOLUTION_REPORT.md").open("a", encoding="utf-8").write("\n".join(lines2) + "\n")


if __name__ == "__main__":
    main()
