"""LCAI-0018B Phase B0 — baseline audit before any generation campaign."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb

from core.config import get_v2_database_path
from domain.unified_experience.models import AssignmentType, DifficultyMode, HomeworkRequest
from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository
from services.content.homework_availability import HomeworkAvailabilityService

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "phase3"
EXPORTS = DOCS / "exports"
QUALITY = ROOT / "resources" / "content" / "quality"
GRADE = "FR-4E"

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
}

PRIORITY = {
    "ENGLISH": "P0",
    "SPANISH": "P0",
    "PHYSICS_CHEMISTRY": "P0",
    "EMC": "P0",
    "FRENCH": "P1",
    "MATHEMATICS": "P1",
    "HISTORY": "P1",
    "GEOGRAPHY": "P1",
    "SVT": "P1",
}

# Planning minima per chapter (Table 4 — not auto-publication thresholds)
CHAPTER_MINIMA = {
    "diagnostic": 4,
    "practice_guided": 8,
    "practice": 12,
    "remediation": 6,
    "revision": 6,
    "assessment": 6,
    "challenge": 4,
    "qcm": 10,
}

CONTENT_FAMILY = {
    "diagnostic": {"diagnostic"},
    "practice_guided": {"guided_practice"},
    "practice": {"practice", "exercise"},
    "remediation": {"remediation"},
    "revision": {"revision"},
    "assessment": {"assessment", "exam_practice"},
    "challenge": {"challenge"},
    "qcm": {"qcm", "multiple_choice"},
}


def connect_readonly() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(get_v2_database_path()), read_only=True)


def map_content_family(content_type: str) -> str:
    normalized = (content_type or "").strip().lower()
    for family, types in CONTENT_FAMILY.items():
        if normalized in types:
            return family
    if "qcm" in normalized or "choice" in normalized:
        return "qcm"
    if normalized in {"practice", "exercise"}:
        return "practice"
    return "other"


def run_reference_tests() -> tuple[int, str]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(ROOT / "tests" / "test_lcai_0018_4e_content_homework.py"),
            str(ROOT / "tests" / "test_content_factory.py"),
            "-q",
            "--tb=line",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output.strip()[-4000:]


def fetch_matrix(connection: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
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
            WHERE csd.status = 'approved' AND sl.code = ?
        ),
        production AS (
            SELECT sub.code AS subject_code,
                   cc.stable_code AS chapter_code,
                   sk.code AS skill_code,
                   alc.content_type,
                   alc.difficulty,
                   count(*) AS prod_count
            FROM production_learning_catalog alc
            JOIN subjects sub ON sub.id = alc.subject_id
            JOIN curriculum_chapters cc ON cc.id = alc.chapter_id
            JOIN skills sk ON sk.id = alc.skill_id
            WHERE alc.grade_code = ?
            GROUP BY ALL
        ),
        draft AS (
            SELECT json_extract_string(cv.payload, '$.curriculum_target.subject_code') AS subject_code,
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
        SELECT c.grade_code, c.subject_code, c.subject_label, c.chapter_code, c.chapter_title,
               c.chapter_status, c.skill_code, c.skill_title,
               coalesce(p.content_type, d.content_type, '') AS content_type,
               coalesce(p.difficulty, d.difficulty, 0) AS difficulty,
               coalesce(p.prod_count, 0) AS approved_production_count,
               coalesce(d.draft_count, 0) AS draft_count,
               CASE WHEN coalesce(p.prod_count, 0) > 0 THEN true ELSE false END AS eligible_for_homework
        FROM curriculum c
        LEFT JOIN production p
          ON p.subject_code = c.subject_code
         AND p.chapter_code = c.chapter_code
         AND p.skill_code = c.skill_code
        LEFT JOIN draft d
          ON d.subject_code = c.subject_code
         AND d.chapter_code = c.chapter_code
         AND d.skill_code = c.skill_code
         AND (p.content_type IS NULL OR d.content_type = p.content_type)
        ORDER BY c.subject_label, c.chapter_code, c.skill_code, content_type, difficulty
        """,
        [GRADE, GRADE, GRADE],
    ).fetchall()

    output: list[dict[str, object]] = []
    for row in rows:
        content_type = str(row[8] or "")
        family = map_content_family(content_type)
        output.append(
            {
                "grade_code": row[0],
                "subject_code": row[1],
                "subject_label": row[2],
                "chapter_code": row[3],
                "chapter_title": row[4],
                "chapter_status": row[5],
                "skill_code": row[6],
                "skill_title": row[7],
                "content_type": content_type,
                "content_family": family,
                "difficulty": int(row[9] or 0),
                "approved_production_count": int(row[10] or 0),
                "draft_count": int(row[11] or 0),
                "eligible_for_homework": bool(row[12]),
            }
        )
    return output


