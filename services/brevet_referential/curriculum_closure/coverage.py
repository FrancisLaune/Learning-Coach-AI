"""Refresh coverage with LCAI-0040 official-count fix and COMPLETE scoring."""

from __future__ import annotations

from typing import Any

from infrastructure.repositories.brevet_content.store import BrevetContentStore
from services.brevet_referential.curriculum_closure.scoring import (
    classify_gap,
    score_coverage_v40,
    subskill_minima,
)
from services.brevet_referential.curriculum_rebuild.target_tree import CORE_SUBJECTS


def _subskill_ok(store: BrevetContentStore, skill_id: int) -> bool:
    subs = store.fetchall(
        "SELECT subskill_id FROM subskills WHERE skill_id = ? AND active",
        [skill_id],
    )
    if not subs:
        return True
    minimum = subskill_minima()
    for (sub_id,) in subs:
        row = store.fetchone(
            """
            SELECT COUNT(DISTINCT csl.content_id)
            FROM content_skill_links csl
            JOIN content_items ci ON ci.content_id = csl.content_id
            WHERE csl.skill_id = ?
              AND csl.subskill_id = ?
              AND ci.runtime_playable
              AND (
                ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED', 'VALIDATED')
                OR ci.source_type = 'OFFICIAL_ARCHIVE'
              )
            """,
            [skill_id, int(sub_id)],
        )
        if int(row[0] or 0) < minimum:
            return False
    return True


