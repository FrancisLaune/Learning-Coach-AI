"""LCAI-0000A — Global curriculum validation inventory (all grades, all subjects)."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb

from core.config import get_v2_database_path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "phase3"
EXPORTS = DOCS / "exports"

# Grades with LCAI-0018 industrialization ticket + validation script mapping
TICKET_BY_GRADE: dict[str, dict[str, str]] = {
    "FR-CM1": {"ticket": "LCAI-0018C", "status": "IMPLEMENTED"},
    "FR-CM2": {"ticket": "LCAI-0018D", "status": "IMPLEMENTED"},
    "FR-6E": {"ticket": "LCAI-0018E", "status": "IMPLEMENTED"},
    "FR-5E": {"ticket": "LCAI-0018F", "status": "IMPLEMENTED"},
    "FR-4E": {"ticket": "LCAI-0018", "status": "IMPLEMENTED"},
    "FR-3E": {"ticket": "LCAI-0018G", "status": "IMPLEMENTED"},
}


@dataclass
class SubjectRow:
    grade_code: str
    grade_label: str
    subject_code: str
    subject_label: str
    chapters_curriculum: int
    chapters_published: int
    chapters_draft_only: int
    chapters_empty: int
    skills_curriculum: int
    published_content_rows: int
    draft_content_rows: int
    ticket: str
    ticket_status: str
    validation_state: str
    human_action: str


def _connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(get_v2_database_path()), read_only=True)


def _chapter_status(published: int, draft: int) -> str:
    if published > 0:
        return "published"
    if draft > 0:
        return "draft_only"
    return "empty"


def collect_inventory(connection: duckdb.DuckDBPyConnection) -> list[SubjectRow]:
    matrix = connection.execute(
        """
        WITH curriculum AS (
            SELECT sl.code AS grade_code,
                   sl.label AS grade_label,
                   sl.rank AS grade_rank,
                   sub.code AS subject_code,
                   sub.default_label AS subject_label,
                   cc.stable_code AS chapter_code,
                   s.code AS skill_code
            FROM curriculum_skill_details csd
            JOIN curriculum_chapters cc ON cc.id = csd.chapter_id
            JOIN school_levels sl ON sl.id = cc.grade_level_id
            JOIN subjects sub ON sub.id = cc.subject_id
            JOIN skills s ON s.id = csd.skill_id
            WHERE csd.status = 'approved'
              AND cc.status = 'approved'
        ),
        production AS (
            SELECT alc.grade_code,
                   sub.code AS subject_code,
                   cc.stable_code AS chapter_code,
                   sk.code AS skill_code,
                   count(*) AS approved_count
            FROM production_learning_catalog alc
            JOIN subjects sub ON sub.id = alc.subject_id
            JOIN curriculum_chapters cc ON cc.id = alc.chapter_id
            JOIN skills sk ON sk.id = alc.skill_id
            GROUP BY ALL
        ),
        draft AS (
            SELECT json_extract_string(cv.payload, '$.curriculum_target.grade_code') AS grade_code,
                   json_extract_string(cv.payload, '$.curriculum_target.subject_code') AS subject_code,
                   json_extract_string(cv.payload, '$.curriculum_target.chapter_code') AS chapter_code,
                   sk.code AS skill_code,
                   count(*) AS draft_count
            FROM exercises e
            JOIN exercise_questions eq ON eq.exercise_id = e.id
            JOIN question_skills qs ON qs.question_id = eq.question_id AND qs.is_primary
            JOIN skills sk ON sk.id = qs.skill_id
            JOIN content_versions cv ON cv.entity_type = 'exercise' AND cv.entity_id = e.id
            WHERE e.status = 'draft'
              AND cv.status = 'draft'
            GROUP BY ALL
        ),
        cell AS (
            SELECT c.grade_code,
                   c.grade_label,
                   c.grade_rank,
                   c.subject_code,
                   c.subject_label,
                   c.chapter_code,
                   c.skill_code,
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
        ),
        chapter_agg AS (
            SELECT grade_code,
                   grade_label,
                   grade_rank,
                   subject_code,
                   subject_label,
                   chapter_code,
                   sum(approved_count) AS chapter_published,
                   sum(draft_count) AS chapter_draft
            FROM cell
            GROUP BY ALL
        )
        SELECT grade_code,
               grade_label,
               grade_rank,
               subject_code,
               subject_label,
               count(DISTINCT chapter_code) AS chapters_curriculum,
               count(DISTINCT CASE WHEN chapter_published > 0 THEN chapter_code END) AS chapters_published,
               count(DISTINCT CASE WHEN chapter_published = 0 AND chapter_draft > 0 THEN chapter_code END) AS chapters_draft_only,
               count(DISTINCT CASE WHEN chapter_published = 0 AND chapter_draft = 0 THEN chapter_code END) AS chapters_empty,
               count(DISTINCT skill_code) AS skills_curriculum,
               sum(chapter_published) AS published_content_rows,
               sum(chapter_draft) AS draft_content_rows
        FROM chapter_agg
        JOIN cell USING (grade_code, grade_label, grade_rank, subject_code, subject_label, chapter_code)
        GROUP BY grade_code, grade_label, grade_rank, subject_code, subject_label
        ORDER BY grade_rank, subject_label
        """
    ).fetchall()

    rows: list[SubjectRow] = []
    for row in matrix:
        grade_code = str(row[0])
        meta = TICKET_BY_GRADE.get(grade_code, {"ticket": "—", "status": "OUT_OF_SCOPE"})
        ticket = meta["ticket"]
        ticket_status = meta["status"]

        chapters_pub = int(row[6])
        chapters_draft = int(row[7])
        chapters_empty = int(row[8])
        published_rows = int(row[10])

        if ticket_status == "PENDING":
            validation_state = "A_IMPLEMENTER"
            human_action = f"Implémenter {ticket} puis LCAI-0000A"
        elif ticket_status == "OUT_OF_SCOPE":
            validation_state = "HORS_PERIMETRE_18"
            human_action = "Hors série LCAI-0018 actuelle"
        elif chapters_pub == 0:
            validation_state = "CONTENU_A_PUBLIER"
            human_action = "Publication / revue pédagogique requise"
        elif chapters_pub < int(row[5]):
            validation_state = "PARTIEL"
            human_action = "Compléter publication + validation UX matières manquantes"
        else:
            validation_state = "PRET_VALIDATION_0000A"
            human_action = "LCAI-0000A puis validation UX humaine"

        rows.append(
            SubjectRow(
                grade_code=grade_code,
                grade_label=str(row[1]),
                subject_code=str(row[3]),
                subject_label=str(row[4]),
                chapters_curriculum=int(row[5]),
                chapters_published=chapters_pub,
                chapters_draft_only=chapters_draft,
                chapters_empty=chapters_empty,
                skills_curriculum=int(row[9]),
                published_content_rows=published_rows,
                draft_content_rows=int(row[11]),
                ticket=ticket,
                ticket_status=ticket_status,
                validation_state=validation_state,
                human_action=human_action,
            )
        )
    return rows


def _load_0000a_status() -> dict[str, str]:
    status: dict[str, str] = {}
    for path in EXPORTS.glob("lcai_0000a_lcai_0018*_validation_report.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        status[payload["ticket"]] = payload.get("technical_validation", "UNKNOWN")
    return status


def apply_0000a_status(rows: list[SubjectRow], ticket_validation: dict[str, str]) -> list[SubjectRow]:
    updated: list[SubjectRow] = []
    for row in rows:
        if row.ticket_status != "IMPLEMENTED":
            updated.append(row)
            continue
        tech = ticket_validation.get(row.ticket)
        if tech == "OK" and row.validation_state in {"PRET_VALIDATION_0000A", "PARTIEL"}:
            row = SubjectRow(
                **{
                    **asdict(row),
                    "validation_state": "TECH_OK_UX_HUMAINE" if row.chapters_published > 0 else row.validation_state,
                    "human_action": "Validation fonctionnelle UX (devoirs) — technique OK",
                }
            )
        elif tech == "OK" and row.validation_state == "CONTENU_A_PUBLIER":
            row = SubjectRow(
                **{
                    **asdict(row),
                    "validation_state": "CONTENU_A_PUBLIER",
                    "human_action": "Ticket OK techniquement ; matière sans contenu publié — publication requise",
                }
            )
        elif tech in {"NOK", "WARN"}:
            if row.chapters_published > 0:
                row = SubjectRow(
                    **{
                        **asdict(row),
                        "validation_state": "TECH_NOK",
                        "human_action": f"Relancer LCAI-0000A ({tech}) — échec technique ticket",
                    }
                )
            elif row.validation_state == "CONTENU_A_PUBLIER":
                pass
            else:
                row = SubjectRow(
                    **{
                        **asdict(row),
                        "validation_state": "TECH_NOK",
                        "human_action": f"Relancer LCAI-0000A ({tech})",
                    }
                )
        updated.append(row)
    return updated


def export_csv(rows: list[SubjectRow], path: Path) -> None:
    fieldnames = list(asdict(rows[0]).keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_markdown(rows: list[SubjectRow], ticket_validation: dict[str, str], path: Path) -> None:
    by_grade: dict[str, list[SubjectRow]] = {}
    for row in rows:
        by_grade.setdefault(row.grade_code, []).append(row)

    lines = [
        "# LCAI-0000A — Inventaire global validation curriculums",
        "",
        f"Dernière exécution : {datetime.now(UTC).replace(microsecond=0).isoformat()}",
        "",
        "## Validation technique LCAI-0000A par ticket",
        "",
        "| Ticket | Validation technique |",
        "|--------|---------------------|",
    ]
    for ticket, status in sorted(ticket_validation.items()):
        lines.append(f"| {ticket} | {status} |")

    lines.extend(["", "## Détail par niveau et matière", ""])

    state_labels = {
        "TECH_OK_UX_HUMAINE": "✅ Tech OK — UX humaine",
        "PRET_VALIDATION_0000A": "🔄 Prêt 0000A",
        "PARTIEL": "⚠️ Partiel",
        "CONTENU_A_PUBLIER": "📦 Sans publication",
        "A_IMPLEMENTER": "⏳ À implémenter",
        "HORS_PERIMETRE_18": "— Hors scope 18",
        "TECH_NOK": "❌ Tech NOK",
    }

    for grade_code in sorted(by_grade, key=lambda code: by_grade[code][0].grade_label):
        grade_rows = by_grade[grade_code]
        label = grade_rows[0].grade_label
        ticket = grade_rows[0].ticket
        lines.append(f"### {label} (`{grade_code}`) — {ticket}")
        lines.append("")
        lines.append("| Matière | Ch. prod. | Ch. curriculum | Lignes prod. | Draft | État | Action |")
        lines.append("|---------|----------:|---------------:|-------------:|------:|------|--------|")
        for row in grade_rows:
            state = state_labels.get(row.validation_state, row.validation_state)
            lines.append(
                f"| {row.subject_label} | {row.chapters_published} | {row.chapters_curriculum} | "
                f"{row.published_content_rows} | {row.draft_content_rows} | {state} | {row.human_action} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Synthèse actions",
            "",
            "1. **LCAI-0000A** : exécuté automatiquement sur tickets implémentés (18, 18C–18E).",
            "2. **Validation humaine** : parcours devoirs par matière où état = Tech OK — UX humaine.",
            "3. **Publication** : matières sans chapitre publié — campagne revue/régénération.",
            "4. **Implémentation** : 5e (18F), 3e (18G) et certification globale (18H) à venir.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_0000a_validations() -> dict[str, str]:
    script = ROOT / "scripts" / "lcai_0000a_technical_validation.py"
    result = subprocess.run(
        [sys.executable, str(script), "--curriculum-all"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode not in (0, 1):
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
    return _load_0000a_status()


def main() -> None:
    connection = _connect()
    try:
        rows = collect_inventory(connection)
    finally:
        connection.close()

    EXPORTS.mkdir(parents=True, exist_ok=True)
    ticket_validation = run_0000a_validations()
    rows = apply_0000a_status(rows, ticket_validation)

    csv_path = EXPORTS / "LCAI_0000A_GLOBAL_CURRICULUM_VALIDATION_INVENTORY.csv"
    md_path = DOCS / "LCAI-0000A_GLOBAL_CURRICULUM_VALIDATION_INVENTORY.md"
    json_path = EXPORTS / "LCAI_0000A_GLOBAL_CURRICULUM_VALIDATION_INVENTORY.json"

    export_csv(rows, csv_path)
    write_markdown(rows, ticket_validation, md_path)
    json_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
                "ticket_validation": ticket_validation,
                "rows": [asdict(row) for row in rows],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    summary: dict[str, int] = {}
    for row in rows:
        summary[row.validation_state] = summary.get(row.validation_state, 0) + 1

    print("LCAI-0000A global curriculum inventory complete")
    print(f"grades/subjects: {len(rows)}")
    for state, count in sorted(summary.items()):
        print(f"  {state}: {count}")
    print(f"csv: {csv_path}")
    print(f"md: {md_path}")


if __name__ == "__main__":
    main()
