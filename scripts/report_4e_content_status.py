"""Report production and draft content status for FR-4E / FR-3E by subject."""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infrastructure.database.v2 import connect_v2
from services.content.approval_coverage import tier

GRADES = ("FR-4E", "FR-3E")


def main() -> None:
    connection = connect_v2()
    try:
        print("=" * 72)
        print("ÉTAT DES CONTENUS — 4e et 3e (préparation brevet)")
        print("=" * 72)

        # --- Production catalog (what homework uses) ---
        prod_rows = connection.execute(
            """
            SELECT sl.code AS grade, sub.code AS subject, sub.default_label AS subject_label,
                   alc.content_type, COUNT(*) AS cnt
            FROM production_learning_catalog alc
            JOIN school_levels sl ON sl.code = alc.grade_code
            JOIN subjects sub ON sub.id = alc.subject_id
            WHERE sl.code IN ('FR-4E', 'FR-3E')
            GROUP BY 1, 2, 3, 4
            ORDER BY 1, 3, 4
            """
        ).fetchall()

        prod_by_grade_subject: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for grade, subject, _label, content_type, cnt in prod_rows:
            prod_by_grade_subject[(grade, subject)][content_type] += int(cnt)
            prod_by_grade_subject[(grade, subject)]["_total"] += int(cnt)

        print("\n## 1. CONTENUS EN PRODUCTION (catalogue devoirs)\n")
        for grade in GRADES:
            print(f"\n### {grade}\n")
            print(f"{'Matière':<22} {'Practice':>8} {'Assessment':>10} {'Autres':>8} {'TOTAL':>8}")
            print("-" * 60)
            subjects = sorted(
                {(g, s) for (g, s) in prod_by_grade_subject if g == grade},
                key=lambda x: x[1],
            )
            if not subjects:
                print("  (aucun)")
                continue
            for _g, subject in subjects:
                data = prod_by_grade_subject[(grade, subject)]
                practice = data.get("practice", 0) + data.get("guided_practice", 0)
                assessment = data.get("assessment", 0)
                other = data["_total"] - practice - assessment
                label_row = connection.execute(
                    "SELECT default_label FROM subjects WHERE code=?", [subject]
                ).fetchone()
                label = label_row[0] if label_row else subject
                print(f"{label:<22} {practice:>8} {assessment:>10} {other:>8} {data['_total']:>8}")

        # --- French 4E detail (user question) ---
        print("\n\n## 2. DÉTAIL FRANÇAIS 4e — contenus production disponibles pour devoirs\n")
        fr_prod = connection.execute(
            """
            SELECT alc.content_id, alc.content_type, alc.difficulty,
                   sk.code AS skill_code, sk.default_label AS skill_label,
                   ch.title AS chapter
            FROM production_learning_catalog alc
            JOIN subjects sub ON sub.id = alc.subject_id
            JOIN skills sk ON sk.id = alc.skill_id
            JOIN curriculum_chapters ch ON ch.id = alc.chapter_id
            WHERE alc.grade_code = 'FR-4E' AND sub.code = 'FRENCH'
            ORDER BY ch.sequence_order, sk.code, alc.content_type, alc.content_id
            """
        ).fetchall()
        print(f"Total production FRENCH FR-4E: {len(fr_prod)}")
        for row in fr_prod:
            print(f"  id={row[0]} | {row[1]:<12} | {row[2]:<8} | {row[3]} | {row[5]} — {row[4]}")

        # --- Skill coverage tier ---
        print("\n\n## 3. COUVERTURE PAR COMPÉTENCE (skills approuvés curriculum 4e/3e)\n")
        coverage_rows = connection.execute(
            """
            WITH approved_skills AS (
                SELECT sl.code AS grade, sub.code AS subject, sub.default_label AS subject_label,
                       s.id AS skill_id, s.code AS skill_code, s.default_label AS skill_label
                FROM curriculum_skill_details csd
                JOIN curriculum_chapters cc ON cc.id = csd.chapter_id
                JOIN school_levels sl ON sl.id = cc.grade_level_id
                JOIN skills s ON s.id = csd.skill_id
                JOIN domains d ON d.id = s.domain_id
                JOIN subjects sub ON sub.id = d.subject_id
                WHERE csd.status = 'approved' AND cc.status = 'approved'
                  AND sl.code IN ('FR-4E', 'FR-3E')
            ),
            prod AS (
                SELECT grade_code, skill_id,
                       SUM(CASE WHEN content_type IN ('practice','guided_practice') THEN 1 ELSE 0 END) AS practice,
                       SUM(CASE WHEN content_type = 'assessment' THEN 1 ELSE 0 END) AS assessment
                FROM production_learning_catalog
                WHERE grade_code IN ('FR-4E', 'FR-3E')
                GROUP BY 1, 2
            )
            SELECT a.grade, a.subject, a.subject_label, a.skill_code, a.skill_label,
                   COALESCE(p.practice, 0) AS practice, COALESCE(p.assessment, 0) AS assessment
            FROM approved_skills a
            LEFT JOIN prod p ON p.grade_code = a.grade AND p.skill_id = a.skill_id
            ORDER BY a.grade, a.subject_label, a.skill_code
            """
        ).fetchall()

        by_grade_subject: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
        gaps: list[tuple] = []
        for grade, subject, subject_label, skill_code, skill_label, practice, assessment in coverage_rows:
            key = (grade, subject_label)
            t = tier(int(practice) > 0, int(assessment) > 0)
            by_grade_subject[key][f"tier{t}"] += 1
            by_grade_subject[key]["skills"] += 1
            if t >= 2:
                gaps.append((grade, subject_label, skill_code, skill_label, practice, assessment, t))

        for grade in GRADES:
            print(f"\n### {grade} — répartition Tier par matière\n")
            print(f"{'Matière':<22} {'Skills':>7} {'Tier1':>7} {'Tier2':>7} {'Tier3':>7}")
            print("-" * 55)
            keys = sorted({k for k in by_grade_subject if k[0] == grade}, key=lambda x: x[1])
            for _g, label in keys:
                d = by_grade_subject[(_g, label)]
                print(
                    f"{label:<22} {d['skills']:>7} {d.get('tier1',0):>7} "
                    f"{d.get('tier2',0):>7} {d.get('tier3',0):>7}"
                )

        # --- Draft / review queue ---
        print("\n\n## 4. CONTENUS DRAFT / À VALIDER (candidats non publiés)\n")
        draft_rows = connection.execute(
            """
            SELECT sl.code AS grade, sub.code AS subject, sub.default_label,
                   cc.status AS candidate_status, cc.content_type, COUNT(*) AS cnt
            FROM content_candidates cc
            JOIN skills s ON s.id = cc.skill_id
            JOIN domains d ON d.id = s.domain_id
            JOIN subjects sub ON sub.id = d.subject_id
            JOIN curriculum_chapters ch ON ch.id = cc.chapter_id
            JOIN school_levels sl ON sl.id = ch.grade_level_id
            WHERE sl.code IN ('FR-4E', 'FR-3E')
              AND cc.production_enabled = FALSE
            GROUP BY 1, 2, 3, 4, 5
            ORDER BY 1, 3, 4, 5
            """
        ).fetchall()

        draft_by: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for grade, _subj, label, status, _ctype, cnt in draft_rows:
            draft_by[(grade, label)][status] += int(cnt)
            draft_by[(grade, label)]["_total"] += int(cnt)

        for grade in GRADES:
            print(f"\n### {grade}\n")
            print(f"{'Matière':<22} {'Draft total':>12}  Détail statuts")
            print("-" * 70)
            keys = sorted({k for k in draft_by if k[0] == grade}, key=lambda x: x[1])
            if not keys:
                print("  (aucun candidat draft)")
                continue
            for _g, label in keys:
                d = draft_by[(_g, label)]
                statuses = ", ".join(f"{k}={v}" for k, v in sorted(d.items()) if k != "_total")
                print(f"{label:<22} {d['_total']:>12}  {statuses}")

        # --- French gaps ---
        print("\n\n## 5. FRANÇAIS 4e — SKILLS SANS COUVERTURE COMPLÈTE (Tier 2 ou 3)\n")
        fr_gaps = [g for g in gaps if g[0] == "FR-4E" and "Français" in g[1] or g[1] == "French" or "français" in g[1].lower()]
        if not fr_gaps:
            fr_gaps = [g for g in gaps if g[0] == "FR-4E" and "FRENCH" in str(g).upper()]
        # better filter by subject code
        fr_gaps = connection.execute(
            """
            WITH approved_skills AS (
                SELECT sl.code AS grade, sub.code AS subject, sub.default_label AS subject_label,
                       s.code AS skill_code, s.default_label AS skill_label
                FROM curriculum_skill_details csd
                JOIN curriculum_chapters cc ON cc.id = csd.chapter_id
                JOIN school_levels sl ON sl.id = cc.grade_level_id
                JOIN skills s ON s.id = csd.skill_id
                JOIN domains d ON d.id = s.domain_id
                JOIN subjects sub ON sub.id = d.subject_id
                WHERE csd.status = 'approved' AND cc.status = 'approved'
                  AND sl.code = 'FR-4E' AND sub.code = 'FRENCH'
            ),
            prod AS (
                SELECT skill_id,
                       SUM(CASE WHEN content_type IN ('practice','guided_practice') THEN 1 ELSE 0 END) AS practice,
                       SUM(CASE WHEN content_type = 'assessment' THEN 1 ELSE 0 END) AS assessment
                FROM production_learning_catalog WHERE grade_code = 'FR-4E'
                GROUP BY 1
            )
            SELECT a.skill_code, a.skill_label,
                   COALESCE(p.practice,0), COALESCE(p.assessment,0)
            FROM approved_skills a
            JOIN skills s ON s.code = a.skill_code
            LEFT JOIN prod p ON p.skill_id = s.id
            ORDER BY a.skill_code
            """
        ).fetchall()

        tier1 = tier2 = tier3 = 0
        print(f"{'Skill':<16} {'Practice':>8} {'Assessment':>10} {'Tier':>5}  Libellé")
        print("-" * 80)
        for skill_code, skill_label, practice, assessment in fr_gaps:
            t = tier(int(practice) > 0, int(assessment) > 0)
            if t == 1:
                tier1 += 1
            elif t == 2:
                tier2 += 1
            else:
                tier3 += 1
            flag = "" if t == 1 else " ← à compléter"
            print(f"{skill_code:<16} {practice:>8} {assessment:>10} {t:>5}  {skill_label}{flag}")
        print(f"\nRésumé FR-4E FRENCH: Tier1={tier1}, Tier2={tier2}, Tier3={tier3}, skills={len(fr_gaps)}")

        print("\n\n## 6. CANDIDATS FRANÇAIS 4e EN ATTENTE (draft, non production)\n")
        fr_drafts = connection.execute(
            """
            SELECT cc.id, cc.content_type, cc.status, cc.recommended_decision,
                   s.code AS skill_code, s.default_label AS skill_label
            FROM content_candidates cc
            JOIN skills s ON s.id = cc.skill_id
            JOIN domains d ON d.id = s.domain_id
            JOIN subjects sub ON sub.id = d.subject_id
            JOIN curriculum_chapters ch ON ch.id = cc.chapter_id
            JOIN school_levels sl ON sl.id = ch.grade_level_id
            WHERE sl.code = 'FR-4E' AND sub.code = 'FRENCH'
              AND cc.production_enabled = FALSE
            ORDER BY cc.status, s.code, cc.content_type, cc.id
            """
        ).fetchall()
        print(f"Total candidats draft FRENCH FR-4E: {len(fr_drafts)}")
        for row in fr_drafts[:50]:
            print(f"  cand={row[0]} | {row[1]:<12} | status={row[2]} | decision={row[3]} | {row[4]} — {row[5]}")
        if len(fr_drafts) > 50:
            print(f"  ... et {len(fr_drafts) - 50} autres")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