def refresh_coverage_v40(store: BrevetContentStore, *, subject_filter: str | None = None) -> list[dict[str, Any]]:
    subjects = [subject_filter] if subject_filter else list(CORE_SUBJECTS)
    rows_out: list[dict[str, Any]] = []
    for subject_code in subjects:
        skills = store.fetchall(
            """
            SELECT sk.skill_id, sk.code, sk.name, sk.brevet_importance,
                   ch.code, ch.name, d.code, d.name, s.code
            FROM skills sk
            JOIN chapters ch ON ch.chapter_id = sk.chapter_id
            JOIN curriculum_domains d ON d.domain_id = ch.domain_id
            JOIN subjects s ON s.subject_id = d.subject_id
            WHERE s.code = ?
              AND sk.active
              AND d.code NOT LIKE '%_CORE'
            ORDER BY d.sort_order, ch.chapter_id, sk.skill_id
            """,
            [subject_code],
        )
        for skill_id, skill_code, skill_name, importance, ch_code, ch_name, dom_code, dom_name, _sc in skills:
            metrics = store.fetchone(
                """
                SELECT
                  COUNT(DISTINCT ci.content_id) FILTER (
                    WHERE ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED', 'VALIDATED')
                      AND ci.runtime_playable
                  ),
                  COUNT(DISTINCT COALESCE(ci.brevet_format, 'UNSPECIFIED')) FILTER (
                    WHERE ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED', 'VALIDATED')
                      AND ci.runtime_playable
                      AND ci.brevet_format IS NOT NULL
                      AND length(ci.brevet_format) > 0
                  ),
                  COUNT(DISTINCT CASE WHEN ci.source_type = 'OFFICIAL_ARCHIVE' THEN ci.content_id END),
                  COUNT(DISTINCT CASE WHEN ci.source_type = 'ARCHIVE_DERIVED'
                        AND ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED', 'VALIDATED')
                        THEN ci.content_id END),
                  COUNT(DISTINCT CASE WHEN ci.source_type = 'BREVET_STYLE'
                        AND ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED', 'VALIDATED')
                        THEN ci.content_id END),
                  COUNT(DISTINCT CASE WHEN ci.source_type = 'AI_GENERATED'
                        AND ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED', 'VALIDATED')
                        THEN ci.content_id END),
                  AVG(CASE
                        WHEN ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED', 'VALIDATED')
                             AND ci.runtime_playable
                             AND (
                               (ci.correction IS NOT NULL AND length(ci.correction) > 0)
                               OR EXISTS (
                                 SELECT 1 FROM content_correction_mechanisms m
                                 WHERE m.content_id = ci.content_id
                               )
                             )
                        THEN 1.0
                        WHEN ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED', 'VALIDATED')
                             AND ci.runtime_playable
                        THEN 0.0
                        ELSE NULL END),
                  COUNT(DISTINCT ci.difficulty_label) FILTER (
                    WHERE ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED', 'VALIDATED')
                      AND ci.runtime_playable
                  ),
                  AVG(CASE
                        WHEN ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED', 'VALIDATED')
                        THEN CASE WHEN ci.runtime_playable THEN 1.0 ELSE 0.0 END
                        ELSE NULL END)
                FROM content_skill_links csl
                JOIN content_items ci ON ci.content_id = csl.content_id
                WHERE csl.skill_id = ?
                """,
                [int(skill_id)],
            )
            assert metrics is not None
            exercise_count = int(metrics[0] or 0)
            family_count = int(metrics[1] or 0)
            official_count = int(metrics[2] or 0)
            archive_derived = int(metrics[3] or 0)
            brevet_style = int(metrics[4] or 0)
            ai_generated = int(metrics[5] or 0)
            correction_cov = float(metrics[6] or 0.0)
            difficulty_span = int(metrics[7] or 0)
            playable_ratio = float(metrics[8] or 0.0)
            sub_ok = _subskill_ok(store, int(skill_id))
            status = score_coverage_v40(
                exercise_count=exercise_count,
                family_count=family_count,
                correction_coverage=correction_cov,
                importance=str(importance),
                playable_ratio=playable_ratio,
                subskill_ok=sub_ok,
            )
            causes = classify_gap(
                exercise_count=exercise_count,
                family_count=family_count,
                correction_coverage=correction_cov,
                importance=str(importance),
                playable_ratio=playable_ratio,
                subskill_ok=sub_ok,
                official_count=official_count,
            )
            store.execute(
                """
                INSERT INTO curriculum_coverage_status(
                    skill_id, coverage_status, exercise_count, family_count, context_count,
                    format_count, official_count, archive_derived_count, brevet_style_count,
                    ai_generated_count, correction_coverage, asset_completeness,
                    difficulty_span, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0, ?, now())
                ON CONFLICT (skill_id) DO UPDATE SET
                    coverage_status = excluded.coverage_status,
                    exercise_count = excluded.exercise_count,
                    family_count = excluded.family_count,
                    format_count = excluded.format_count,
                    official_count = excluded.official_count,
                    archive_derived_count = excluded.archive_derived_count,
                    brevet_style_count = excluded.brevet_style_count,
                    ai_generated_count = excluded.ai_generated_count,
                    correction_coverage = excluded.correction_coverage,
                    difficulty_span = excluded.difficulty_span,
                    updated_at = now()
                """,
                [
                    int(skill_id),
                    status,
                    exercise_count,
                    family_count,
                    family_count,
                    family_count,
                    official_count,
                    archive_derived,
                    brevet_style,
                    ai_generated,
                    correction_cov,
                    difficulty_span,
                ],
            )
            rows_out.append(
                {
                    "subject": subject_code,
                    "domain": dom_name,
                    "domain_code": dom_code,
                    "chapter": ch_name,
                    "chapter_code": ch_code,
                    "skill": skill_name,
                    "skill_code": skill_code,
                    "skill_id": int(skill_id),
                    "importance": importance,
                    "exercise_count": exercise_count,
                    "family_count": family_count,
                    "official_count": official_count,
                    "archive_derived_count": archive_derived,
                    "brevet_style_count": brevet_style,
                    "ai_generated_count": ai_generated,
                    "correction_coverage": correction_cov,
                    "difficulty_span": difficulty_span,
                    "playable_ratio": playable_ratio,
                    "coverage_status": status,
                    "gap_causes": causes,
                    "subskill_ok": sub_ok,
                }
            )
    return rows_out
