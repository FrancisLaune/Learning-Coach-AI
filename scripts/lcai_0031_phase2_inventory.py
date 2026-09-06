"""LCAI-0031 Phase 2 — inventory and classify existing V2 content (read/report)."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from core.config import PROJECT_ROOT, get_v2_database_path
from domain.dnb.config import (
    CONTINUOUS_ASSESSMENT_ONLY_SUBJECTS,
    DNB_TERMINAL_SUBJECTS,
    PRIMARY_USER_GRADE_CODE,
    REMEDIATION_GRADE_CODES,
)
from infrastructure.database.v2 import connect_v2

EXPORT_DIR = PROJECT_ROOT / "docs" / "phase6" / "LCAI-0031" / "exports"


@dataclass(frozen=True, slots=True)
class GradeInventoryRow:
    grade_code: str
    product_role: str | None
    chapters: int
    skills: int
    production_content: int
    classification: str


@dataclass(frozen=True, slots=True)
class SubjectInventoryRow:
    subject_code: str
    assessment_role: str | None
    chapters_3e: int
    skills_3e: int
    production_3e: int
    classification: str


def _classify_grade(code: str) -> str:
    if code == PRIMARY_USER_GRADE_CODE:
        return "KEEP_TERMINAL"
    if code in REMEDIATION_GRADE_CODES:
        return "ARCHIVE_PREREQUISITE"
    return "DEPRECATE_OUT_OF_SCOPE"


def _classify_subject(code: str) -> str:
    if code in DNB_TERMINAL_SUBJECTS:
        return "MIGRATE_TERMINAL"
    if code in CONTINUOUS_ASSESSMENT_ONLY_SUBJECTS:
        return "KEEP_CONTINUOUS_ONLY"
    return "REVIEW"


def inventory_database(database_path: Path | None = None) -> dict[str, object]:
    path = database_path or get_v2_database_path()
    connection = connect_v2(path, read_only=True)
    try:
        grade_rows = connection.execute(
            """
            SELECT sl.code,
                   sl.product_role,
                   (SELECT COUNT(*) FROM curriculum_chapters cc
                    WHERE cc.grade_level_id = sl.id AND cc.status = 'approved') AS chapters,
                   (SELECT COUNT(*) FROM curriculum_skill_details csd
                    JOIN curriculum_chapters cc ON cc.id = csd.chapter_id
                    WHERE cc.grade_level_id = sl.id AND csd.status = 'approved') AS skills,
                   (SELECT COUNT(*) FROM production_learning_catalog plc
                    WHERE plc.grade_code = sl.code) AS production_content
            FROM school_levels sl
            WHERE sl.code LIKE 'FR-%'
            ORDER BY sl.rank DESC
            """
        ).fetchall()
        grades = [
            GradeInventoryRow(
                grade_code=str(row[0]),
                product_role=None if row[1] is None else str(row[1]),
                chapters=int(row[2] or 0),
                skills=int(row[3] or 0),
                production_content=int(row[4] or 0),
                classification=_classify_grade(str(row[0])),
            )
            for row in grade_rows
        ]

        subject_rows = connection.execute(
            """
            SELECT s.code,
                   s.assessment_role,
                   COUNT(DISTINCT CASE WHEN sl.code = 'FR-3E' AND cc.status = 'approved' THEN cc.id END),
                   COUNT(DISTINCT CASE WHEN sl.code = 'FR-3E' AND csd.status = 'approved' THEN csd.skill_id END),
                   (SELECT COUNT(*) FROM production_learning_catalog plc
                    WHERE plc.subject_id = s.id AND plc.grade_code = 'FR-3E')
            FROM subjects s
            LEFT JOIN curriculum_chapters cc ON cc.subject_id = s.id
            LEFT JOIN school_levels sl ON sl.id = cc.grade_level_id
            LEFT JOIN curriculum_skill_details csd ON csd.chapter_id = cc.id
            WHERE s.archived_at IS NULL
            GROUP BY s.id, s.code, s.assessment_role
            ORDER BY s.code
            """
        ).fetchall()
        subjects = [
            SubjectInventoryRow(
                subject_code=str(row[0]),
                assessment_role=None if row[1] is None else str(row[1]),
                chapters_3e=int(row[2] or 0),
                skills_3e=int(row[3] or 0),
                production_3e=int(row[4] or 0),
                classification=_classify_subject(str(row[0])),
            )
            for row in subject_rows
        ]

        curriculum_version = connection.execute(
            "SELECT code, status FROM curriculum_versions WHERE code = 'FR_3E_2027_V1'"
        ).fetchone()
        link = connection.execute(
            """
            SELECT b.code, b.version, c.code, ppl.link_role
            FROM program_product_links ppl
            JOIN programs b ON b.id = ppl.product_program_id
            JOIN programs c ON c.id = ppl.curriculum_program_id
            """
        ).fetchall()
        caps = connection.execute("SELECT COUNT(*) FROM subject_dnb_capabilities").fetchone()
        class_counts = Counter(item.classification for item in grades)
        subject_counts = Counter(item.classification for item in subjects)
    finally:
        connection.close()

    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "database": str(path),
        "curriculum_version": None
        if curriculum_version is None
        else {"code": str(curriculum_version[0]), "status": str(curriculum_version[1])},
        "program_links": [
            {
                "product": f"{row[0]}/{row[1]}",
                "curriculum": str(row[2]),
                "role": str(row[3]),
            }
            for row in link
        ],
        "subject_capabilities_rows": int(caps[0] if caps else 0),
        "grades": [asdict(item) for item in grades],
        "subjects": [asdict(item) for item in subjects],
        "grade_classification_counts": dict(class_counts),
        "subject_classification_counts": dict(subject_counts),
        "totals": {
            "chapters_3e": next((g.chapters for g in grades if g.grade_code == "FR-3E"), 0),
            "skills_3e": next((g.skills for g in grades if g.grade_code == "FR-3E"), 0),
            "production_3e": next((g.production_content for g in grades if g.grade_code == "FR-3E"), 0),
            "production_remediation": sum(
                g.production_content for g in grades if g.classification == "ARCHIVE_PREREQUISITE"
            ),
            "production_languages_3e": sum(
                s.production_3e for s in subjects if s.classification == "KEEP_CONTINUOUS_ONLY"
            ),
        },
        "known_gaps": [
            "TECHNOLOGY: 0 chapters / 0 production on FR-3E (content debt, not schema).",
            "prior_grade_remediation / exam_preparation edges still at 0 in curriculum_skill_relations.",
            "Curriculum authored under FR-CYCLE4-3E; BREVET/2027 linked via program_product_links.",
        ],
    }


def write_inventory_exports(payload: dict[str, object] | None = None) -> Path:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    data = payload or inventory_database()
    target = EXPORT_DIR / "LCAI-0031_PHASE2_CONTENT_INVENTORY.json"
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def populate_content_classifications(database_path: Path | None = None) -> int:
    """Idempotent classification rows for production catalog (no content mutation)."""
    path = database_path or get_v2_database_path()
    connection = connect_v2(path)
    try:
        rows = connection.execute(
            """
            SELECT plc.content_id, plc.grade_code, s.code
            FROM production_learning_catalog plc
            JOIN subjects s ON s.id = plc.subject_id
            WHERE plc.grade_code LIKE 'FR-%'
            """
        ).fetchall()
        inserted = 0
        for content_id, grade_code, subject_code in rows:
            grade = str(grade_code)
            subject = str(subject_code)
            if grade == PRIMARY_USER_GRADE_CODE and subject in DNB_TERMINAL_SUBJECTS:
                classification, reason = "MIGRATE", "FR-3E terminal DNB content"
            elif grade == PRIMARY_USER_GRADE_CODE and subject in CONTINUOUS_ASSESSMENT_ONLY_SUBJECTS:
                classification, reason = "KEEP", "FR-3E continuous assessment (languages)"
            elif grade in REMEDIATION_GRADE_CODES:
                classification, reason = "ARCHIVE", "Prior-grade content retained for remediation"
            else:
                classification, reason = "DEPRECATE", "Out of product scope"
            connection.execute(
                """
                INSERT INTO content_migration_classifications(
                    content_id, grade_code, subject_code, classification, reason
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (content_id, grade_code) DO UPDATE SET
                    subject_code = EXCLUDED.subject_code,
                    classification = EXCLUDED.classification,
                    reason = EXCLUDED.reason,
                    classified_at = now()
                """,
                [int(content_id), grade, subject, classification, reason],
            )
            inserted += 1
        return inserted
    finally:
        connection.close()


def main() -> None:
    classified = populate_content_classifications()
    path = write_inventory_exports()
    print(f"Classified {classified} content rows; wrote {path}")


if __name__ == "__main__":
    main()
