"""LCAI-0018 Phase 0 audit: full 4e coverage across all configured subjects."""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb

from core.config import get_v2_database_path
from domain.unified_experience.models import (
    AssignmentType,
    DifficultyMode,
    HomeworkRequest,
    SubjectHomeworkAvailability,
)
from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository
from services.content.homework_availability import HomeworkAvailabilityService
from services.unified_experience import HomeworkService

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "phase3"
EXPORTS = DOCS / "exports"
QUALITY = ROOT / "resources" / "content" / "quality"
GRADE = "FR-4E"
PRIORITY_SUBJECTS = ("ENGLISH", "PHYSICS_CHEMISTRY", "FRENCH", "MATHEMATICS")
SUBJECT_LABELS = {
    "ENGLISH": "Anglais",
    "PHYSICS_CHEMISTRY": "Physique-Chimie",
    "FRENCH": "Français",
    "MATHEMATICS": "Mathématiques",
    "GEOGRAPHY": "Géographie",
    "HISTORY": "Histoire",
    "SVT": "SVT",
    "EMC": "EMC",
    "SPANISH": "Espagnol",
    "TECHNOLOGY": "Technologie",
    "ARTS": "Arts plastiques",
    "MUSIC": "Éducation musicale",
    "PE": "EPS",
    "LATIN": "Latin",
}


def connect_readonly() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(get_v2_database_path()), read_only=True)


def load_quality_index() -> dict[tuple[str, str, str, str, int], dict[str, object]]:
    results = json.loads((QUALITY / "lcai_0012d_quality_results.json").read_text(encoding="utf-8"))
    index: dict[tuple[str, str, str, str, int], dict[str, object]] = {}
    for item in results:
        if item.get("grade") != GRADE:
            continue
        key = (
            str(item.get("subject")),
            str(item.get("chapter")),
            str(item.get("skill")),
            str(item.get("content_type")),
            int(item.get("difficulty") or 0),
        )
        index[key] = item
    return index