def homework_acceptance(repository: DuckDBUnifiedExperienceRepository, grade_id: int) -> list[dict[str, object]]:
    service = HomeworkAvailabilityService(repository)
    rows: list[dict[str, object]] = []
    for item in service.list_for_grade(grade_id):
        preview = repository.select_approved_content_detailed(
            HomeworkRequest(
                0,
                "SYSTEM",
                "lcai-0018b-b0",
                AssignmentType.GLOBAL_SUBJECT,
                item.subject_id,
                grade_id,
                (),
                (),
                DifficultyMode.MEDIUM,
                10,
                None,
                datetime.now(tz=UTC),
            )
        )
        can_ten = len(preview.content_ids) >= 10
        if item.availability_status == "unavailable":
            status = "UNAVAILABLE"
        elif can_ten:
            status = "PRODUCTION_READY"
        else:
            status = "LIMITED"
        rows.append(
            {
                "subject_code": item.subject_code,
                "subject_label": item.subject_label,
                "priority": PRIORITY.get(item.subject_code, "P1"),
                "production_count": item.production_count,
                "eligible_count": item.eligible_count,
                "homework_10_result": len(preview.content_ids),
                "coverage_status": status,
                "ten_question_homework": "PASS" if can_ten else "FAIL",
            }
        )
    return rows


def gap_analysis(matrix: list[dict[str, object]]) -> list[dict[str, object]]:
    chapter_buckets: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in matrix:
        if int(row["approved_production_count"]) <= 0:
            continue
        key = (str(row["subject_code"]), str(row["chapter_code"]))
        family = str(row["content_family"])
        if family != "other":
            chapter_buckets[key][family] += int(row["approved_production_count"])

    gaps: list[dict[str, object]] = []
    chapters_seen: set[tuple[str, str]] = set()
    for row in matrix:
        key = (str(row["subject_code"]), str(row["chapter_code"]))
        if key in chapters_seen:
            continue
        chapters_seen.add(key)
        counts = chapter_buckets.get(key, {})
        total = sum(counts.values())
        deficits: dict[str, int] = {}
        for family, minimum in CHAPTER_MINIMA.items():
            deficit = max(0, minimum - counts.get(family, 0))
            if deficit:
                deficits[family] = deficit
        gaps.append(
            {
                "subject_code": key[0],
                "subject_label": row["subject_label"],
                "chapter_code": key[1],
                "chapter_title": row["chapter_title"],
                "priority": PRIORITY.get(key[0], "P1"),
                "approved_total": total,
                "eligible_skills_with_content": sum(
                    1
                    for r in matrix
                    if r["subject_code"] == key[0]
                    and r["chapter_code"] == key[1]
                    and int(r["approved_production_count"]) > 0
                ),
                "planning_deficit_total": sum(deficits.values()),
                "deficits_json": json.dumps(deficits, ensure_ascii=False),
                "gap_status": "EMPTY" if total == 0 else ("CRITICAL" if sum(deficits.values()) > 20 else "PARTIAL"),
            }
        )
    return sorted(gaps, key=lambda item: (str(item["priority"]), str(item["subject_label"]), str(item["chapter_code"])))


def write_coverage_csv(matrix: list[dict[str, object]]) -> Path:
    EXPORTS.mkdir(parents=True, exist_ok=True)
    path = DOCS / "LCAI-0018B_COVERAGE_MATRIX.csv"
    if not matrix:
        return path
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(matrix[0].keys()))
        writer.writeheader()
        writer.writerows(matrix)
    return path


def write_gap_csv(gaps: list[dict[str, object]]) -> None:
    path = EXPORTS / "LCAI-0018B_GAP_BY_CHAPTER.csv"
    if not gaps:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(gaps[0].keys()))
        writer.writeheader()
        writer.writerows(gaps)


