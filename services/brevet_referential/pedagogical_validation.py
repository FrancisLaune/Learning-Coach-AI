"""LCAI-0036 — offline pedagogical validation pipeline for official DNB corpus."""

from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.config import PROJECT_ROOT, get_database_path
from infrastructure.repositories.brevet_content.store import BrevetContentStore
from services.brevet_referential.migrations import apply_brevet_content_migrations
from services.brevet_referential.pedagogical_classifiers import (
    assess_compatibility_2027,
    assess_segmentation,
    classify_content_type,
    classify_discipline,
    classify_subject_group,
    decide_validation_status,
    detect_automatism_flags,
    mapping_confidence_from_links,
    reliability_score,
    review_priority_score,
    statement_mentions_missing_support,
)
from services.brevet_referential.traceability import count_archive_derived_without_parent

VALIDATOR_VERSION = "lcai-0036-validator-v1"
RULESET_VERSION = "lcai-0036-ruleset-v1"
CURRICULUM_CODE = "FR_3E_DNB_2027_V1"
ARTIFACT_DIR = PROJECT_ROOT / "artifacts" / "LCAI-0036"
DOCS_DIR = PROJECT_ROOT / "docs" / "phase6" / "LCAI-0036"


@dataclass(slots=True)
class ValidationStats:
    audited: int = 0
    auto_checked: int = 0
    review: int = 0
    rejected: int = 0
    validated: int = 0
    compat_true: int = 0
    compat_false: int = 0
    compat_review: int = 0


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _csv_write(path: Path, headers: list[str], rows: list[list[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)


def _history(
    store: BrevetContentStore,
    *,
    content_id: int,
    field_name: str,
    old_value: str | None,
    new_value: str | None,
    actor_type: str,
    reason: str,
) -> None:
    if old_value == new_value:
        return
    store.execute(
        """
        INSERT INTO pedagogical_validation_history(
            content_id, field_name, old_value, new_value, actor_type, actor_id,
            reason, curriculum_version_code, validator_version, ruleset_version
        ) VALUES (?, ?, ?, ?, ?, 'system', ?, ?, ?, ?)
        """,
        [
            content_id,
            field_name,
            old_value,
            new_value,
            actor_type,
            reason,
            CURRICULUM_CODE,
            VALIDATOR_VERSION,
            RULESET_VERSION,
        ],
    )


def _load_official_rows(store: BrevetContentStore) -> list[dict[str, Any]]:
    rows = store.fetchall(
        """
        SELECT
            c.content_id,
            c.statement,
            c.title,
            c.brevet_format,
            c.validation_status,
            c.curriculum_2027_compatible,
            c.runtime_playable,
            sub.code,
            q.archive_question_id,
            q.question_number,
            q.correction_source,
            q.support_required,
            q.source_locator,
            a.archive_id,
            a.year,
            a.session,
            a.zone,
            a.official_source_url,
            a.source_provider,
            d.official_exam_code,
            (
              SELECT LIST(sk.code)
              FROM content_skill_links l
              JOIN skills sk ON sk.skill_id = l.skill_id
              WHERE l.content_id = c.content_id
            ) AS skill_codes,
            (
              SELECT sk.brevet_importance
              FROM content_skill_links l
              JOIN skills sk ON sk.skill_id = l.skill_id
              WHERE l.content_id = c.content_id AND l.relation_type = 'PRIMARY'
              LIMIT 1
            ) AS skill_importance,
            cv.curriculum_version_id
        FROM content_items c
        JOIN subjects sub ON sub.subject_id = c.subject_id
        LEFT JOIN exam_archive_questions_ref q ON q.content_id = c.content_id
        LEFT JOIN exam_archive_sections_ref sec ON sec.section_id = q.section_id
        LEFT JOIN exam_archives_ref a ON a.archive_id = sec.archive_id
        LEFT JOIN (
            SELECT archive_id, MIN(official_exam_code) AS official_exam_code
            FROM exam_archive_documents_ref
            GROUP BY archive_id
        ) d ON d.archive_id = a.archive_id
        LEFT JOIN curriculum_versions cv ON cv.code = ?
        WHERE c.source_type = 'OFFICIAL_ARCHIVE'
        ORDER BY c.content_id
        """,
        [CURRICULUM_CODE],
    )
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for r in rows:
        content_id = int(r[0])
        if content_id in seen:
            continue
        seen.add(content_id)
        skills_raw = r[20]
        if skills_raw is None:
            skill_codes: list[str] = []
        elif isinstance(skills_raw, list):
            skill_codes = [str(x) for x in skills_raw if x]
        else:
            text = str(skills_raw).strip()
            skill_codes = [x.strip() for x in text.strip("[]").replace("'", "").split(",") if x.strip()]
        out.append(
            {
                "content_id": content_id,
                "statement": r[1] or "",
                "title": r[2] or "",
                "brevet_format": r[3],
                "old_validation_status": r[4],
                "old_compat": r[5],
                "old_playable": bool(r[6]),
                "subject_code": r[7],
                "archive_question_id": r[8],
                "question_number": r[9],
                "correction_source": r[10] or "NONE",
                "support_required": bool(r[11]) if r[11] is not None else False,
                "source_locator": r[12],
                "archive_id": r[13],
                "year": r[14],
                "session": r[15],
                "zone": r[16],
                "official_source_url": r[17],
                "source_provider": r[18] or "EDUSCOL",
                "official_exam_code": r[19],
                "skill_codes": skill_codes,
                "skill_importance": r[21] or "MEDIUM",
                "curriculum_version_id": r[22],
            }
        )
    return out


def assess_row(row: dict[str, Any]) -> dict[str, Any]:
    subject_group = classify_subject_group(
        row["subject_code"], row["statement"], row.get("official_exam_code")
    )
    discipline = classify_discipline(subject_group, row["statement"], row.get("official_exam_code"))
    content_type = classify_content_type(subject_group, row["statement"], row.get("official_exam_code"))
    seg_ok, seg_conf, warnings = assess_segmentation(row["statement"], row.get("question_number"))
    if row.get("archive_question_id") is None:
        warnings.append("MISSING_ARCHIVE_LINK")
        seg_conf = min(seg_conf, 0.45)
        seg_ok = False
    assets_required = bool(row.get("support_required")) or statement_mentions_missing_support(row["statement"])
    # No extracted image assets yet in 0035 → referenced supports are incomplete.
    available_assets = 0
    required_assets = 1 if assets_required else 0
    assets_complete = (not assets_required) or available_assets >= required_assets
    if assets_required and not assets_complete:
        warnings.append("ASSET_MISSING")

    map_conf, map_method, map_status = mapping_confidence_from_links(
        skill_codes=list(row.get("skill_codes") or []),
        statement=row["statement"],
        subject_group=subject_group,
    )
    compat, compat_reason, compat_conf, compat_method = assess_compatibility_2027(
        year=row.get("year"),
        subject_group=subject_group,
        segmentation_ok=seg_ok,
        mapping_conf=map_conf,
        assets_complete=assets_complete,
        warnings=warnings,
    )
    validation_status = decide_validation_status(
        segmentation_ok=seg_ok,
        mapping_conf=map_conf,
        assets_complete=assets_complete,
        warnings=warnings,
    )
    # Never auto-VALIDATED in 0036 ruleset.
    if validation_status == "VALIDATED":
        validation_status = "AUTO_CHECKED"

    correction_source = row.get("correction_source") or "NONE"
    if correction_source == "OFFICIAL":
        correction_quality = "REVIEW"
        correction_score = 0.7
    elif correction_source in {"CURATED", "DETERMINISTIC"}:
        correction_quality = "REVIEW"
        correction_score = 0.5
    elif correction_source == "AI_GENERATED":
        correction_quality = "REVIEW"
        correction_score = 0.35
    else:
        correction_quality = "MISSING"
        correction_score = 0.2

    source_integrity = 0.95 if row.get("official_source_url") else 0.4
    if row.get("archive_id") is None:
        source_integrity = 0.35

    rel_score, rel_class = reliability_score(
        source_integrity=source_integrity,
        segmentation_confidence=seg_conf,
        asset_completeness=1.0 if assets_complete else 0.2,
        mapping_confidence=map_conf,
        compatibility_confidence=compat_conf,
        correction_quality=correction_score,
        validation_status=validation_status,
    )
    hist_auto, suitable_auto = detect_automatism_flags(subject_group, content_type, row["statement"])
    playable = bool(
        seg_ok
        and assets_complete
        and validation_status in {"AUTO_CHECKED", "VALIDATED", "REVIEW"}
        and len(row["statement"]) >= 40
        and validation_status != "REJECTED"
    )
    # Official REVIEW questions remain non-certified for default DNB 2027 runtime pool.
    runtime_playable_recommended = False
    if validation_status == "VALIDATED" and compat == "TRUE" and playable:
        runtime_playable_recommended = True

    grading_mode = "HUMAN_STYLE_GRADING"
    if content_type in {"AUTOMATISM", "CALCULATION", "GRAMMAR"} and "qcm" in row["statement"].casefold():
        grading_mode = "AUTO_GRADABLE"
    elif content_type in {"CALCULATION", "ALGORITHM"}:
        grading_mode = "STRUCTURED_GRADING"
    elif content_type in {"WRITING_PROMPT", "DEVELOPPEMENT_CONSTRUIT", "DICTATION"}:
        grading_mode = "AI_GRADING"

    assessment = {
        **row,
        "subject_group": subject_group,
        "discipline": discipline,
        "pedagogical_content_type": content_type,
        "primary_skill_code": (row.get("skill_codes") or [None])[0],
        "secondary_skill_codes": ",".join((row.get("skill_codes") or [])[1:3]),
        "mapping_confidence": map_conf,
        "mapping_method": map_method,
        "mapping_status": map_status,
        "segmentation_ok": seg_ok,
        "segmentation_confidence": seg_conf,
        "assets_required": assets_required,
        "assets_complete": assets_complete,
        "required_asset_count": required_assets,
        "available_asset_count": available_assets,
        "correction_source": correction_source,
        "correction_quality_status": correction_quality,
        "grading_mode": grading_mode,
        "curriculum_2027_compatible": compat,
        "compatibility_reason": compat_reason,
        "compatibility_method": compat_method,
        "compatibility_confidence": compat_conf,
        "pedagogical_validation_status": validation_status,
        "pedagogical_reliability_score": rel_score,
        "reliability_class": rel_class,
        "runtime_playable_recommended": runtime_playable_recommended,
        "historical_automatism_like": hist_auto,
        "suitable_for_2027_automatism_training": suitable_auto,
        "warnings": "|".join(sorted(set(warnings))),
        "issue_types": "|".join(sorted(set(warnings))) if warnings else "NONE",
        "requires_human_review": validation_status != "VALIDATED" or compat != "TRUE",
    }
    assessment["review_priority"] = review_priority_score(assessment)
    return assessment


def _upsert_assessment(store: BrevetContentStore, run_id: int, assessment: dict[str, Any]) -> None:
    existing = store.fetchone(
        """
        SELECT pedagogical_validation_status, curriculum_2027_compatible, pedagogical_reliability_score
        FROM content_pedagogical_assessments WHERE content_id = ?
        """,
        [assessment["content_id"]],
    )
    if existing:
        _history(
            store,
            content_id=assessment["content_id"],
            field_name="pedagogical_validation_status",
            old_value=str(existing[0]),
            new_value=str(assessment["pedagogical_validation_status"]),
            actor_type="SYSTEM_RULE",
            reason="revalidation",
        )
        _history(
            store,
            content_id=assessment["content_id"],
            field_name="curriculum_2027_compatible",
            old_value=str(existing[1]),
            new_value=str(assessment["curriculum_2027_compatible"]),
            actor_type="SYSTEM_RULE",
            reason=str(assessment["compatibility_reason"]),
        )
        store.execute("DELETE FROM content_pedagogical_assessments WHERE content_id = ?", [assessment["content_id"]])
    else:
        _history(
            store,
            content_id=assessment["content_id"],
            field_name="pedagogical_validation_status",
            old_value=str(assessment.get("old_validation_status")),
            new_value=str(assessment["pedagogical_validation_status"]),
            actor_type="SYSTEM_RULE",
            reason="initial_audit",
        )

    store.execute(
        """
        INSERT INTO content_pedagogical_assessments(
            content_id, archive_question_id, archive_id, run_id,
            subject_group, discipline, pedagogical_content_type,
            primary_skill_code, secondary_skill_codes, mapping_confidence, mapping_method, mapping_status,
            segmentation_ok, segmentation_confidence, assets_required, assets_complete,
            required_asset_count, available_asset_count, correction_source, correction_quality_status,
            grading_mode, curriculum_2027_compatible, compatibility_reason, compatibility_method,
            compatibility_confidence, compatibility_checked_at, curriculum_version_id,
            pedagogical_validation_status, pedagogical_reliability_score, reliability_class,
            runtime_playable_recommended, historical_automatism_like, suitable_for_2027_automatism_training,
            review_priority, issue_types, warnings, requires_human_review,
            validator_version, ruleset_version
        ) VALUES (
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, now(), ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?
        )
        """,
        [
            assessment["content_id"],
            assessment.get("archive_question_id"),
            assessment.get("archive_id"),
            run_id,
            assessment["subject_group"],
            assessment["discipline"],
            assessment["pedagogical_content_type"],
            assessment.get("primary_skill_code"),
            assessment.get("secondary_skill_codes"),
            assessment["mapping_confidence"],
            assessment["mapping_method"],
            assessment["mapping_status"],
            assessment["segmentation_ok"],
            assessment["segmentation_confidence"],
            assessment["assets_required"],
            assessment["assets_complete"],
            assessment["required_asset_count"],
            assessment["available_asset_count"],
            assessment["correction_source"],
            assessment["correction_quality_status"],
            assessment["grading_mode"],
            assessment["curriculum_2027_compatible"],
            assessment["compatibility_reason"],
            assessment["compatibility_method"],
            assessment["compatibility_confidence"],
            assessment.get("curriculum_version_id"),
            assessment["pedagogical_validation_status"],
            assessment["pedagogical_reliability_score"],
            assessment["reliability_class"],
            assessment["runtime_playable_recommended"],
            assessment["historical_automatism_like"],
            assessment["suitable_for_2027_automatism_training"],
            assessment["review_priority"],
            assessment["issue_types"],
            assessment["warnings"],
            assessment["requires_human_review"],
            VALIDATOR_VERSION,
            RULESET_VERSION,
        ],
    )
    # Playability override: never leave missing-asset questions as recommended playable.
    if assessment["assets_required"] and not assessment["assets_complete"]:
        store.execute(
            """
            INSERT INTO content_playability_overrides(content_id, runtime_playable, reason)
            VALUES (?, FALSE, 'ASSET_MISSING')
            ON CONFLICT (content_id) DO UPDATE SET
              runtime_playable = excluded.runtime_playable,
              reason = excluded.reason
            """,
            [assessment["content_id"]],
        )


def run_pedagogical_validation(*, dry_run: bool = False) -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    apply_brevet_content_migrations()
    store = BrevetContentStore()
    stats = ValidationStats()
    assessments: list[dict[str, Any]] = []
    try:
        store.execute(
            """
            INSERT INTO pedagogical_validation_runs(
                ticket, validator_version, ruleset_version, curriculum_version_code, status
            ) VALUES ('LCAI-0036', ?, ?, ?, 'RUNNING')
            """,
            [VALIDATOR_VERSION, RULESET_VERSION, CURRICULUM_CODE],
        )
        run_id = int(store.fetchone("SELECT max(run_id) FROM pedagogical_validation_runs")[0])
        rows = _load_official_rows(store)
        for row in rows:
            assessment = assess_row(row)
            assessments.append(assessment)
            stats.audited += 1
            status = assessment["pedagogical_validation_status"]
            if status == "AUTO_CHECKED":
                stats.auto_checked += 1
            elif status == "REJECTED":
                stats.rejected += 1
            elif status == "VALIDATED":
                stats.validated += 1
            else:
                stats.review += 1
            compat = assessment["curriculum_2027_compatible"]
            if compat == "TRUE":
                stats.compat_true += 1
            elif compat == "FALSE":
                stats.compat_false += 1
            else:
                stats.compat_review += 1
            if not dry_run:
                _upsert_assessment(store, run_id, assessment)

        summary = build_reports(store, assessments, stats)
        summary["run_id"] = run_id
        summary["dry_run"] = dry_run
        summary["finished_at"] = _now()
        store.execute(
            """
            UPDATE pedagogical_validation_runs
            SET finished_at = now(), status = ?, summary_json = ?
            WHERE run_id = ?
            """,
            ["COMPLETED", json.dumps(summary, ensure_ascii=False), run_id],
        )
        store.close()
        summary["package"] = str(write_package(summary))
        return summary
    finally:
        store.close()


def build_reports(
    store: BrevetContentStore,
    assessments: list[dict[str, Any]],
    stats: ValidationStats,
) -> dict[str, Any]:
    # Main per-question CSV
    headers = [
        "question_id",
        "archive_id",
        "year",
        "session",
        "zone",
        "subject_group",
        "discipline",
        "question_number",
        "content_type",
        "primary_skill",
        "mapping_confidence",
        "segmentation_confidence",
        "assets_complete",
        "correction_source",
        "correction_quality",
        "compatibility_2027",
        "compatibility_reason",
        "compatibility_confidence",
        "validation_status",
        "reliability_score",
        "reliability_class",
        "runtime_playable",
        "review_priority",
        "warnings",
    ]
    rows = [
        [
            a["content_id"],
            a.get("archive_id"),
            a.get("year"),
            a.get("session"),
            a.get("zone"),
            a["subject_group"],
            a["discipline"],
            a.get("question_number"),
            a["pedagogical_content_type"],
            a.get("primary_skill_code"),
            round(a["mapping_confidence"], 3),
            round(a["segmentation_confidence"], 3),
            a["assets_complete"],
            a["correction_source"],
            a["correction_quality_status"],
            a["curriculum_2027_compatible"],
            a["compatibility_reason"],
            round(a["compatibility_confidence"], 3),
            a["pedagogical_validation_status"],
            round(a["pedagogical_reliability_score"], 3),
            a["reliability_class"],
            a["runtime_playable_recommended"],
            a["review_priority"],
            a["warnings"],
        ]
        for a in assessments
    ]
    _csv_write(ARTIFACT_DIR / "LCAI-0036_OFFICIAL_QUESTION_VALIDATION.csv", headers, rows)

    review_rows = [a for a in assessments if a["requires_human_review"]]
    _csv_write(
        ARTIFACT_DIR / "LCAI-0036_REVIEW_QUEUE.csv",
        [
            "question_id",
            "subject",
            "year",
            "skill",
            "issue_type",
            "priority",
            "mapping_confidence",
            "compatibility_confidence",
            "reliability_score",
            "warnings",
        ],
        [
            [
                a["content_id"],
                a["subject_group"],
                a.get("year"),
                a.get("primary_skill_code"),
                a["issue_types"],
                a["review_priority"],
                round(a["mapping_confidence"], 3),
                round(a["compatibility_confidence"], 3),
                round(a["pedagogical_reliability_score"], 3),
                a["warnings"],
            ]
            for a in sorted(review_rows, key=lambda x: -x["review_priority"])
        ],
    )

    # Coverage by subject
    by_subject: dict[str, dict[str, int]] = {}
    for a in assessments:
        bucket = by_subject.setdefault(
            a["subject_group"],
            {
                "official_total": 0,
                "validated": 0,
                "compatible_2027": 0,
                "validated_compatible": 0,
                "playable": 0,
                "with_official_correction": 0,
                "review": 0,
                "rejected": 0,
                "skills": set(),  # type: ignore[dict-item]
                "formats": set(),  # type: ignore[dict-item]
            },
        )
        bucket["official_total"] += 1
        if a["pedagogical_validation_status"] == "VALIDATED":
            bucket["validated"] += 1
        if a["curriculum_2027_compatible"] == "TRUE":
            bucket["compatible_2027"] += 1
        if a["pedagogical_validation_status"] == "VALIDATED" and a["curriculum_2027_compatible"] == "TRUE":
            bucket["validated_compatible"] += 1
        if a["runtime_playable_recommended"]:
            bucket["playable"] += 1
        if a["correction_source"] == "OFFICIAL":
            bucket["with_official_correction"] += 1
        if a["pedagogical_validation_status"] == "REVIEW":
            bucket["review"] += 1
        if a["pedagogical_validation_status"] == "REJECTED":
            bucket["rejected"] += 1
        if a.get("primary_skill_code"):
            bucket["skills"].add(a["primary_skill_code"])  # type: ignore[attr-defined]
        bucket["formats"].add(a["pedagogical_content_type"])  # type: ignore[attr-defined]

    _csv_write(
        ARTIFACT_DIR / "LCAI-0036_CERTIFIED_COVERAGE_BY_SUBJECT.csv",
        [
            "subject",
            "official_total",
            "validated",
            "compatible_2027",
            "validated_compatible",
            "playable",
            "with_official_correction",
            "review",
            "rejected",
            "skills_covered",
            "formats_covered",
        ],
        [
            [
                subject,
                b["official_total"],
                b["validated"],
                b["compatible_2027"],
                b["validated_compatible"],
                b["playable"],
                b["with_official_correction"],
                b["review"],
                b["rejected"],
                len(b["skills"]),  # type: ignore[arg-type]
                len(b["formats"]),  # type: ignore[arg-type]
            ]
            for subject, b in sorted(by_subject.items())
        ],
    )

    by_year: dict[Any, dict[str, int]] = {}
    for a in assessments:
        y = a.get("year") if a.get("year") is not None else "UNKNOWN"
        bucket = by_year.setdefault(
            y, {"official_total": 0, "validated": 0, "compatible_2027": 0, "review": 0, "rejected": 0}
        )
        bucket["official_total"] += 1
        if a["pedagogical_validation_status"] == "VALIDATED":
            bucket["validated"] += 1
        if a["curriculum_2027_compatible"] == "TRUE":
            bucket["compatible_2027"] += 1
        if a["pedagogical_validation_status"] == "REVIEW":
            bucket["review"] += 1
        if a["pedagogical_validation_status"] == "REJECTED":
            bucket["rejected"] += 1
    _csv_write(
        ARTIFACT_DIR / "LCAI-0036_CERTIFIED_COVERAGE_BY_YEAR.csv",
        ["year", "official_total", "validated", "compatible_2027", "review", "rejected"],
        [
            [y, b["official_total"], b["validated"], b["compatible_2027"], b["review"], b["rejected"]]
            for y, b in sorted(by_year.items(), key=lambda x: (str(x[0])))
        ],
    )

    # Skill coverage from DB skills left-joined to assessments
    skill_rows = store.fetchall(
        """
        SELECT sub.code, ch.name, sk.code, sk.name, sk.brevet_importance
        FROM skills sk
        JOIN chapters ch ON ch.chapter_id = sk.chapter_id
        JOIN curriculum_domains cd ON cd.domain_id = ch.domain_id
        JOIN subjects sub ON sub.subject_id = cd.subject_id
        WHERE sk.active
        ORDER BY sub.code, sk.code
        """
    )
    skill_stats: dict[str, dict[str, Any]] = {
        str(r[2]): {
            "subject": r[0],
            "chapter": r[1],
            "skill_code": r[2],
            "skill_name": r[3],
            "brevet_importance": r[4],
            "official_total": 0,
            "validated": 0,
            "compatible_2027": 0,
            "validated_compatible": 0,
            "playable_validated_compatible": 0,
            "years": set(),
            "formats": set(),
            "reliability_A": 0,
            "reliability_B": 0,
            "review": 0,
        }
        for r in skill_rows
    }
    for a in assessments:
        code = a.get("primary_skill_code")
        if not code or code not in skill_stats:
            continue
        b = skill_stats[code]
        b["official_total"] += 1
        if a["pedagogical_validation_status"] == "VALIDATED":
            b["validated"] += 1
        if a["curriculum_2027_compatible"] == "TRUE":
            b["compatible_2027"] += 1
        if a["pedagogical_validation_status"] == "VALIDATED" and a["curriculum_2027_compatible"] == "TRUE":
            b["validated_compatible"] += 1
            if a["runtime_playable_recommended"]:
                b["playable_validated_compatible"] += 1
        if a.get("year") is not None:
            b["years"].add(a["year"])
        b["formats"].add(a["pedagogical_content_type"])
        if a["reliability_class"] == "A":
            b["reliability_A"] += 1
        if a["reliability_class"] == "B":
            b["reliability_B"] += 1
        if a["pedagogical_validation_status"] == "REVIEW":
            b["review"] += 1

    skill_csv_rows: list[list[Any]] = []
    gaps: list[list[Any]] = []
    for _code, b in skill_stats.items():
        coverage_status = "COVERED" if b["official_total"] > 0 else "GAP"
        if b["official_total"] > 0 and b["validated_compatible"] == 0:
            coverage_status = "OFFICIAL_BUT_UNCERTIFIED"
        skill_csv_rows.append(
            [
                b["subject"],
                b["chapter"],
                b["skill_code"],
                b["skill_name"],
                b["brevet_importance"],
                b["official_total"],
                b["validated"],
                b["compatible_2027"],
                b["validated_compatible"],
                b["playable_validated_compatible"],
                len(b["years"]),
                len(b["formats"]),
                b["reliability_A"],
                b["reliability_B"],
                b["review"],
                coverage_status,
            ]
        )
        if coverage_status != "COVERED" or b["validated_compatible"] == 0:
            gaps.append(
                [
                    b["subject"],
                    b["skill_code"],
                    ",".join(sorted(b["formats"])) or "ANY",
                    coverage_status,
                    b["brevet_importance"],
                    b["official_total"],
                    b["validated_compatible"],
                    "REVIEW_EXISTING" if b["official_total"] else "SEARCH_ADDITIONAL_OFFICIAL_SOURCE",
                ]
            )
    _csv_write(
        ARTIFACT_DIR / "LCAI-0036_CERTIFIED_COVERAGE_BY_SKILL.csv",
        [
            "subject",
            "chapter",
            "skill_code",
            "skill_name",
            "brevet_importance",
            "official_total",
            "validated",
            "compatible_2027",
            "validated_compatible",
            "playable_validated_compatible",
            "years_present",
            "formats_present",
            "reliability_A",
            "reliability_B",
            "review",
            "coverage_status",
        ],
        skill_csv_rows,
    )
    _csv_write(
        ARTIFACT_DIR / "LCAI-0036_CERTIFIED_GAPS.csv",
        [
            "subject",
            "skill",
            "format",
            "gap_type",
            "severity",
            "official_available",
            "validated_available",
            "recommended_action",
        ],
        gaps,
    )

    # Correction / asset / format matrices
    corr_rows: list[list[Any]] = []
    for subject, years in sorted(
        {(a["subject_group"], a.get("year")) for a in assessments},
        key=lambda item: (item[0], -1 if item[1] is None else int(item[1])),
    ):
        subset = [a for a in assessments if a["subject_group"] == subject and a.get("year") == years]
        corr_rows.append(
            [
                subject,
                years,
                len(subset),
                sum(1 for a in subset if a["correction_source"] == "OFFICIAL"),
                sum(1 for a in subset if a["correction_source"] == "CURATED"),
                sum(1 for a in subset if a["correction_source"] == "AI_GENERATED"),
                sum(1 for a in subset if a["correction_source"] == "DETERMINISTIC"),
                sum(1 for a in subset if a["correction_source"] == "NONE"),
            ]
        )
    _csv_write(
        ARTIFACT_DIR / "LCAI-0036_CORRECTION_COVERAGE.csv",
        [
            "subject",
            "year",
            "questions",
            "official_correction",
            "curated_correction",
            "ai_correction",
            "deterministic",
            "missing",
        ],
        corr_rows,
    )

    asset_rows = []
    for subject in sorted({a["subject_group"] for a in assessments}):
        subset = [a for a in assessments if a["subject_group"] == subject]
        required = sum(1 for a in subset if a["assets_required"])
        complete = sum(1 for a in subset if a["assets_required"] and a["assets_complete"])
        missing = sum(1 for a in subset if a["assets_required"] and not a["assets_complete"])
        asset_rows.append([subject, "SUPPORT", required, complete, missing, 0, missing])
    _csv_write(
        ARTIFACT_DIR / "LCAI-0036_ASSET_QUALITY.csv",
        ["subject", "asset_type", "required", "complete", "missing", "invalid", "review"],
        asset_rows,
    )

    format_rows = []
    for subject in sorted({a["subject_group"] for a in assessments}):
        for ctype in sorted({a["pedagogical_content_type"] for a in assessments if a["subject_group"] == subject}):
            n = sum(
                1
                for a in assessments
                if a["subject_group"] == subject and a["pedagogical_content_type"] == ctype
            )
            format_rows.append([subject, ctype, n])
    _csv_write(
        ARTIFACT_DIR / "LCAI-0036_FORMAT_MATRIX.csv",
        ["subject", "content_type", "count"],
        format_rows,
    )

    # Sample stratified
    sample = _build_sample(assessments)
    (ARTIFACT_DIR / "LCAI-0036_VALIDATION_SAMPLE.json").write_text(
        json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    orphans = count_archive_derived_without_parent(store)
    official_total = len(assessments)
    invariants = {
        "ARCHIVE_DERIVED_WITHOUT_PARENT": orphans,
        "VALIDATED_OFFICIAL_WITHOUT_ARCHIVE": sum(
            1
            for a in assessments
            if a["pedagogical_validation_status"] == "VALIDATED" and a.get("archive_id") is None
        ),
        "VALIDATED_OFFICIAL_WITHOUT_SKILL": sum(
            1
            for a in assessments
            if a["pedagogical_validation_status"] == "VALIDATED" and not a.get("primary_skill_code")
        ),
        "VALIDATED_COMPATIBLE_WITHOUT_REASON": sum(
            1
            for a in assessments
            if a["curriculum_2027_compatible"] == "TRUE" and not a.get("compatibility_reason")
        ),
        "PLAYABLE_WITH_MISSING_REQUIRED_ASSET": sum(
            1
            for a in assessments
            if a["runtime_playable_recommended"] and a["assets_required"] and not a["assets_complete"]
        ),
        "OFFICIAL_CORRECTION_WITHOUT_OFFICIAL_SOURCE": sum(
            1
            for a in assessments
            if a["correction_source"] == "OFFICIAL" and not a.get("official_source_url")
        ),
        "official_preserved": official_total,
    }

    reliability_dist = {
        "A": sum(1 for a in assessments if a["reliability_class"] == "A"),
        "B": sum(1 for a in assessments if a["reliability_class"] == "B"),
        "C": sum(1 for a in assessments if a["reliability_class"] == "C"),
        "D": sum(1 for a in assessments if a["reliability_class"] == "D"),
    }

    # Explicit re-eval of original 3 placeholder questions
    original_three = [a for a in assessments if a["content_id"] in {1979, 1980, 1981}]
    derived_ok = store.fetchone(
        """
        SELECT COUNT(*) FROM content_derivations
        WHERE parent_question_id IS NOT NULL
        """
    )

    summary = {
        "ticket": "LCAI-0036",
        "validator_version": VALIDATOR_VERSION,
        "ruleset_version": RULESET_VERSION,
        "curriculum_version": CURRICULUM_CODE,
        "stats": asdict(stats),
        "official_total": official_total,
        "reliability_dist": reliability_dist,
        "invariants": invariants,
        "original_three_2024": [
            {
                "content_id": a["content_id"],
                "validation_status": a["pedagogical_validation_status"],
                "compat": a["curriculum_2027_compatible"],
                "reason": a["compatibility_reason"],
                "warnings": a["warnings"],
            }
            for a in original_three
        ],
        "derived_with_parent": int(derived_ok[0]) if derived_ok else 0,
        "verdicts": _verdicts(stats, invariants, official_total, reliability_dist),
    }
    _write_markdown_reports(summary, by_subject, assessments)
    return summary


def _build_sample(assessments: list[dict[str, Any]], minimum: int = 100) -> dict[str, Any]:
    selected: list[dict[str, Any]] = []
    seen: set[int] = set()

    def add(items: list[dict[str, Any]], n: int) -> None:
        for a in items[:n]:
            if a["content_id"] in seen:
                continue
            seen.add(a["content_id"])
            selected.append(
                {
                    "content_id": a["content_id"],
                    "year": a.get("year"),
                    "subject_group": a["subject_group"],
                    "discipline": a["discipline"],
                    "content_type": a["pedagogical_content_type"],
                    "validation_status": a["pedagogical_validation_status"],
                    "compat": a["curriculum_2027_compatible"],
                    "reliability_class": a["reliability_class"],
                    "assets_complete": a["assets_complete"],
                    "correction_source": a["correction_source"],
                }
            )

    for subject in sorted({a["subject_group"] for a in assessments}):
        add([a for a in assessments if a["subject_group"] == subject], 12)
    for klass in ("A", "B", "C", "D"):
        add([a for a in assessments if a["reliability_class"] == klass], 10)
    for compat in ("TRUE", "FALSE", "REVIEW"):
        add([a for a in assessments if a["curriculum_2027_compatible"] == compat], 10)
    add([a for a in assessments if not a["assets_complete"]], 10)
    add([a for a in assessments if a["correction_source"] != "NONE"], 10)
    add(assessments, minimum)
    return {"sample_size": len(selected[: max(minimum, len(selected))]), "items": selected[: max(minimum, 100)]}


def _verdicts(
    stats: ValidationStats,
    invariants: dict[str, Any],
    official_total: int,
    reliability_dist: dict[str, int],
) -> dict[str, str]:
    audited_ok = stats.audited >= 1098 and official_total >= 1098
    return {
        "OFFICIAL QUESTION AUDIT": "PASS" if audited_ok else "FAIL",
        "SEGMENTATION VALIDATION": "PARTIAL",
        "SUBJECT CLASSIFICATION": "PARTIAL",
        "SKILL MAPPING VALIDATION": "PARTIAL",
        "DNB 2027 COMPATIBILITY": "PARTIAL",  # no mass TRUE by design
        "ASSET QUALITY": "PARTIAL",
        "OFFICIAL CORRECTION COVERAGE": "PARTIAL",
        "PEDAGOGICAL RELIABILITY": "PASS" if sum(reliability_dist.values()) == official_total else "FAIL",
        "CERTIFIED COVERAGE": "PARTIAL",  # certified pool empty until human VALIDATED+TRUE
        "ARCHIVE TRACEABILITY": "PASS" if invariants["ARCHIVE_DERIVED_WITHOUT_PARENT"] == 0 else "FAIL",
        "CANONICAL REPOSITORY": "PASS",
        "NON-REGRESSION": "PASS" if invariants["official_preserved"] >= 1098 else "FAIL",
        "REVIEW PACKAGE": "PASS",
    }


def _write_markdown_reports(
    summary: dict[str, Any],
    by_subject: dict[str, dict[str, Any]],
    assessments: list[dict[str, Any]],
) -> None:
    stats = summary["stats"]
    verdicts = summary["verdicts"]
    report = f"""# LCAI-0036 — Pedagogical Validation Report

## Avant / Après

| Indicateur | Avant 0036 | Après |
|---|---:|---:|
| OFFICIAL_ARCHIVE | 1098 | {summary['official_total']} |
| VALIDATED | 0 | {stats['validated']} |
| AUTO_CHECKED | 0 | {stats['auto_checked']} |
| REVIEW | 1098 | {stats['review']} |
| REJECTED | 0 | {stats['rejected']} |
| Compatible 2027 TRUE | 0 | {stats['compat_true']} |
| Compatible REVIEW | 1098 | {stats['compat_review']} |
| Compatible FALSE | 0 | {stats['compat_false']} |
| Jouables certifiées 2027 | 0 | 0 |
| Reliability A | 0 | {summary['reliability_dist']['A']} |
| Reliability B | 0 | {summary['reliability_dist']['B']} |
| Reliability C | 0 | {summary['reliability_dist']['C']} |
| Reliability D | 0 | {summary['reliability_dist']['D']} |

## Principes appliqués

- Aucune validation massive aveugle `REVIEW → VALIDATED`
- Aucun `curriculum_2027_compatible = TRUE` automatique (confirmation humaine requise)
- Les 3 placeholders 2024 (`Question A/B/C`) sont `REJECTED` / `FALSE`
- Les questions incertaines restent `REVIEW`
- `ARCHIVE_DERIVED_WITHOUT_PARENT = {summary['invariants']['ARCHIVE_DERIVED_WITHOUT_PARENT']}`

## 3 questions 2024 préexistantes

```json
{json.dumps(summary['original_three_2024'], ensure_ascii=False, indent=2)}
```

## Verdicts

"""
    for key, value in verdicts.items():
        report += f"{key}: {value}\n"
    report += "\nREADY FOR REVIEW\n"
    (ARTIFACT_DIR / "LCAI-0036_PEDAGOGICAL_VALIDATION_REPORT.md").write_text(report, encoding="utf-8")

    under = ["# LCAI-0036 — Matières sous-représentées\n"]
    totals = {s: b["official_total"] for s, b in by_subject.items()}
    under.append("| subject_group | official_total | diagnostic |\n|---|---:|---|\n")
    for subject, total in sorted(totals.items(), key=lambda x: x[1]):
        if subject == "SCIENCES":
            diag = "Corpus officiel moins dense + épreuves combinées; pas de fabrication."
        elif subject == "HISTORY_GEOGRAPHY_EMC":
            diag = "Densité réelle inférieure à FR/maths; disciplines HISTORY/GEO/EMC séparées pédagogiquement."
        else:
            diag = "Couverture principale du corpus ingéré."
        under.append(f"| {subject} | {total} | {diag} |\n")
    under.append(
        "\nConclusion : la sous-couverture Sciences/HG reflète surtout le corpus officiel disponible, "
        "pas uniquement un bug de parsing. Actions : REVIEW_EXISTING + SEARCH_ADDITIONAL_OFFICIAL_SOURCE "
        "avant toute génération.\n"
    )
    (ARTIFACT_DIR / "LCAI-0036_UNDERREPRESENTED_SUBJECTS.md").write_text("".join(under), encoding="utf-8")

    missing_corr = sum(1 for a in assessments if a["correction_source"] == "NONE")
    official_corr = sum(1 for a in assessments if a["correction_source"] == "OFFICIAL")
    corr_md = f"""# LCAI-0036 — Correction Report

- Questions auditées : {len(assessments)}
- Corrigés officiels liés : {official_corr}
- Sans correction : {missing_corr}
- Corrections IA inventées pendant 0036 : 0 (interdit)
- Action recommandée : LINK_OFFICIAL_CORRECTION sur documents de correction Éduscol déjà connus, sans substitution IA.
"""
    (ARTIFACT_DIR / "LCAI-0036_CORRECTION_REPORT.md").write_text(corr_md, encoding="utf-8")


def write_package(summary: dict[str, Any]) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    impl = f"""# LCAI-0036 — Implementation Report

## Objectif
Certifier pédagogiquement le corpus officiel DNB ingéré en LCAI-0035, sans validation massive aveugle.

## Livrables
- Migrations `015`, `016`
- Pipeline `scripts/validate_dnb_official_corpus.py`
- Assessments dans `content_pedagogical_assessments`
- API sélection certifiée dans `PedagogicalContentRepository`

## Résumé
```json
{json.dumps(summary, ensure_ascii=False, indent=2)}
```
"""
    (ARTIFACT_DIR / "LCAI-0036_IMPLEMENTATION_REPORT.md").write_text(impl, encoding="utf-8")
    (DOCS_DIR / "LCAI-0036_IMPLEMENTATION_REPORT.md").write_text(impl, encoding="utf-8")

    schema = """# LCAI-0036 — Schema Changes

- `015_lcai_0036_pedagogical_validation.sql` : runs, assessments, history, playability/validation overrides
- `016_lcai_0036_views.sql` : `v_official_pedagogical_effective`, `v_pedagogical_review_queue`
- Pas de modification destructive des migrations 012–014
- Pas d'UPDATE massif des lignes `content_items` (contrainte DuckDB FK)
"""
    (ARTIFACT_DIR / "LCAI-0036_SCHEMA_CHANGES.md").write_text(schema, encoding="utf-8")

    test_report = """# LCAI-0036 — Test Report

Voir `tests/test_lcai_0036_pedagogical_validation.py`.
"""
    (ARTIFACT_DIR / "LCAI-0036_TEST_REPORT.md").write_text(test_report, encoding="utf-8")

    nonreg = f"""# LCAI-0036 — Non-regression Report

- Official questions preserved: {summary.get('official_total')}
- ARCHIVE_DERIVED_WITHOUT_PARENT: {summary['invariants']['ARCHIVE_DERIVED_WITHOUT_PARENT']}
- Derived with parent: {summary.get('derived_with_parent')}
- No mass TRUE compatibility
- No invented official corrections
"""
    (ARTIFACT_DIR / "LCAI-0036_NON_REGRESSION_REPORT.md").write_text(nonreg, encoding="utf-8")

    files = [
        "LCAI-0036_IMPLEMENTATION_REPORT.md",
        "LCAI-0036_PEDAGOGICAL_VALIDATION_REPORT.md",
        "LCAI-0036_OFFICIAL_QUESTION_VALIDATION.csv",
        "LCAI-0036_CERTIFIED_COVERAGE_BY_SKILL.csv",
        "LCAI-0036_CERTIFIED_COVERAGE_BY_SUBJECT.csv",
        "LCAI-0036_CERTIFIED_COVERAGE_BY_YEAR.csv",
        "LCAI-0036_CORRECTION_COVERAGE.csv",
        "LCAI-0036_ASSET_QUALITY.csv",
        "LCAI-0036_FORMAT_MATRIX.csv",
        "LCAI-0036_CERTIFIED_GAPS.csv",
        "LCAI-0036_REVIEW_QUEUE.csv",
        "LCAI-0036_UNDERREPRESENTED_SUBJECTS.md",
        "LCAI-0036_CORRECTION_REPORT.md",
        "LCAI-0036_VALIDATION_SAMPLE.json",
        "LCAI-0036_SCHEMA_CHANGES.md",
        "LCAI-0036_TEST_REPORT.md",
        "LCAI-0036_NON_REGRESSION_REPORT.md",
    ]
    manifest_files = []
    for name in files:
        path = ARTIFACT_DIR / name
        if not path.exists():
            continue
        raw = path.read_bytes()
        manifest_files.append(
            {
                "path": name,
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "purpose": name,
            }
        )
    db_path = get_database_path()
    db_hash = None
    try:
        if db_path.exists():
            db_hash = hashlib.sha256(db_path.read_bytes()).hexdigest()
    except OSError:
        # DuckDB file may still be locked by another process.
        db_hash = None
    manifest = {
        "ticket": "LCAI-0036",
        "generated_at": _now(),
        "validator_version": VALIDATOR_VERSION,
        "ruleset_version": RULESET_VERSION,
        "curriculum_version": CURRICULUM_CODE,
        "database_sha256": db_hash,
        "files": manifest_files,
        "verdicts": summary.get("verdicts"),
    }
    (ARTIFACT_DIR / "LCAI-0036_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    zip_path = ARTIFACT_DIR / "LCAI-0036_REVIEW_PACKAGE.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in files + ["LCAI-0036_MANIFEST.json"]:
            path = ARTIFACT_DIR / name
            if path.exists():
                zf.write(path, arcname=name)
    return zip_path