def export_coverage_matrix(
    connection: duckdb.DuckDBPyConnection,
    quality_index: dict[tuple[str, str, str, str, int], dict[str, object]],
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        WITH curriculum AS (
            SELECT sl.code AS grade_code,
                   sub.code AS subject_code,
                   sub.default_label AS subject_label,
                   cc.stable_code AS chapter_code,
                   cc.title AS chapter_title,
                   cc.status AS chapter_status,
                   s.code AS skill_code,
                   s.default_label AS skill_title
            FROM curriculum_skill_details csd
            JOIN curriculum_chapters cc ON cc.id = csd.chapter_id
            JOIN school_levels sl ON sl.id = cc.grade_level_id
            JOIN subjects sub ON sub.id = cc.subject_id
            JOIN skills s ON s.id = csd.skill_id
            WHERE csd.status = 'approved'
              AND sl.code = ?
        ),
        production AS (
            SELECT alc.grade_code,
                   sub.code AS subject_code,
                   cc.stable_code AS chapter_code,
                   sk.code AS skill_code,
                   alc.content_type,
                   alc.difficulty,
                   count(*) AS approved_count
            FROM production_learning_catalog alc
            JOIN subjects sub ON sub.id = alc.subject_id
            JOIN curriculum_chapters cc ON cc.id = alc.chapter_id
            JOIN skills sk ON sk.id = alc.skill_id
            WHERE alc.grade_code = ?
            GROUP BY ALL
        ),
        draft AS (
            SELECT json_extract_string(cv.payload, '$.curriculum_target.grade_code') AS grade_code,
                   json_extract_string(cv.payload, '$.curriculum_target.subject_code') AS subject_code,
                   json_extract_string(cv.payload, '$.curriculum_target.chapter_code') AS chapter_code,
                   sk.code AS skill_code,
                   json_extract_string(cv.payload, '$.canonical_content_type') AS content_type,
                   e.difficulty,
                   e.status,
                   count(*) AS draft_count
            FROM exercises e
            JOIN exercise_questions eq ON eq.exercise_id = e.id
            JOIN question_skills qs ON qs.question_id = eq.question_id AND qs.is_primary
            JOIN skills sk ON sk.id = qs.skill_id
            JOIN content_versions cv ON cv.entity_type = 'exercise' AND cv.entity_id = e.id
            WHERE e.status = 'draft'
              AND cv.status = 'draft'
              AND json_extract_string(cv.payload, '$.curriculum_target.grade_code') = ?
            GROUP BY ALL
        )
        SELECT c.grade_code,
               c.subject_code,
               c.subject_label,
               c.chapter_code,
               c.chapter_title,
               c.chapter_status,
               c.skill_code,
               c.skill_title,
               coalesce(p.content_type, d.content_type, '') AS content_type,
               coalesce(p.difficulty, d.difficulty, 0) AS difficulty,
               coalesce(d.status, CASE WHEN coalesce(p.approved_count, 0) > 0 THEN 'approved' ELSE 'missing' END) AS status,
               coalesce(p.approved_count, 0) AS approved_count,
               coalesce(d.draft_count, 0) AS draft_count,
               coalesce(p.approved_count, 0) + coalesce(d.draft_count, 0) AS total_count,
               coalesce(p.approved_count, 0) AS usable_count,
               cast(NULL AS VARCHAR) AS last_updated_at
        FROM curriculum c
        LEFT JOIN production p
            ON p.grade_code = c.grade_code
           AND p.subject_code = c.subject_code
           AND p.chapter_code = c.chapter_code
           AND p.skill_code = c.skill_code
        LEFT JOIN draft d
            ON d.grade_code = c.grade_code
           AND d.subject_code = c.subject_code
           AND d.chapter_code = c.chapter_code
           AND d.skill_code = c.skill_code
           AND (p.content_type IS NULL OR d.content_type = p.content_type)
        ORDER BY c.subject_label, c.chapter_code, c.skill_code, content_type, difficulty
        """,
        [GRADE, GRADE, GRADE],
    ).fetchall()

    output: list[dict[str, object]] = []
    for row in rows:
        subject_code = str(row[1])
        chapter_code = str(row[3])
        skill_code = str(row[6])
        content_type = str(row[8])
        difficulty = int(row[9] or 0)
        approved_count = int(row[11] or 0)
        quality = quality_index.get((subject_code, chapter_code, skill_code, content_type, difficulty), {})
        eligible = approved_count > 0
        output.append(
            {
                "grade_code": row[0],
                "subject_code": subject_code,
                "subject_label": row[2],
                "chapter_code": chapter_code,
                "chapter_title": row[4],
                "chapter_status": row[5],
                "skill_code": skill_code,
                "skill_title": row[7],
                "content_type": content_type,
                "difficulty": difficulty,
                "status": row[10],
                "decision": quality.get("decision", ""),
                "structural_pass": quality.get("structural_pass", ""),
                "active_version": quality.get("version_id", ""),
                "eligible_for_homework": eligible,
                "total_count": int(row[13] or 0),
                "approved_count": approved_count,
                "usable_count": int(row[14] or 0),
                "draft_count": int(row[12] or 0),
                "last_updated_at": row[15] or "",
            }
        )
    return output


def curriculum_subject_summary(connection: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
    return [
        {
            "subject_code": row[0],
            "subject_label": row[1],
            "production_total": int(row[2] or 0),
            "practice": int(row[3] or 0),
            "assessment": int(row[4] or 0),
            "other": int(row[5] or 0),
            "chapters_with_prod": int(row[6] or 0),
            "chapters_curriculum": int(row[7] or 0),
        }
        for row in connection.execute(
            """
            WITH curriculum_subjects AS (
                SELECT DISTINCT sub.code AS subject_code,
                       sub.default_label AS subject_label
                FROM curriculum_chapters cc
                JOIN school_levels sl ON sl.id = cc.grade_level_id
                JOIN subjects sub ON sub.id = cc.subject_id
                WHERE sl.code = ? AND cc.status = 'approved'
            ),
            prod AS (
                SELECT sub.code AS subject_code,
                       alc.content_type,
                       alc.chapter_id
                FROM production_learning_catalog alc
                JOIN subjects sub ON sub.id = alc.subject_id
                WHERE alc.grade_code = ?
            ),
            chapters AS (
                SELECT sub.code AS subject_code, count(*) AS chapter_count
                FROM curriculum_chapters cc
                JOIN school_levels sl ON sl.id = cc.grade_level_id
                JOIN subjects sub ON sub.id = cc.subject_id
                WHERE sl.code = ? AND cc.status = 'approved'
                GROUP BY 1
            )
            SELECT cs.subject_code,
                   cs.subject_label,
                   count(p.subject_code),
                   sum(CASE WHEN p.content_type IN ('practice','guided_practice') THEN 1 ELSE 0 END),
                   sum(CASE WHEN p.content_type = 'assessment' THEN 1 ELSE 0 END),
                   sum(CASE WHEN p.content_type NOT IN ('practice','guided_practice','assessment') THEN 1 ELSE 0 END),
                   count(DISTINCT p.chapter_id),
                   coalesce(max(c.chapter_count), 0)
            FROM curriculum_subjects cs
            LEFT JOIN prod p ON p.subject_code = cs.subject_code
            LEFT JOIN chapters c ON c.subject_code = cs.subject_code
            GROUP BY cs.subject_code, cs.subject_label
            ORDER BY cs.subject_label
            """,
            [GRADE, GRADE, GRADE],
        ).fetchall()
    ]


def all_4e_subjects_from_quality() -> tuple[str, ...]:
    results = json.loads((QUALITY / "lcai_0012d_quality_results.json").read_text(encoding="utf-8"))
    subjects = sorted({str(item["subject"]) for item in results if item.get("grade") == GRADE})
    return tuple(subjects)


def export_review_queue(subject_code: str, output_path: Path) -> int:
    results = json.loads((QUALITY / "lcai_0012d_quality_results.json").read_text(encoding="utf-8"))
    rows = [item for item in results if item.get("grade") == GRADE and item.get("subject") == subject_code]
    rows.sort(key=lambda item: (str(item.get("decision")), str(item.get("skill")), str(item.get("code"))))
    fieldnames = [
        "grade",
        "subject_code",
        "subject_label",
        "skill_code",
        "chapter_code",
        "content_type",
        "decision",
        "status",
        "content_id",
        "version_id",
        "code",
        "difficulty",
        "structural_pass",
        "approval_candidate",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in rows:
            writer.writerow(
                {
                    "grade": item.get("grade"),
                    "subject_code": item.get("subject"),
                    "subject_label": SUBJECT_LABELS.get(subject_code, subject_code),
                    "skill_code": item.get("skill"),
                    "chapter_code": item.get("chapter"),
                    "content_type": item.get("content_type"),
                    "decision": item.get("decision"),
                    "status": item.get("status"),
                    "content_id": item.get("content_id"),
                    "version_id": item.get("version_id"),
                    "code": item.get("code"),
                    "difficulty": item.get("difficulty"),
                    "structural_pass": item.get("structural_pass"),
                    "approval_candidate": item.get("approval_candidate"),
                }
            )
    return len(rows)


def diagnose_subject(item: SubjectHomeworkAvailability) -> str:
    if item.availability_status == "available":
        return "OK"
    if item.production_count == 0:
        return "Absence de contenu Approved publié"
    if item.eligible_count == 0:
        return "Filtre difficulté ou type — contenus publiés non éligibles"
    if item.eligible_count < 10:
        return "Contenu insuffisant pour un devoir standard"
    return "Couverture limitée"


def write_all_subjects_audit(
    *,
    summaries: list[dict[str, object]],
    availability: tuple[SubjectHomeworkAvailability, ...],
    matrix_rows: list[dict[str, object]],
    review_counts: dict[str, int],
) -> None:
    availability_map = {item.subject_code: item for item in availability}
    lines = [
        "# LCAI-0018 — Phase 0 : audit exhaustif toutes matières (4e)",
        "",
        "## Runtime",
        "",
        f"- Base V2 : `{get_v2_database_path()}`",
        "- Chemin devoirs : `ui/unified_app._homework_form` → `HomeworkService` → `DuckDBUnifiedExperienceRepository.select_approved_content_detailed`",
        "- Catalogue production : vue/table `production_learning_catalog`",
        "- Matières UI devoirs : `curriculum_subjects_for_grade` (toutes matières curriculum, pas seulement celles avec stock)",
        "",
        "## Synthèse par matière",
        "",
        "| Matière | Statut devoir | Prod. | Éligibles | Chapitres prod. | Chapitres curriculum | Diagnostic |",
        "|---------|---------------|------:|----------:|----------------:|---------------------:|------------|",
    ]
    for summary in summaries:
        code = str(summary["subject_code"])
        item = availability_map.get(code)
        if item is None:
            continue
        lines.append(
            f"| {summary['subject_label']} | {item.homework_status_label} | "
            f"{summary['production_total']} | {item.eligible_count} | "
            f"{summary['chapters_with_prod']} | {summary['chapters_curriculum']} | "
            f"{diagnose_subject(item)} |"
        )

    zero_rows = sum(1 for row in matrix_rows if int(row["approved_count"]) == 0)
    lines.extend(
        [
            "",
            "## Métriques couverture",
            "",
            f"- Lignes matrice curriculum : **{len(matrix_rows)}**",
            f"- Combinaisons skill/type à zéro contenu publié : **{zero_rows}**",
            f"- Matières curriculum configurées : **{len(summaries)}**",
            "",
            "## Cause P0 Anglais / Physique-Chimie",
            "",
            "Contenus publiés uniquement en **difficulté 2** alors que l'UI propose **Moyen = 3**.",
            "Correctif : assouplissement automatique + états UI Disponible / Couverture limitée / Indisponible.",
            "",
            "## Files de revue exportées",
            "",
        ]
    )
    for code, count in sorted(review_counts.items()):
        label = SUBJECT_LABELS.get(code, code)
        lines.append(f"- `{code}` ({label}) : {count} candidat(s) → `exports/LCAI-0018_4E_REVIEW_QUEUE_{code}.csv`")

    lines.extend(
        [
            "",
            "## Livrables",
            "",
            "- `docs/phase3/exports/LCAI-0018_4E_COVERAGE_MATRIX.csv`",
            "- `docs/phase3/LCAI-0018_HOMEWORK_ACCEPTANCE_MATRIX.md`",
            "- Files `exports/LCAI-0018_4E_REVIEW_QUEUE_<SUBJECT>.csv`",
            "",
        ]
    )
    (DOCS / "LCAI-0018_PHASE0_ALL_SUBJECTS_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")


def write_homework_acceptance_matrix(
    availability: tuple[SubjectHomeworkAvailability, ...],
    repository: DuckDBUnifiedExperienceRepository,
    grade_id: int,
) -> None:
    service = HomeworkService(repository)
    lines = [
        "# LCAI-0018 — Matrice d'acceptation devoirs 4e",
        "",
        "| Matière | Statut | Éligibles | Devoir 10 ex. | Assouplissement | Résultat |",
        "|---------|--------|----------:|--------------:|-----------------|----------|",
    ]
    for item in availability:
        request = HomeworkRequest(
            0,
            "SYSTEM",
            "lcai-0018-audit",
            AssignmentType.GLOBAL_SUBJECT,
            item.subject_id,
            grade_id,
            (),
            (),
            DifficultyMode.MEDIUM,
            10,
            None,
            None,
        )
        preview = service.preview_selection(request)
        can_create = len(preview.content_ids) > 0
        relaxed = "Oui" if preview.difficulty_relaxed else "Non"
        result = "PASS" if can_create else "FAIL"
        lines.append(
            f"| {item.subject_label} | {item.homework_status_label} | {item.eligible_count} | "
            f"{len(preview.content_ids)} | {relaxed} | {result} |"
        )
    lines.append("")
    (DOCS / "LCAI-0018_HOMEWORK_ACCEPTANCE_MATRIX.md").write_text("\n".join(lines), encoding="utf-8")


def write_pedagogical_validation_stub(review_counts: dict[str, int]) -> None:
    lines = [
        "# LCAI-0018 — Rapport de validation pédagogique (brouillon)",
        "",
        "Ce rapport sera complété après publication contrôlée du socle P0/P1.",
        "",
        "## État actuel",
        "",
        "- Validation structurelle disponible via `lcai_0012d_quality_results.json`",
        "- Publication humaine obligatoire avant activation production",
        "",
        "## Candidats en file par matière",
        "",
    ]
    for code, count in sorted(review_counts.items()):
        lines.append(f"- **{SUBJECT_LABELS.get(code, code)}** : {count} candidat(s)")
    lines.extend(
        [
            "",
            "## Prochaines étapes",
            "",
            "1. Traiter les candidats PASS Anglais et Physique-Chimie en priorité.",
            "2. Compléter barèmes et variantes acceptées selon exigences disciplinaires du ticket.",
            "3. Valider manuellement un échantillon par matière avant publication de masse.",
            "",
        ]
    )
    (DOCS / "LCAI-0018_PEDAGOGICAL_VALIDATION_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    EXPORTS.mkdir(parents=True, exist_ok=True)
    quality_index = load_quality_index()
    connection = connect_readonly()
    try:
        summaries = curriculum_subject_summary(connection)
        matrix_rows = export_coverage_matrix(connection, quality_index)
        grade_id = int(connection.execute("SELECT id FROM school_levels WHERE code=?", [GRADE]).fetchone()[0])
    finally:
        connection.close()

    matrix_path = EXPORTS / "LCAI-0018_4E_COVERAGE_MATRIX.csv"
    if matrix_rows:
        with matrix_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(matrix_rows[0].keys()))
            writer.writeheader()
            writer.writerows(matrix_rows)

    subject_codes = sorted({str(item["subject_code"]) for item in summaries} | set(all_4e_subjects_from_quality()))
    review_counts: dict[str, int] = {}
    for code in subject_codes:
        count = export_review_queue(code, EXPORTS / f"LCAI-0018_4E_REVIEW_QUEUE_{code}.csv")
        if count:
            review_counts[code] = count

    repository = DuckDBUnifiedExperienceRepository(get_v2_database_path())
    availability = HomeworkAvailabilityService(repository).list_for_grade(grade_id)
    write_all_subjects_audit(
        summaries=summaries,
        availability=availability,
        matrix_rows=matrix_rows,
        review_counts=review_counts,
    )
    write_homework_acceptance_matrix(availability, repository, grade_id)
    write_pedagogical_validation_stub(review_counts)

    print("Phase 0 all-subjects audit complete")
    print("subjects:", len(summaries))
    print("matrix rows:", len(matrix_rows))
    print("review queues:", review_counts)


if __name__ == "__main__":
    main()