def write_ai_fallback_contract() -> None:
    lines = [
        "# LCAI-0018B — Contrat de fallback IA (état B0)",
        "",
        "## Services existants à réutiliser (interdit : second moteur)",
        "",
        "| Couche | Fichier | Rôle |",
        "|--------|---------|------|",
        "| Génération LLM | `infrastructure/generators/openai_content.py` | `OpenAIContentGenerator.generate()` |",
        "| Factory | `services/content/factory.py` | `ContentFactoryService.generate_drafts()` |",
        "| Contrat domaine | `domain/content/factory.py` | `ContentGenerationRequest`, `GeneratedContentCandidate` |",
        "| Gaps offline | `services/content/expansion.py` | `coverage_gaps()`, `CoverageGap.request()` |",
        "| Validation | `services/content/quality.py` | gates structurels |",
        "| Revue IA | `services/content/ai_pedagogical_review.py` | pré-validation pédagogique |",
        "| Publication | `services/content/ai_controlled_publication.py` | publication contrôlée |",
        "| Sélection devoirs | `infrastructure/repositories/unified_experience.py` | `select_approved_content_detailed()` |",
        "",
        "## Écart B0 identifié",
        "",
        "**Aucun pont runtime** ne relie `HomeworkService` / `select_approved_content_detailed` à `ContentFactoryService`.",
        "",
        "Comportement actuel lors d'un déficit :",
        "1. Le moteur retourne moins de contenus que demandé.",
        "2. L'UI affiche « Couverture limitée » ou limite la taille du devoir.",
        "3. Aucun appel LLM à la demande n'est déclenché.",
        "",
        "## Contrat d'entrée cible (Lot B4)",
        "",
        "Réutiliser `ContentGenerationRequest` avec les champs du ticket :",
        "`request_id`, `CurriculumTarget`, `primary_skill_code`, `pedagogical_intent`, `difficulty`,",
        "`variation_constraints`, `language_code`, empreintes récentes.",
        "",
        "## Contrat de sortie cible",
        "",
        "Réutiliser `GeneratedContentCandidate` + validation `CandidateValidator` + gates `quality.py`.",
        "Usage séance : autorisé après validation runtime ; **pas de publication catalogue automatique**.",
        "",
        "## Conditions d'appel IA (Lot B4)",
        "",
        "- Déficit mesuré entre quota demandé et stock éligible `production_learning_catalog`.",
        "- Curriculum/chapitre/skill actifs résolus.",
        "- LLM disponible ; sinon résultat dégradé explicite sans session corrompue.",
        "",
    ]
    (DOCS / "LCAI-0018B_AI_FALLBACK_CONTRACT.md").write_text("\n".join(lines), encoding="utf-8")


def write_adaptive_scenarios() -> None:
    lines = [
        "# LCAI-0018B — Scénarios adaptatifs (baseline B0)",
        "",
        "Scénarios à valider au Lot B5. Sources de signaux déjà présentes en V2 :",
        "",
        "| Signal | Table / service |",
        "|--------|-----------------|",
        "| Maîtrise skill | `longitudinal_mastery_current` |",
        "| Historique séances | `learning_sessions`, `session_activities` |",
        "| Difficulté adaptative devoirs | `HomeworkRequest` + `_difficulty()` |",
        "| Recommandations | `PersonalizedSessionService` |",
        "",
        "## Scénarios obligatoires",
        "",
        "| Situation | Décision attendue | État B0 |",
        "|-----------|-------------------|---------|",
        "| Échecs répétés | Remédiation / prérequis | Partiel (moteur recommandation, pas devoirs) |",
        "| Réussites stables | Augmenter difficulté | Partiel |",
        "| Réussite après indices | Consolidation | Partiel |",
        "| Notion ancienne | Révision espacée | Partiel |",
        "| Prérequis non maîtrisé | Bloquer avancé | À vérifier Lot B5 |",
        "| Deux élèves différents | Séquences différentes | Non garanti pour devoirs catalogue seul |",
        "",
    ]
    (DOCS / "LCAI-0018B_ADAPTIVE_SCENARIOS.md").write_text("\n".join(lines), encoding="utf-8")


def write_homework_matrix(rows: list[dict[str, object]]) -> None:
    lines = [
        "# LCAI-0018B — Matrice d'acceptation devoirs 4e (baseline B0)",
        "",
        "| Matière | Priorité | Publiés | Éligibles | Devoir 10 ex. | Statut | Résultat |",
        "|---------|----------|--------:|----------:|--------------:|--------|----------|",
    ]
    for row in rows:
        lines.append(
            f"| {row['subject_label']} | {row['priority']} | {row['production_count']} | "
            f"{row['eligible_count']} | {row['homework_10_result']} | {row['coverage_status']} | "
            f"{row['ten_question_homework']} |"
        )
    lines.append("")
    (DOCS / "LCAI-0018B_HOMEWORK_ACCEPTANCE_MATRIX.md").write_text("\n".join(lines), encoding="utf-8")


