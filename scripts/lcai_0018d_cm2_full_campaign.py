"""LCAI-0018D — CM2 full chapter publication campaign (sequential subjects)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb

from core.config import get_v2_database_path
from infrastructure.database.v2 import reset_v2_connections
from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from services.content.cm2_full_publication import (
    CM2_SUBJECT_ORDER,
    GRADE,
    SUBJECT_LABELS,
    curriculum_chapters,
    execute_cm2_draft_fallback_publication,
    execute_cm2_relaxed_publication,
    load_bundles,
    plan_cm2_draft_fallback_subject,
    plan_cm2_subject_chapters,
    published_chapters,
)
from services.content.primary_controlled_publication import verify_import_state, verify_review_completion

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "docs" / "phase3" / "exports"
CAMPAIGN_REPORT_PATH = REPORT_DIR / "lcai_0018d_cm2_full_campaign_report.json"
CAMPAIGN_MD_PATH = ROOT / "docs" / "phase3" / "LCAI-0018D_CM2_FULL_CAMPAIGN_REPORT.md"
CONFIRMATION_FLAG = "--confirm-cm2-full-publication"


def _chapter_coverage(connection: duckdb.DuckDBPyConnection) -> dict[str, dict[str, int]]:
    coverage: dict[str, dict[str, int]] = {}
    for subject in CM2_SUBJECT_ORDER:
        expected = curriculum_chapters(connection, grade_code=GRADE, subject_code=subject)
        published = published_chapters(connection, grade_code=GRADE, subject_code=subject)
        coverage[subject] = {
            "curriculum": len(expected),
            "published": len(published),
            "missing": len(expected - published),
        }
    return coverage


def run_campaign(
    *,
    execute: bool,
    confirmed: bool,
    database_path: Path,
    subjects: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    reset_v2_connections()
    review_status = verify_review_completion()
    if not review_status["complete"]:
        raise RuntimeError("LCAI-0012E review incomplete.")

    import_status = verify_import_state(database_path)
    reset_v2_connections()
    bundles, loader_meta = load_bundles(database_path)
    reset_v2_connections()
    repository = DuckDBContentQualityRepository(database_path)
    already_published = {
        int(item["source_version_id"])
        for item in repository.list_ai_controlled_publications(
            campaign_id="LCAI-0012E-CM1-5E-PUBLICATION-V1"
        )
    }
    reset_v2_connections()

    subject_sequence = subjects or CM2_SUBJECT_ORDER
    subject_results: list[dict[str, Any]] = []
    total_published = 0

    connection = duckdb.connect(str(database_path))
    try:
        coverage_before = _chapter_coverage(connection)
    finally:
        connection.close()
        reset_v2_connections()

    for subject_code in subject_sequence:
        manifest, plan = plan_cm2_subject_chapters(
            bundles,
            subject_code=subject_code,
            database_path=database_path,
            already_published_version_ids=already_published,
        )
        fallback_items: list[dict[str, Any]] = []
        if plan["manifest_count"] == 0 and subject_code == "ENGLISH":
            manifest, fallback_items, plan = plan_cm2_draft_fallback_subject(
                subject_code=subject_code,
                database_path=database_path,
                already_published_version_ids=already_published,
            )

        subject_report: dict[str, Any] = {
            "subject_code": subject_code,
            "subject_label": SUBJECT_LABELS.get(subject_code, subject_code),
            "plan": plan,
            "published": [],
        }

        if execute:
            if not confirmed:
                raise SystemExit(f"Real execution requires {CONFIRMATION_FLAG}")
            if manifest:
                if fallback_items:
                    published = execute_cm2_draft_fallback_publication(
                        repository, manifest=manifest, items=fallback_items
                    )
                else:
                    published = execute_cm2_relaxed_publication(
                        repository, manifest=manifest, bundles=bundles
                    )
                subject_report["published"] = published
                total_published += len(published)
                for row in published:
                    already_published.add(int(row["version_id"]))

        subject_results.append(subject_report)

    connection = duckdb.connect(str(database_path))
    try:
        coverage_after = _chapter_coverage(connection)
    finally:
        connection.close()
        reset_v2_connections()

    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "mode": "EXECUTE" if execute else "DRY_RUN",
        "grade": GRADE,
        "objective": "B_24_CHAPTERS",
        "policy": {
            "accept_warning": True,
            "skip_teacher_review": True,
            "allow_rejected_relaxed": True,
        },
        "subject_sequence": list(subject_sequence),
        "import_status": import_status,
        "review_status": review_status,
        "loader_meta": loader_meta,
        "coverage_before": coverage_before,
        "coverage_after": coverage_after,
        "total_published": total_published,
        "subjects": subject_results,
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    CAMPAIGN_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_markdown(report)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return report


def _write_markdown(report: dict[str, Any]) -> None:
    lines = [
        "# LCAI-0018D — Campagne CM2 complète (24 chapitres)",
        "",
        f"**Date :** {report['generated_at']}",
        f"**Mode :** {report['mode']}",
        f"**Objectif :** {report['objective']}",
        "",
        "## Couverture chapitres",
        "",
        "| Matière | Ch. curriculum | Publiés avant | Publiés après | Manquants après |",
        "|---------|---------------:|--------------:|--------------:|----------------:|",
    ]
    for subject in report["subject_sequence"]:
        before = report["coverage_before"][subject]
        after = report["coverage_after"][subject]
        label = SUBJECT_LABELS.get(subject, subject)
        lines.append(
            f"| {label} | {after['curriculum']} | {before['published']} | {after['published']} | {after['missing']} |"
        )

    total_cur = sum(report["coverage_after"][s]["curriculum"] for s in report["subject_sequence"]) + 5
    total_pub = sum(report["coverage_after"][s]["published"] for s in report["subject_sequence"]) + 5
    lines.extend(
        [
            "",
            f"**Total publiés :** {total_pub} / 24 chapitres (maths inclus)",
            f"**Publications exécutées :** {report['total_published']}",
            "",
            "## Détail par matière",
            "",
        ]
    )
    for subject_report in report["subjects"]:
        plan = subject_report["plan"]
        lines.append(f"### {plan['subject_label']} (`{plan['subject_code']}`)")
        lines.append("")
        lines.append(f"- Manifeste : **{plan['manifest_count']}** item(s)")
        lines.append(f"- Chapitres ciblés : {', '.join(plan['selected_chapters']) or '—'}")
        if plan["blocked"]:
            lines.append(f"- Bloqués : **{len(plan['blocked'])}**")
        if subject_report["published"]:
            lines.append(f"- Publiés : **{len(subject_report['published'])}**")
        lines.append("")

    lines.extend(
        [
            "## Livrables",
            "",
            "- `docs/phase3/exports/lcai_0018d_cm2_full_campaign_report.json`",
            "- `docs/phase3/LCAI-0018D_CM2_FULL_CAMPAIGN_REPORT.md`",
            "",
        ]
    )
    CAMPAIGN_MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="LCAI-0018D CM2 full chapter publication campaign.")
    parser.add_argument("--execute", action="store_true", help="Perform publication writes.")
    parser.add_argument(
        CONFIRMATION_FLAG,
        action="store_true",
        dest="confirm_publication",
        help="Required confirmation for real execution.",
    )
    parser.add_argument(
        "--subject",
        action="append",
        dest="subjects",
        help="Limit to one or more subject codes (default: full sequence).",
    )
    parser.add_argument("--database", default=str(get_v2_database_path()))
    args = parser.parse_args()
    run_campaign(
        execute=args.execute,
        confirmed=args.confirm_publication,
        database_path=Path(args.database),
        subjects=tuple(args.subjects) if args.subjects else None,
    )


if __name__ == "__main__":
    main()
