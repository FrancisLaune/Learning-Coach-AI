"""4e/3e content report from quality JSON artifacts (no live DB required)."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUALITY = ROOT / "resources" / "content" / "quality"

SUBJECT_LABELS = {
    "EMC": "EMC",
    "ENGLISH": "Anglais",
    "FRENCH": "Français",
    "GEOGRAPHY": "Géographie",
    "HISTORY": "Histoire",
    "MATHEMATICS": "Mathématiques",
    "PHYSICS_CHEMISTRY": "Physique-Chimie",
    "SPANISH": "Espagnol",
    "SVT": "SVT",
}


def load(name: str):
    return json.loads((QUALITY / name).read_text(encoding="utf-8"))


def tier(practice: int, assessment: int) -> int:
    p, a = practice > 0, assessment > 0
    if p and a:
        return 1
    if p or a:
        return 2
    return 3


def main() -> None:
    coverage = load("lcai_0012d2_skill_coverage.json")
    wave1 = load("lcai_0012d4_wave1_summary.json")
    teacher_q = load("lcai_0012e_teacher_review_queue.json")
    quality = load("lcai_0012d4_ai_pedagogical_review_summary.json")

    grades = ("FR-4E", "FR-3E")
    by_grade_subject: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "skills": 0,
            "tier1": 0,
            "tier2": 0,
            "tier3": 0,
            "prod_practice": 0,
            "prod_assessment": 0,
            "prod_total": 0,
            "skills_t2": [],
            "skills_t3": [],
        }
    )

    french_4e_prod: list[dict] = []

    for row in coverage:
        g = str(row["grade"])
        if g not in grades:
            continue
        subj = str(row["subject"])
        key = (g, subj)
        pr = int(row.get("approved_practice") or 0)
        as_ = int(row.get("approved_assessment") or 0)
        t = tier(pr, as_)
        slot = by_grade_subject[key]
        slot["skills"] += 1
        slot[f"tier{t}"] += 1
        slot["prod_practice"] += pr
        slot["prod_assessment"] += as_
        slot["prod_total"] += pr + as_
        entry = {
            "skill": row.get("skill"),
            "skill_name": row.get("skill_name"),
            "practice": pr,
            "assessment": as_,
            "tier": t,
        }
        if t == 2:
            slot["skills_t2"].append(entry)
        elif t == 3:
            slot["skills_t3"].append(entry)
        if g == "FR-4E" and subj == "FRENCH" and (pr or as_):
            french_4e_prod.append(entry)

    pending_by: dict[tuple[str, str], list] = defaultdict(list)
    queue = teacher_q if isinstance(teacher_q, list) else teacher_q.get("queue", [])
    for item in queue:
        g = str(item.get("grade", ""))
        if g not in grades:
            continue
        pending_by[(g, str(item.get("subject", "")))].append(item)

    print("=" * 72)
    print("ÉTAT DES CONTENUS — 4e et 3e (artefacts qualité LCAI-0012D)")
    print("Source: lcai_0012d2_skill_coverage.json + files de revue")
    print("=" * 72)

    snap = wave1.get("coverage_snapshot", {})
    print("\n## Snapshot global (post-campagne D4 Wave 1)\n")
    print(f"Tier 1 (practice + assessment): {snap.get('overall', {}).get('tier1', '?')} skills")
    print(f"Tier 2 (un seul slot):          {snap.get('overall', {}).get('tier2', '?')} skills")
    print(f"Tier 3 (aucun slot prod.):      {snap.get('overall', {}).get('tier3', '?')} skills")
    for g in grades:
        bg = snap.get("by_grade", {}).get(g, {})
        print(f"  {g}: T1={bg.get('tier1','?')} T2={bg.get('tier2','?')} T3={bg.get('tier3','?')}")

    for g in grades:
        print(f"\n## {g} — par matière\n")
        print(
            f"{'Matière':<18} {'Skills':>6} {'T1':>4} {'T2':>4} {'T3':>4} "
            f"{'Prod.P':>7} {'Prod.A':>7} {'Prod tot':>8} {'Revue':>6}"
        )
        print("-" * 72)
        keys = sorted({k for k in by_grade_subject if k[0] == g}, key=lambda x: SUBJECT_LABELS.get(x[1], x[1]))
        for gg, subj in keys:
            if gg != g:
                continue
            d = by_grade_subject[(gg, subj)]
            rev = len(pending_by.get((g, subj), []))
            label = SUBJECT_LABELS.get(subj, subj)
            print(
                f"{label:<18} {d['skills']:>6} {d['tier1']:>4} {d['tier2']:>4} {d['tier3']:>4} "
                f"{d['prod_practice']:>7} {d['prod_assessment']:>7} {d['prod_total']:>7} {rev:>6}"
            )

    print("\n## Français 4e — contenus PRODUCTION disponibles pour devoirs\n")
    print(f"Total slots production (practice + assessment): {sum(r['practice']+r['assessment'] for r in french_4e_prod)}")
    print(f"Skills avec au moins 1 contenu: {len(french_4e_prod)} / 34\n")
    for row in sorted(french_4e_prod, key=lambda x: str(x["skill"])):
        print(
            f"  {row['skill']:<42} P={row['practice']} A={row['assessment']}  "
            f"{row['skill_name']}"
        )

    d = by_grade_subject[("FR-4E", "FRENCH")]
    print(f"\n## Français 4e — skills Tier 2 (1 slot manquant) — {len(d['skills_t2'])} skills\n")
    for row in d["skills_t2"]:
        missing = "assessment" if row["practice"] else "practice"
        print(f"  {row['skill']} — manque {missing} — {row['skill_name']}")

    print(f"\n## Français 4e — skills Tier 3 (aucun contenu prod.) — {len(d['skills_t3'])} skills\n")
    for row in d["skills_t3"][:15]:
        print(f"  {row['skill']} — {row['skill_name']}")
    if len(d["skills_t3"]) > 15:
        print(f"  ... et {len(d['skills_t3']) - 15} autres skills sans contenu production")

    print("\n## File enseignant — candidats FR-4E / FR-3E à revoir\n")
    for g in grades:
        total = sum(len(v) for k, v in pending_by.items() if k[0] == g)
        print(f"{g}: {total} candidats en attente revue humaine")
        for (gg, subj), items in sorted(pending_by.items(), key=lambda x: (x[0][0], x[0][1])):
            if gg != g:
                continue
            print(f"  {SUBJECT_LABELS.get(subj, subj)}: {len(items)}")

    ai = quality.get("summary", quality)
    if isinstance(ai, dict):
        print("\n## Revue IA pédagogique (Wave 2 — référence)\n")
        for k, v in ai.items():
            if isinstance(v, (int, float, str)):
                print(f"  {k}: {v}")

    print("\n---")
    print("Note: les devoirs utilisent production_learning_catalog uniquement.")
    print("Un devoir Français 4e global ne voit que les contenus production ci-dessus (~8 slots).")


if __name__ == "__main__":
    main()
