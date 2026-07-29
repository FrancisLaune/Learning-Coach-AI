"""Rapport : nombre de contenus par matière pour la 4e (FR-4E)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb

from core.config import get_v2_database_path

GRADE = "FR-4E"
OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "phase3" / "LCAI-0018_4E_CONTENU_PAR_MATIERE.md"


def main() -> None:
    conn = duckdb.connect(str(get_v2_database_path()), read_only=True)
    try:
        production = conn.execute(
            """
            SELECT sub.code,
                   sub.default_label,
                   count(*) AS total,
                   sum(CASE WHEN alc.content_type IN ('practice','guided_practice') THEN 1 ELSE 0 END) AS practice,
                   sum(CASE WHEN alc.content_type = 'assessment' THEN 1 ELSE 0 END) AS assessment,
                   sum(CASE WHEN alc.content_type NOT IN ('practice','guided_practice','assessment') THEN 1 ELSE 0 END) AS autres,
                   count(DISTINCT alc.chapter_id) AS chapitres_prod
            FROM production_learning_catalog alc
            JOIN subjects sub ON sub.id = alc.subject_id
            WHERE alc.grade_code = ?
            GROUP BY 1, 2
            ORDER BY sub.default_label
            """,
            [GRADE],
        ).fetchall()

        draft_rows = conn.execute(
            """
            SELECT json_extract_string(cv.payload, '$.curriculum_target.subject_code') AS subject_code,
                   count(DISTINCT e.id) AS draft_count
            FROM exercises e
            JOIN content_versions cv ON cv.entity_type = 'exercise' AND cv.entity_id = e.id
            WHERE e.status = 'draft'
              AND cv.status = 'draft'
              AND json_extract_string(cv.payload, '$.curriculum_target.grade_code') = ?
            GROUP BY 1
            """,
            [GRADE],
        ).fetchall()
        draft_map = {str(row[0]): int(row[1]) for row in draft_rows if row[0]}

        curriculum_rows = conn.execute(
            """
            SELECT sub.code,
                   sub.default_label,
                   count(DISTINCT cc.id) AS chapters
            FROM curriculum_chapters cc
            JOIN school_levels sl ON sl.id = cc.grade_level_id
            JOIN subjects sub ON sub.id = cc.subject_id
            WHERE sl.code = ? AND cc.status = 'approved'
            GROUP BY 1, 2
            ORDER BY sub.default_label
            """,
            [GRADE],
        ).fetchall()
    finally:
        conn.close()

    prod_map = {str(row[0]): row for row in production}
    total_prod = sum(int(row[2]) for row in production)
    total_draft = sum(draft_map.values())

    lines = [
        "# 4e — Nombre de contenus par matière",
        "",
        f"**Niveau :** {GRADE}  ",
        f"**Base :** `learning_coach_v2.duckdb` (catalogue production + brouillons)  ",
        f"**Date :** généré automatiquement",
        "",
        "## Synthèse",
        "",
        f"- **Matières configurées (curriculum)** : {len(curriculum_rows)}",
        f"- **Contenus publiés (production)** : **{total_prod}**",
        f"- **Contenus brouillon (draft)** : **{total_draft}**",
        "",
        "## Détail par matière",
        "",
        "| Matière | Code | Chapitres curriculum | Chapitres avec contenu publié | Publiés | Practice | Assessment | Autres | Brouillons |",
        "|---------|------|---------------------:|------------------------------:|--------:|---------:|-----------:|-------:|-----------:|",
    ]

    for code, label, chapters in curriculum_rows:
        code = str(code)
        label = str(label)
        row = prod_map.get(code)
        if row:
            total = int(row[2])
            practice = int(row[3])
            assessment = int(row[4])
            autres = int(row[5])
            ch_prod = int(row[6])
        else:
            total = practice = assessment = autres = ch_prod = 0
        drafts = draft_map.get(code, 0)
        lines.append(
            f"| {label} | {code} | {chapters} | {ch_prod} | {total} | {practice} | {assessment} | {autres} | {drafts} |"
        )

    lines.extend(
        [
            "",
            "## Légende",
            "",
            "- **Publiés** : contenus Approved actifs dans `production_learning_catalog` (éligibles aux devoirs).",
            "- **Brouillons** : exercices en statut `draft` ciblant la 4e, non publiés.",
            "- **Practice / Assessment** : répartition par type pédagogique du stock publié.",
            "",
            "## Matières absentes du curriculum 4e",
            "",
        ]
    )

    curriculum_codes = {str(row[0]) for row in curriculum_rows}
    orphan_drafts = sorted(set(draft_map) - curriculum_codes)
    if orphan_drafts:
        for code in orphan_drafts:
            lines.append(f"- `{code}` : {draft_map[code]} brouillon(s) (hors curriculum actif)")
    else:
        lines.append("- Aucune.")

    lines.append("")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUTPUT)
    print(f"total production: {total_prod}, draft: {total_draft}, subjects: {len(curriculum_rows)}")


if __name__ == "__main__":
    main()