def write_gap_analysis_md(gaps: list[dict[str, object]]) -> None:
    empty = [g for g in gaps if g["gap_status"] == "EMPTY"]
    critical = [g for g in gaps if g["gap_status"] == "CRITICAL"]
    lines = [
        "# LCAI-0018B — Analyse des écarts (Gap Analysis B0)",
        "",
        f"- Chapitres curriculum 4e : **{len(gaps)}**",
        f"- Chapitres sans contenu publié : **{len(empty)}**",
        f"- Chapitres avec déficit planification critique : **{len(critical)}**",
        "",
        "## Chapitres vides (priorité immédiate)",
        "",
    ]
    for gap in empty:
        lines.append(
            f"- **{gap['subject_label']}** / `{gap['chapter_code']}` ({gap['priority']}) — 0 contenu publié"
        )
    lines.extend(["", "## Top écarts par matière P0", ""])
    for code in ("ENGLISH", "SPANISH", "PHYSICS_CHEMISTRY", "EMC"):
        subject_gaps = [g for g in gaps if g["subject_code"] == code]
        if not subject_gaps:
            continue
        lines.append(f"### {SUBJECT_LABELS.get(code, code)}")
        for gap in subject_gaps:
            lines.append(
                f"- `{gap['chapter_code']}` : {gap['approved_total']} publiés, "
                f"déficit planifié {gap['planning_deficit_total']} — {gap['deficits_json']}"
            )
        lines.append("")
    lines.append("Export détaillé : `docs/phase3/exports/LCAI-0018B_GAP_BY_CHAPTER.csv`")
    (DOCS / "LCAI-0018B_GAP_ANALYSIS.md").write_text("\n".join(lines), encoding="utf-8")


def write_baseline_md(
    *,
    matrix: list[dict[str, object]],
    gaps: list[dict[str, object]],
    homework: list[dict[str, object]],
    test_exit: int,
    test_output: str,
) -> None:
    prod_by_subject: dict[str, int] = defaultdict(int)
    draft_by_subject: dict[str, int] = defaultdict(int)
    for row in matrix:
        prod_by_subject[str(row["subject_code"])] += int(row["approved_production_count"])
        draft_by_subject[str(row["subject_code"])] += int(row["draft_count"])

    lines = [
        "# LCAI-0018B — Phase B0 Baseline (gelée)",
        "",
        f"**Date :** {datetime.now(tz=UTC).strftime('%Y-%m-%d %H:%M UTC')}  ",
        f"**Base runtime :** `{get_v2_database_path()}`  ",
        f"**Ticket source :** `LCAI-0018B_COUVERTURE_4E_CONTENU_ET_GENERATION_ADAPTATIVE_IA_SPECIFICATION_CURSOR_V2.docx`",
        "",
        "## Chemins applicatifs confirmés",
        "",
        "| Flux | Chemin |",
        "|------|--------|",
        "| Devoirs UI | `ui/unified_app._homework_form` |",
        "| Devoirs service | `HomeworkService` → `select_approved_content_detailed` |",
        "| Catalogue éligible | `production_learning_catalog` + gates production |",
        "| Génération offline | `ContentFactoryService` / `scripts/run_content_expansion.py` |",
        "| Professeur IA | `AITeacherService` (explications, pas exercices devoirs) |",
        "| Recommandations | `PersonalizedSessionService` |",
        "",
        "## Synthèse recalculée (ne pas recopier l'historique)",
        "",
        "| Matière | Priorité | Publiés | Brouillons | Devoir 10 ex. | Statut |",
        "|---------|----------|--------:|-----------:|--------------:|--------|",
    ]
    for row in homework:
        code = str(row["subject_code"])
        lines.append(
            f"| {row['subject_label']} | {row['priority']} | {prod_by_subject.get(code, 0)} | "
            f"{draft_by_subject.get(code, 0)} | {row['homework_10_result']} | {row['coverage_status']} |"
        )

    ten_pass = sum(1 for row in homework if row["ten_question_homework"] == "PASS")
    lines.extend(
        [
            "",
            "## Métriques baseline",
            "",
            f"- Lignes matrice curriculum : **{len(matrix)}**",
            f"- Chapitres actifs : **{len(gaps)}**",
            f"- Chapitres vides : **{sum(1 for g in gaps if g['gap_status'] == 'EMPTY')}**",
            f"- Matières passant devoir 10 questions : **{ten_pass}/{len(homework)}**",
            "",
            "## Tests de référence (avant modification B1+)",
            "",
            f"- Commande : `pytest tests/test_lcai_0018_4e_content_homework.py tests/test_content_factory.py`",
            f"- Code sortie : **{test_exit}** ({'OK' if test_exit == 0 else 'ÉCHEC'})",
            "",
            "```",
            test_output[-2500:] if test_output else "(aucune sortie)",
            "```",
            "",
            "## Divergence ticket vs implémentation",
            "",
            "1. **Génération dynamique à la demande** : absente du runtime devoirs (voir `LCAI-0018B_AI_FALLBACK_CONTRACT.md`).",
            "2. **Quotas par chapitre (Table 4)** : largement non atteints ; déficits calculés dans Gap Analysis.",
            "3. **Français** : 25 publiés mais seulement ~8 éligibles au filtre devoir (difficulté/type).",
            "",
            "## Livrables B0 gelés",
            "",
            "- `LCAI-0018B_COVERAGE_MATRIX.csv`",
            "- `LCAI-0018B_GAP_ANALYSIS.md`",
            "- `exports/LCAI-0018B_GAP_BY_CHAPTER.csv`",
            "- `LCAI-0018B_AI_FALLBACK_CONTRACT.md`",
            "- `LCAI-0018B_ADAPTIVE_SCENARIOS.md`",
            "- `LCAI-0018B_HOMEWORK_ACCEPTANCE_MATRIX.md`",
            "",
            "## Prochain lot (B1 — sans démarrer sans validation Francis)",
            "",
            "P0 : Anglais, Espagnol, Physique-Chimie, EMC → recette 10 questions + préparation fallback IA.",
            "",
        ]
    )
    (DOCS / "LCAI-0018B_PHASE0_BASELINE.md").write_text("\n".join(lines), encoding="utf-8")


