"""Build the LCAI-0012D4 Wave-1 review queue and planning artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository  # noqa: E402
from infrastructure.repositories.content_quality import DuckDBContentQualityRepository  # noqa: E402
from scripts.run_content_approval_acceleration import _review_taxonomy  # noqa: E402
from scripts.run_content_quality_audit import _candidate_sources  # noqa: E402
from services.content.d4_wave1 import (  # noqa: E402
    audit_wave1_queue,
    build_active_wave1_queue,
    build_wave1_targets,
    coverage_snapshot,
    g2_complement_plan,
    prepare_ranked_records,
    projected_tier1_totals,
)

ROOT = Path(__file__).resolve().parents[1]
QUALITY = ROOT / "resources" / "content" / "quality"
DOCS = ROOT / "docs" / "phase2"


def _load(name: str) -> Any:
    return json.loads((QUALITY / name).read_text(encoding="utf-8"))


def _dump(name: str, value: Any) -> None:
    (QUALITY / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def run() -> dict[str, Any]:
    results: list[dict[str, Any]] = _load("lcai_0012d_quality_results.json")
    duplicates = _load("lcai_0012d_duplicate_audit.json")
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

    ranked = prepare_ranked_records(
        results,
        sources,
        coverage,
        near_codes=near_codes,
        resolved=resolved,
    )
    targets = build_wave1_targets(coverage_rows, ranked)
    queue, summary = build_active_wave1_queue(targets, coverage_rows, review_statuses)
    complements = g2_complement_plan(targets, review_statuses)
    projection = projected_tier1_totals(coverage_rows, targets)
    snapshot = coverage_snapshot(coverage_rows)
    audit = audit_wave1_queue(queue)

    complement_counts = {
        "practice": sum(1 for item in complements if item["generate_slot"] == "practice"),
        "assessment": sum(1 for item in complements if item["generate_slot"] == "assessment"),
        "total": len(complements),
    }

    payload = {
        "wave": "LCAI-0012D4-WAVE1",
        "target_tier1": 100,
        "summary": summary,
        "projection": projection,
        "coverage_snapshot": snapshot,
        "queue": queue,
        "targets": [
            {
                "skill": target["skill"],
                "skill_name": target["skill_name"],
                "grade": target["grade"],
                "subject": target["subject"],
                "chapter": target["chapter"],
                "wave_band": target["wave_band"],
                "selected_slot": target["selected_slot"],
                "complement_slot": target["complement_slot"],
                "candidate_count": len(target["candidates"]),
                "active_version_id": next(
                    (
                        int(candidate["version_id"])
                        for candidate in target["candidates"]
                        if review_statuses.get(int(candidate["version_id"]), "PENDING") == "PENDING"
                    ),
                    None,
                ),
            }
            for target in targets
        ],
        "g2_complement_plan": complements,
        "complement_counts": complement_counts,
        "human_review_audit": audit,
    }

    _dump("lcai_0012d4_wave1_review_queue.json", queue)
    _dump("lcai_0012d4_wave1_targets.json", payload["targets"])
    _dump("lcai_0012d4_wave1_alternates.json", {target["skill"]: target["candidates"] for target in targets})
    _dump("lcai_0012d4_wave1_g2_complements.json", complements)
    _dump("lcai_0012d4_wave1_human_review_audit.json", audit)
    _dump("lcai_0012d4_wave1_summary.json", payload)

    report = f"""# LCAI-0012D4 — Wave 1 Implementation Report

## Objectif

Atteindre jusqu'à **100 compétences Tier 1** via revue humaine minimale (54 candidats max).

## File de revue Wave 1

- Tier 2 sélectionnés : {summary["tier2_selected"]}
- G2 sélectionnés : {summary["g2_selected"]}
- Taille totale de la file active : {summary["queue_size"]}

## Projection Tier 1

| Étape | Tier 1 |
| --- | ---: |
| Baseline | {projection["baseline_tier1"]} |
| Après approbations Tier 2 | {projection["after_tier2_approvals"]} |
| Après approbations G2 existantes | {projection["after_g2_existing_approvals"]} |
| Après compléments G2 générés + approuvés | {projection["after_g2_complements"]} |

## Compléments G2 à générer (après approbation du candidat existant)

- Practice : {complement_counts["practice"]}
- Assessment : {complement_counts["assessment"]}
- Total : {complement_counts["total"]}

## Décisions humaines attendues (succès complet)

- Revues Tier 2 : {summary["tier2_selected"]}
- Revues G2 existantes : {summary["g2_selected"]}
- Revues compléments générés : {complement_counts["total"]}
- **Total ≈ {summary["tier2_selected"] + summary["g2_selected"] + complement_counts["total"]}**

## Lancement UI

```powershell
python -m streamlit run ui/content_approval_d4_wave1_app.py
```

**D4 WAVE 1: READY FOR HUMAN REVIEW**
"""
    (DOCS / "LCAI-0012D4_WAVE1_IMPLEMENTATION_REPORT.md").write_text(report, encoding="utf-8")
    return payload


if __name__ == "__main__":
    print(json.dumps(run()["summary"], ensure_ascii=False, indent=2))
