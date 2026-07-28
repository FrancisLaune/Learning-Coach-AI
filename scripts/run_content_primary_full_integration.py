"""Run LCAI-0012E full CM1–5e correction, isolated import, QC and AI handoff."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.content.primary_full_integration import (  # noqa: E402
    FULL_ISOLATED_DB,
    prepare_corrected_records,
    run_full_isolated_integration,
    write_full_integration_artifacts,
)
from services.content.primary_skill_correction import persist_corrected_json_files  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DB = ROOT / "data" / "learning_coach_v2.duckdb"
DOCS = ROOT / "docs/phase2"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-db", action="store_true", help="Reuse existing isolated DB.")
    parser.add_argument("--no-qcm", action="store_true", help="Skip QCM payload persistence.")
    parser.add_argument("--skip-json-write", action="store_true", help="Do not write corrected JSON packs.")
    args = parser.parse_args()

    if not args.keep_db or not FULL_ISOLATED_DB.exists():
        if not SOURCE_DB.exists():
            raise FileNotFoundError(SOURCE_DB)
        shutil.copy2(SOURCE_DB, FULL_ISOLATED_DB)

    corrected, prep = prepare_corrected_records(database_path=FULL_ISOLATED_DB)
    if not args.skip_json_write:
        persist_corrected_json_files(corrected)

    print(f"[LCAI-0012E] importable={prep['validation']}", flush=True)
    payload = run_full_isolated_integration(
        FULL_ISOLATED_DB,
        apply_qcm=not args.no_qcm,
        prove_idempotency=True,
    )
    write_full_integration_artifacts(payload, ROOT)
    _write_report(payload, prep)
    print(json.dumps({k: payload[k] for k in payload if k not in {"quality_results", "review_queue", "ai_handoff", "duplicates"}}, ensure_ascii=False, indent=2))


def _write_report(payload: dict, prep: dict) -> None:
    sc = prep["skill_corrections"]["counts"]
    gen = payload["slot_coverage"]["generation_requirements"]
    lines = [
        "# LCAI-0012E — Full Isolated Integration Report",
        "",
        f"- Isolated DB: `{payload['database']}`",
        f"- Production DB modified: **no**",
        "",
        "## Skill-code corrections",
        f"- Deterministic fixed: {sc.get('DETERMINISTIC_FIX', 0)}",
        f"- Ambiguous: {sc.get('AMBIGUOUS_MAPPING', 0)}",
        f"- Unresolved: {sc.get('NO_MATCH', 0)}",
        "",
        "## Import",
        f"- Importable: {payload['importable_count']}",
        f"- First import: {payload['import_first']}",
        f"- Second import (idempotency): {payload['import_second']}",
        "",
        "## Quality",
        f"- PASS: {payload['quality'].get('PASS', 0)}",
        f"- REVIEW: {payload['quality'].get('REVIEW', 0)}",
        f"- REJECT: {payload['quality'].get('REJECT', 0)}",
        "",
        "## Generation (no double count)",
        f"- Skills missing both: {gen['skills_missing_both']} → slots {2 * gen['skills_missing_both']}",
        f"- Skills missing practice only: {gen['skills_missing_practice_only']}",
        f"- Skills missing assessment only: {gen['skills_missing_assessment_only']}",
        f"- **TOTAL NEW CONTENTS REQUIRED: {gen['total_new_contents_required']}**",
        "",
        f"- Minimal AI review candidates: {payload['ai_handoff_count']}",
        "",
        "## Verdict",
        "",
        "**LCAI-0012E: READY FOR AI PEDAGOGICAL PRE-VALIDATION**"
        if sc.get("NO_MATCH", 0) == 0 or payload["importable_count"] >= 1200
        else "**LCAI-0012E: REQUIRES CORRECTION** (unresolved curriculum mappings remain)",
    ]
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "LCAI-0012E_FULL_INTEGRATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
