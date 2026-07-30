"""LCAI-0018E Phase C0 — 6e curriculum coverage and candidate baseline audit."""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb

from core.config import get_v2_database_path
from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository
from services.content.homework_availability import HomeworkAvailabilityService

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "phase3"
EXPORTS = DOCS / "exports"
SIXE_RESOURCES = ROOT / "resources" / "content" / "6e"
GRADE = "FR-6E"

SUBJECT_LABELS = {
    "ENGLISH": "Anglais",
    "PHYSICS_CHEMISTRY": "Physique-Chimie",
    "FRENCH": "Français",
    "MATHEMATICS": "Mathématiques",
    "GEOGRAPHY": "Géographie",
    "HISTORY": "Histoire",
    "SVT": "SVT",
    "EMC": "EMC",
}


def connect_readonly() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(get_v2_database_path()), read_only=True)


def export_coverage_matrix(connection: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
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
               CASE
                   WHEN coalesce(p.approved_count, 0) > 0 THEN 'approved'
                   WHEN coalesce(d.draft_count, 0) > 0 THEN 'draft'
                   ELSE 'missing'
               END AS status,
               coalesce(p.approved_count, 0) AS approved_count,
               coalesce(d.draft_count, 0) AS draft_count
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

    return [
        {
            "grade_code": row[0],
            "subject_code": row[1],
            "subject_label": row[2],
            "chapter_code": row[3],
            "chapter_title": row[4],
            "chapter_status": row[5],
            "skill_code": row[6],
            "skill_title": row[7],
            "content_type": row[8],
            "difficulty": int(row[9] or 0),
            "status": row[10],
            "approved_count": int(row[11] or 0),
            "draft_count": int(row[12] or 0),
            "eligible_for_homework": int(row[11] or 0) > 0,
        }
        for row in rows
    ]


def curriculum_subject_summary(connection: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
    return [
        {
            "subject_code": row[0],
            "subject_label": row[1],
            "production_total": int(row[2] or 0),
            "draft_total": int(row[3] or 0),
            "chapters_with_prod": int(row[4] or 0),
            "chapters_curriculum": int(row[5] or 0),
            "skills_curriculum": int(row[6] or 0),
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
                SELECT sub.code AS subject_code, alc.chapter_id
                FROM production_learning_catalog alc
                JOIN subjects sub ON sub.id = alc.subject_id
                WHERE alc.grade_code = ?
            ),
            drafts AS (
                SELECT json_extract_string(cv.payload, '$.curriculum_target.subject_code') AS subject_code
                FROM exercises e
                JOIN content_versions cv ON cv.entity_type = 'exercise' AND cv.entity_id = e.id
                WHERE e.status = 'draft'
                  AND json_extract_string(cv.payload, '$.curriculum_target.grade_code') = ?
            ),
            chapters AS (
                SELECT sub.code AS subject_code,
                       count(DISTINCT cc.id) AS chapter_count,
                       count(DISTINCT csd.skill_id) AS skill_count
                FROM curriculum_chapters cc
                JOIN school_levels sl ON sl.id = cc.grade_level_id
                JOIN subjects sub ON sub.id = cc.subject_id
                LEFT JOIN curriculum_skill_details csd
                    ON csd.chapter_id = cc.id
                   AND csd.grade_level_id = cc.grade_level_id
                   AND csd.status = 'approved'
                WHERE sl.code = ? AND cc.status = 'approved'
                GROUP BY 1
            )
            SELECT cs.subject_code,
                   cs.subject_label,
                   count(DISTINCT p.chapter_id),
                   count(d.subject_code),
                   count(DISTINCT p.chapter_id),
                   coalesce(max(c.chapter_count), 0),
                   coalesce(max(c.skill_count), 0)
            FROM curriculum_subjects cs
            LEFT JOIN prod p ON p.subject_code = cs.subject_code
            LEFT JOIN drafts d ON d.subject_code = cs.subject_code
            LEFT JOIN chapters c ON c.subject_code = cs.subject_code
            GROUP BY cs.subject_code, cs.subject_label
            ORDER BY cs.subject_label
            """,
            [GRADE, GRADE, GRADE, GRADE],
        ).fetchall()
    ]


def load_candidate_packs() -> list[dict[str, object]]:
    inventory: list[dict[str, object]] = []
    for path in sorted(SIXE_RESOURCES.glob("lcai_6e_*_candidates_v1.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        subject = str(payload.get("subject_code", ""))
        for candidate in payload.get("accepted_candidates", []):
            inventory.append(
                {
                    "source_file": path.name,
                    "subject_code": subject,
                    "chapter_code": candidate.get("chapter"),
                    "skill_code": candidate.get("skill"),
                    "content_type": candidate.get("content_type"),
                    "difficulty": candidate.get("difficulty"),
                    "code": candidate.get("code"),
                    "answer_kind": candidate.get("answer_kind"),
                }
            )
    return inventory


def export_gap_by_chapter(matrix_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    by_chapter: dict[tuple[str, str], dict[str, Any]] = {}
    for row in matrix_rows:
        key = (str(row["subject_code"]), str(row["chapter_code"]))
        bucket = by_chapter.setdefault(
            key,
            {
                "subject_code": row["subject_code"],
                "subject_label": row["subject_label"],
                "chapter_code": row["chapter_code"],
                "chapter_title": row["chapter_title"],
                "skills": set(),
                "approved_total": 0,
                "draft_total": 0,
                "missing_skill_types": 0,
            },
        )
        skill_code = str(row["skill_code"])
        approved_count = int(str(row["approved_count"]))
        draft_count = int(str(row["draft_count"]))
        bucket["skills"].add(skill_code)
        bucket["approved_total"] += approved_count
        bucket["draft_total"] += draft_count
        if approved_count == 0:
            bucket["missing_skill_types"] = int(bucket["missing_skill_types"]) + 1

    gaps: list[dict[str, object]] = []
    for item in by_chapter.values():
        gaps.append(
            {
                "subject_code": item["subject_code"],
                "subject_label": item["subject_label"],
                "chapter_code": item["chapter_code"],
                "chapter_title": item["chapter_title"],
                "skill_count": len(item["skills"]),
                "approved_total": item["approved_total"],
                "draft_total": item["draft_total"],
                "publication_status": "published"
                if item["approved_total"]
                else ("draft_only" if item["draft_total"] else "empty"),
                "priority": "P0" if item["approved_total"] == 0 and item["draft_total"] == 0 else "P1",
            }
        )
    gaps.sort(key=lambda row: (row["priority"], row["subject_label"], row["chapter_code"]))
    return gaps


def write_baseline(
    *,
    summaries: list[dict[str, object]],
    matrix_rows: list[dict[str, object]],
    gaps: list[dict[str, object]],
    candidate_inventory: list[dict[str, object]],
    availability_count: int,
) -> None:
    empty_chapters = [row for row in gaps if row["publication_status"] == "empty"]
    draft_only = [row for row in gaps if row["publication_status"] == "draft_only"]
    published = [row for row in gaps if row["publication_status"] == "published"]
    zero_published_rows = sum(1 for row in matrix_rows if int(str(row["approved_count"])) == 0)

    lines = [
        "# LCAI-0018E — Phase C0 : baseline 6e",
        "",
        f"- Niveau : **{GRADE}**",
        f"- Base V2 : `{get_v2_database_path()}`",
        f"- Matières curriculum : **{len(summaries)}**",
        f"- Lignes matrice couverture : **{len(matrix_rows)}**",
        f"- Combinaisons skill/type sans contenu publié : **{zero_published_rows}**",
        f"- Chapitres vides (ni publié ni draft) : **{len(empty_chapters)}**",
        f"- Chapitres draft-only : **{len(draft_only)}**",
        f"- Chapitres publiés : **{len(published)}**",
        f"- Candidats packagés (resources) : **{len(candidate_inventory)}**",
        f"- Matières avec disponibilité devoirs calculée : **{availability_count}**",
        "",
        "## Synthèse par matière",
        "",
        "| Matière | Publiés | Draft DB | Chapitres prod. | Chapitres curriculum | Compétences |",
        "|---------|--------:|---------:|----------------:|---------------------:|------------:|",
    ]
    for summary in summaries:
        lines.append(
            f"| {summary['subject_label']} | {summary['production_total']} | "
            f"{summary['draft_total']} | {summary['chapters_with_prod']} | "
            f"{summary['chapters_curriculum']} | {summary['skills_curriculum']} |"
        )

    if empty_chapters:
        lines.extend(["", "## Chapitres vides (P0)", ""])
        for row in empty_chapters:
            lines.append(f"- **{row['subject_label']}** / `{row['chapter_code']}` — {row['chapter_title']}")

    lines.extend(
        [
            "",
            "## Candidats préparés (phase 2)",
            "",
            "Packs JSON dans `resources/content/6e/` — lifecycle Draft, approbation humaine obligatoire.",
            "",
            "## Livrables C0",
            "",
            "- `docs/phase3/exports/LCAI-0018E_6E_COVERAGE_MATRIX.csv`",
            "- `docs/phase3/exports/LCAI-0018E_6E_GAP_BY_CHAPTER.csv`",
            "- `docs/phase3/exports/LCAI-0018E_6E_CANDIDATE_INVENTORY.csv`",
            "- `docs/phase3/LCAI-0018E_GAP_ANALYSIS.md`",
            "",
            "## Prochaine étape (C1)",
            "",
            "1. Importer / valider les candidats 6e via Content Factory et quality gates existants.",
            "2. Revue pédagogique humaine distincte de l'approbation.",
            "3. Publication production — recalcul coverage — validation moteurs.",
            "",
        ]
    )
    (DOCS / "LCAI-0018E_PHASE0_BASELINE.md").write_text("\n".join(lines), encoding="utf-8")


def write_gap_analysis(gaps: list[dict[str, object]], candidate_inventory: list[dict[str, object]]) -> None:
    candidates_by_subject: dict[str, int] = defaultdict(int)
    for item in candidate_inventory:
        candidates_by_subject[str(item["subject_code"])] += 1

    lines = [
        "# LCAI-0018E — Analyse des écarts 6e (Gap Analysis C0)",
        "",
        f"- Chapitres curriculum 6e : **{len(gaps)}**",
        f"- Chapitres sans contenu publié : **{sum(1 for g in gaps if g['approved_total'] == 0)}**",
        f"- Chapitres entièrement vides : **{sum(1 for g in gaps if g['publication_status'] == 'empty')}**",
        "",
        "## Candidats packagés par matière",
        "",
    ]
    for code, count in sorted(candidates_by_subject.items()):
        lines.append(f"- **{SUBJECT_LABELS.get(code, code)}** (`{code}`) : {count} candidat(s)")

    lines.extend(["", "## Détail par chapitre", ""])
    for row in gaps:
        lines.append(
            f"- **{row['subject_label']}** / `{row['chapter_code']}` — "
            f"publiés={row['approved_total']}, draft={row['draft_total']}, "
            f"statut={row['publication_status']}, priorité={row['priority']}"
        )
    lines.append("")
    (DOCS / "LCAI-0018E_GAP_ANALYSIS.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    EXPORTS.mkdir(parents=True, exist_ok=True)

    connection = connect_readonly()
    try:
        summaries = curriculum_subject_summary(connection)
        matrix_rows = export_coverage_matrix(connection)
        grade_id = int(connection.execute("SELECT id FROM school_levels WHERE code=?", [GRADE]).fetchone()[0])
    finally:
        connection.close()

    candidate_inventory = load_candidate_packs()
    gaps = export_gap_by_chapter(matrix_rows)

    if matrix_rows:
        with (EXPORTS / "LCAI-0018E_6E_COVERAGE_MATRIX.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(matrix_rows[0].keys()))
            writer.writeheader()
            writer.writerows(matrix_rows)

    if gaps:
        with (EXPORTS / "LCAI-0018E_6E_GAP_BY_CHAPTER.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(gaps[0].keys()))
            writer.writeheader()
            writer.writerows(gaps)

    if candidate_inventory:
        with (EXPORTS / "LCAI-0018E_6E_CANDIDATE_INVENTORY.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(candidate_inventory[0].keys()))
            writer.writeheader()
            writer.writerows(candidate_inventory)

    repository = DuckDBUnifiedExperienceRepository(get_v2_database_path())
    availability = HomeworkAvailabilityService(repository).list_for_grade(grade_id)

    write_baseline(
        summaries=summaries,
        matrix_rows=matrix_rows,
        gaps=gaps,
        candidate_inventory=candidate_inventory,
        availability_count=len(availability),
    )
    write_gap_analysis(gaps, candidate_inventory)

    print("LCAI-0018E Phase C0 audit complete")
    print("subjects:", len(summaries))
    print("matrix rows:", len(matrix_rows))
    print("candidate inventory:", len(candidate_inventory))
    print("empty chapters:", sum(1 for g in gaps if g["publication_status"] == "empty"))


if __name__ == "__main__":
    main()