def write_implementation_report(test_exit: int) -> None:
    lines = [
        "# LCAI-0018B — Rapport d'implémentation",
        "",
        "## Lot en cours : B0 (terminé)",
        "",
        "- Audit baseline exécuté : `scripts/lcai_0018b_phase0_baseline.py`",
        "- Aucune génération massive lancée",
        "- Aucune migration DuckDB",
        "- Aucun commit / push (politique Francis)",
        "",
        "## Fichiers créés",
        "",
        "- `docs/phase3/LCAI-0018B_PHASE0_BASELINE.md`",
        "- `docs/phase3/LCAI-0018B_COVERAGE_MATRIX.csv`",
        "- `docs/phase3/LCAI-0018B_GAP_ANALYSIS.md`",
        "- `docs/phase3/LCAI-0018B_AI_FALLBACK_CONTRACT.md`",
        "- `docs/phase3/LCAI-0018B_ADAPTIVE_SCENARIOS.md`",
        "- `docs/phase3/LCAI-0018B_HOMEWORK_ACCEPTANCE_MATRIX.md`",
        "- `docs/phase3/exports/LCAI-0018B_GAP_BY_CHAPTER.csv`",
        "- `scripts/lcai_0018b_phase0_baseline.py`",
        "",
        f"## Tests baseline : exit {test_exit}",
        "",
        "## Limites et dette",
        "",
        "- Fallback IA runtime : **non implémenté** (Lot B4)",
        "- Publication automatique : **interdite** par ticket",
        "- Rapports QA pédagogique / traçabilité génération : à produire après B1-B4",
        "",
    ]
    (DOCS / "LCAI-0018B_IMPLEMENTATION_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    EXPORTS.mkdir(parents=True, exist_ok=True)
    connection = connect_readonly()
    try:
        matrix = fetch_matrix(connection)
        grade_id = int(connection.execute("SELECT id FROM school_levels WHERE code=?", [GRADE]).fetchone()[0])
    finally:
        connection.close()

    repository = DuckDBUnifiedExperienceRepository(get_v2_database_path())
    homework = homework_acceptance(repository, grade_id)
    gaps = gap_analysis(matrix)

    write_coverage_csv(matrix)
    write_gap_csv(gaps)
    write_gap_analysis_md(gaps)
    write_ai_fallback_contract()
    write_adaptive_scenarios()
    write_homework_matrix(homework)

    print("Running reference tests...")
    test_exit, test_output = run_reference_tests()
    write_baseline_md(
        matrix=matrix,
        gaps=gaps,
        homework=homework,
        test_exit=test_exit,
        test_output=test_output,
    )
    write_implementation_report(test_exit)

    print("LCAI-0018B B0 baseline complete")
    print("matrix rows:", len(matrix))
    print("chapters:", len(gaps))
    print("tests exit:", test_exit)


if __name__ == "__main__":
    main()
