"""Migrate SQLite / DuckDB legacy exercises into content_items."""

from __future__ import annotations

import sqlite3

from core.config import PROJECT_ROOT
from infrastructure.repositories.brevet_content.store import BrevetContentStore
from services.brevet_referential.models import difficulty_score, fingerprint_text, slugify

SUBJECT_ALIASES = {
    "mathématiques": "MATHEMATICS",
    "mathematiques": "MATHEMATICS",
    "maths": "MATHEMATICS",
    "français": "FRENCH",
    "francais": "FRENCH",
    "histoire": "HISTORY",
    "géographie": "GEOGRAPHY",
    "geographie": "GEOGRAPHY",
    "emc": "EMC",
    "physique-chimie": "PHYSICS_CHEMISTRY",
    "physique chimie": "PHYSICS_CHEMISTRY",
    "svt": "SVT",
    "technologie": "TECHNOLOGY",
}


def _resolve_subject_code(label: str) -> str | None:
    key = str(label or "").strip().casefold()
    return SUBJECT_ALIASES.get(key)


def _lookup_chapter_skill(store: BrevetContentStore, subject_id: int, chapter_name: str) -> tuple[int | None, int | None]:
    code = slugify(chapter_name)[:80]
    row = store.fetchone(
        """
        SELECT ch.chapter_id, sk.skill_id
        FROM chapters ch
        JOIN curriculum_domains d ON d.domain_id = ch.domain_id
        JOIN skills sk ON sk.chapter_id = ch.chapter_id
        WHERE d.subject_id = ? AND (ch.code = ? OR ch.name = ?)
        LIMIT 1
        """,
        [subject_id, code, chapter_name],
    )
    if row is None:
        return None, None
    return int(row[0]), int(row[1])


def migrate_sqlite_exercises(store: BrevetContentStore | None = None) -> dict[str, int]:
    store = store or BrevetContentStore()
    imported = 0
    skipped = 0
    paths = [
        PROJECT_ROOT / "revision_3e_enrichie" / "revision_3e.db",
        PROJECT_ROOT / "revision_3e_enrichie" / "objectif_brevet_2027.db",
    ]
    for path in paths:
        if not path.exists():
            continue
        sc = sqlite3.connect(path)
        try:
            cols = [r[1] for r in sc.execute("PRAGMA table_info(exercises)").fetchall()]
            if "question" not in cols:
                continue
            rows = sc.execute("SELECT * FROM exercises").fetchall()
            col_index = {name: idx for idx, name in enumerate(cols)}
            for row in rows:
                subject_label = row[col_index["subject"]]
                chapter = row[col_index["chapter"]]
                question = row[col_index["question"]]
                expected = row[col_index.get("expected", col_index.get("expected_answer", 0))]
                explanation = row[col_index["explanation"]] if "explanation" in col_index else ""
                difficulty = row[col_index["difficulty"]] if "difficulty" in col_index else "Moyen"
                answer_type = (
                    row[col_index["answer_type"]]
                    if "answer_type" in col_index
                    else row[col_index["kind"]]
                    if "kind" in col_index
                    else "text"
                )
                hint = row[col_index["hint"]] if "hint" in col_index else None
                subject_code = _resolve_subject_code(str(subject_label))
                if subject_code is None:
                    skipped += 1
                    continue
                subject_id = store.subject_id(subject_code)
                if subject_id is None:
                    skipped += 1
                    continue
                chapter_id, skill_id = _lookup_chapter_skill(store, subject_id, str(chapter))
                fp = fingerprint_text("LEGACY_SQLITE", path.name, subject_code, chapter, question, expected)
                cid, is_new = store.insert_content(
                    content_type="EXERCISE",
                    source_type="LEGACY_BANK",
                    subject_id=subject_id,
                    chapter_id=chapter_id,
                    title=f"{chapter} — exercice legacy",
                    statement=str(question),
                    answer_type=str(answer_type or "text"),
                    expected_answer=str(expected) if expected is not None else None,
                    accepted_answers_json=None,
                    correction=str(explanation or ""),
                    hint=str(hint) if hint else None,
                    difficulty_score=difficulty_score(str(difficulty)),
                    difficulty_label=str(difficulty),
                    estimated_seconds=90,
                    brevet_format="EXERCISE",
                    curriculum_2027_compatible="REVIEW",
                    runtime_playable=True,
                    validation_status="AUTO_VALIDATED",
                    quality_score=0.6,
                    fingerprint=fp,
                    semantic_fingerprint=fingerprint_text(question),
                    usage_policy="AVAILABLE_FOR_PRACTICE",
                    skill_id=skill_id,
                )
                if is_new:
                    imported += 1
        finally:
            sc.close()
    return {"imported": imported, "skipped": skipped}


def migrate_duckdb_exam_questions(store: BrevetContentStore | None = None) -> dict[str, int]:
    store = store or BrevetContentStore()
    try:
        rows = store.fetchall(
            """
            SELECT eq.id, e.subject, eq.chapter, eq.question, eq.expected_answer, eq.explanation,
                   eq.answer_type, eq.difficulty, eq.target_seconds
            FROM exam_questions eq
            JOIN exams e ON e.id = eq.exam_id
            """
        )
    except Exception:
        return {"imported": 0, "skipped": 0, "note": "exam_questions unavailable"}
    imported = 0
    skipped = 0
    for row in rows:
        _eq_id, subject_label, chapter, question, expected, explanation, answer_type, difficulty, seconds = row
        subject_code = _resolve_subject_code(str(subject_label))
        if subject_code is None:
            subject_id = store.subject_id(str(subject_label).upper())
        else:
            subject_id = store.subject_id(subject_code)
        if subject_id is None:
            skipped += 1
            continue
        chapter_id, skill_id = _lookup_chapter_skill(store, subject_id, str(chapter))
        fp = fingerprint_text("LEGACY_EXAM_Q", row[0], chapter, question, expected)
        cid, is_new = store.insert_content(
            content_type="EXAM_QUESTION",
            source_type="LEGACY_BANK",
            subject_id=subject_id,
            chapter_id=chapter_id,
            title=f"{chapter} — question d'examen legacy",
            statement=str(question),
            answer_type=str(answer_type or "text"),
            expected_answer=str(expected) if expected is not None else None,
            accepted_answers_json=None,
            correction=str(explanation or ""),
            hint=None,
            difficulty_score=difficulty_score(str(difficulty)),
            difficulty_label=str(difficulty or "Moyen"),
            estimated_seconds=int(seconds or 90),
            brevet_format="EXAM_QUESTION",
            curriculum_2027_compatible="TRUE",
            runtime_playable=True,
            validation_status="AUTO_VALIDATED",
            quality_score=0.65,
            fingerprint=fp,
            semantic_fingerprint=fingerprint_text(question),
            usage_policy="AVAILABLE_FOR_PRACTICE",
            skill_id=skill_id,
        )
        if is_new:
            imported += 1
    return {"imported": imported, "skipped": skipped}
