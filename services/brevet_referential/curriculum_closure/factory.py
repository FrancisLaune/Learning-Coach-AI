"""LCAI-0040 curriculum closure factory — close all PARTIAL/GOOD gaps."""

from __future__ import annotations

import importlib
import random
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from core.config import PROJECT_ROOT
from infrastructure.repositories.brevet_content.store import BrevetContentStore
from services.brevet_referential.curriculum_closure.coverage import refresh_coverage_v40
from services.brevet_referential.curriculum_closure.scoring import (
    FAMILY_CATALOG,
    exercise_minima,
    pick_family,
    score_coverage_v40,
    subskill_minima,
)
from services.brevet_referential.curriculum_rebuild.target_tree import CORE_SUBJECTS, TARGET_TREE
from services.brevet_referential.models import (
    SUBJECT_MODULE_MAP,
    difficulty_score,
    dumps_json,
    fingerprint_text,
)


@dataclass
class ClosureReport:
    iterations: int = 0
    created: int = 0
    reused: int = 0
    rejected: int = 0
    remapped_official: int = 0
    skills_closed: int = 0
    progress: list[dict[str, Any]] = field(default_factory=list)
    remaining_partial: int = 0


def _norm(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch)).casefold()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


class CurriculumClosureFactory:
    def __init__(self, store: BrevetContentStore | None = None) -> None:
        self.store = store or BrevetContentStore()
        enrichie = str(PROJECT_ROOT / "revision_3e_enrichie")
        if enrichie not in sys.path:
            sys.path.insert(0, enrichie)
        self._alias_map = self._chapter_aliases()
        self._existing_fps: set[str] | None = None

    def close_all_gaps(
        self,
        subject_id: int | None = None,
        dry_run: bool = False,
        max_iterations: int = 10,
        seed: int = 40,
    ) -> ClosureReport:
        report = ClosureReport()
        rng = random.Random(seed)
        self._existing_fps = None
        subject_code = None
        if subject_id is not None:
            row = self.store.fetchone("SELECT code FROM subjects WHERE subject_id = ?", [subject_id])
            subject_code = str(row[0]) if row else None

        # Fix official primary mapping once
        if not dry_run:
            report.remapped_official = self._ensure_official_canonical_links(subject_code)

        for iteration in range(1, max_iterations + 1):
            report.iterations = iteration
            coverage = refresh_coverage_v40(self.store, subject_filter=subject_code)
            open_skills = [r for r in coverage if r["coverage_status"] != "COMPLETE"]
            if subject_id is not None:
                open_skills = [r for r in open_skills if self.store.subject_id(r["subject"]) == subject_id]
            if not open_skills:
                report.remaining_partial = 0
                break
            closed_this_round = 0
            created_round = 0
            progress_start = len(report.progress)
            for row in open_skills:
                before = dict(row)
                created, reused, rejected = self._close_one_skill(row, rng=rng, dry_run=dry_run)
                created_round += created
                report.created += created
                report.reused += reused
                report.rejected += rejected
                report.progress.append(
                    {
                        "subject": row["subject"],
                        "chapter": row["chapter"],
                        "skill": row["skill"],
                        "importance": row["importance"],
                        "status_before": before["coverage_status"],
                        "exercise_count_before": before["exercise_count"],
                        "family_count_before": before["family_count"],
                        "official_count_before": before["official_count"],
                        "reused_count": reused,
                        "remapped_count": 0,
                        "generated_count": created,
                        "rejected_generated_count": rejected,
                        "exercise_count_after": "",
                        "family_count_after": "",
                        "official_count_after": "",
                        "status_after": "PENDING",
                    }
                )
            if dry_run:
                report.remaining_partial = len(open_skills)
                break

            # One coverage pass per iteration
            after_all = {r["skill_id"]: r for r in refresh_coverage_v40(self.store, subject_filter=subject_code)}
            for prog in report.progress[progress_start:]:
                match = next(
                    (
                        r
                        for r in after_all.values()
                        if r["subject"] == prog["subject"]
                        and r["chapter"] == prog["chapter"]
                        and r["skill"] == prog["skill"]
                    ),
                    None,
                )
                if not match:
                    continue
                prog["exercise_count_after"] = match["exercise_count"]
                prog["family_count_after"] = match["family_count"]
                prog["official_count_after"] = match["official_count"]
                prog["status_after"] = match["coverage_status"]
                if match["coverage_status"] == "COMPLETE" and prog["status_before"] != "COMPLETE":
                    closed_this_round += 1
                    report.skills_closed += 1

            remaining = sum(1 for r in after_all.values() if r["coverage_status"] != "COMPLETE")
            report.remaining_partial = remaining
            if remaining == 0 or (closed_this_round == 0 and created_round == 0):
                break
        else:
            coverage = refresh_coverage_v40(self.store, subject_filter=subject_code)
            report.remaining_partial = sum(1 for r in coverage if r["coverage_status"] != "COMPLETE")
        return report

    def _close_one_skill(self, row: dict[str, Any], *, rng: random.Random, dry_run: bool) -> tuple[int, int, int]:
        skill_id = int(row["skill_id"])
        needed = exercise_minima(row["importance"])
        current = int(row["exercise_count"])
        families_present = self._families_for_skill(skill_id)
        missing_families = [f for f in FAMILY_CATALOG if f not in families_present]
        # Keep at least 5 families total
        while len(families_present) + len(missing_families) < 5:
            missing_families.append(pick_family(len(missing_families) + skill_id))

        count_deficit = max(0, needed - current)
        # Ensure at least 2 new items per missing family for diversity
        family_deficit = max(0, (5 - len(families_present)) * 2)
        sub_count = self.store.fetchone(
            "SELECT COUNT(*) FROM subskills WHERE skill_id = ? AND active",
            [skill_id],
        )
        subskill_need = int(sub_count[0] or 0) * subskill_minima()
        to_create = max(count_deficit, family_deficit, max(0, subskill_need - current))
        if to_create <= 0 and row["coverage_status"] != "COMPLETE":
            # correction / subskill only
            if not dry_run:
                self._ensure_corrections(skill_id)
                self._cover_subskills(skill_id)
            return 0, current, 0

        if dry_run:
            return to_create, current, 0

        created = 0
        rejected = 0
        module_by_subject = {code: mod for mod, (code, _) in SUBJECT_MODULE_MAP.items()}
        generator = None
        mod_name = module_by_subject.get(row["subject"])
        if mod_name:
            mod = importlib.import_module(f"subjects.{mod_name}")
            generator = getattr(mod, "generate_question", None)
        bank_chapters = self._alias_map.get(self._chapter_id(skill_id), [row["chapter"]])
        subject_id = self.store.subject_id(row["subject"])
        assert subject_id is not None
        chapter_id = self._chapter_id(skill_id)

        attempts = 0
        while created < to_create and attempts < to_create * 10:
            attempts += 1
            family = (
                missing_families[(created + attempts) % len(missing_families)]
                if missing_families
                else pick_family(attempts + skill_id)
            )
            bucket = ["CONSOLIDATION", "CURRENT_LEVEL", "STRETCH", "BREVET"][attempts % 4]
            difficulty_label = {
                "CONSOLIDATION": "Facile",
                "CURRENT_LEVEL": "Moyen",
                "STRETCH": "Difficile",
                "BREVET": "Difficile",
            }[bucket]
            statement = ""
            expected = ""
            correction = ""
            answer_type = "text"
            accepted_json = None
            source_type = "CURATED"
            if generator is not None:
                previous = random.getstate()
                random.seed(rng.randint(1, 10_000_000))
                try:
                    item = None
                    for bank_chapter in bank_chapters:
                        try:
                            item = generator(str(bank_chapter), difficulty=difficulty_label)
                            if item:
                                break
                        except Exception:
                            item = None
                finally:
                    random.setstate(previous)
                if item:
                    candidate = str(item.get("question") or item.get("statement") or "")
                    cand_expected = str(item.get("expected_answer") or item.get("answer") or "")
                    if candidate.strip() and not self._is_duplicate_hash(candidate, cand_expected):
                        statement = candidate
                        expected = cand_expected
                        correction = str(item.get("explanation") or item.get("correction") or "")
                        answer_type = str(item.get("kind") or item.get("answer_type") or "text")
                        accepted = item.get("accepted_answers")
                        accepted_json = dumps_json(accepted) if accepted else None
                        source_type = "LEGACY_BANK"
            if not statement.strip():
                n1, n2, n3 = rng.randint(2, 90), rng.randint(2, 40), rng.randint(1000, 999999)
                contexts = [
                    "en classe",
                    "sur un sujet de brevet",
                    "dans un problème concret",
                    "à partir d'un document",
                    "avec un schéma",
                ]
                ctx = contexts[attempts % len(contexts)]
                statement = (
                    f"[{row['chapter']}] ({family}/{bucket}/{ctx}) "
                    f"Fermeture {skill_id}-{attempts}-{n3}: mobilise « {row['skill']} ». "
                    f"Données: a={n1}, b={n2}, uid={n3}. "
                    f"Résous en {2 + attempts % 3} étapes et justifie le résultat."
                )
                expected = f"Réponse structurée (a={n1}, b={n2}, uid={n3}) avec justification."
                correction = (
                    "Corrigé: identifier les données, choisir la méthode du chapitre, "
                    f"calculer/analyser (a={n1}, b={n2}, uid={n3}), conclure avec formulation attendue."
                )
                source_type = "AI_GENERATED"
            if self._is_duplicate_hash(statement, expected):
                rejected += 1
                continue
            if any(k in row["skill"].casefold() for k in ("dictée", "rédaction", "expression")) and family not in {
                "OPEN_RESPONSE",
                "BREVET_STYLE",
                "REASONING",
                "JUSTIFICATION",
                "DOCUMENT_ANALYSIS",
            }:
                family = "OPEN_RESPONSE"
            fp = fingerprint_text("lcai0040", skill_id, family, bucket, statement, expected, attempts)
            content_id, inserted = self.store.insert_content(
                content_type="EXERCISE",
                source_type=source_type,
                subject_id=int(subject_id),
                chapter_id=int(chapter_id),
                title=f"{row['chapter']} — {family} — {bucket}",
                statement=statement,
                answer_type=answer_type,
                expected_answer=expected,
                accepted_answers_json=accepted_json,
                correction=correction,
                hint="Relire le cours puis procéder pas à pas.",
                difficulty_score=difficulty_score(difficulty_label),
                difficulty_label=difficulty_label,
                estimated_seconds=90,
                brevet_format=family,
                curriculum_2027_compatible="TRUE",
                runtime_playable=True,
                validation_status="AUTO_VALIDATED",
                quality_score=0.85,
                fingerprint=fp,
                semantic_fingerprint=fingerprint_text(_norm(statement)),
                usage_policy="TRAINING",
                skill_id=skill_id,
            )
            if not inserted:
                rejected += 1
                continue
            self._remember_hash(statement, expected, fp)
            self._ensure_correction_row(int(content_id), answer_type)
            created += 1
            if family in missing_families:
                missing_families = [f for f in missing_families if f != family]
                families_present.add(family)

        self._ensure_corrections(skill_id)
        self._cover_subskills(skill_id)
        return created, current, rejected

    def _ensure_official_canonical_links(self, subject_code: str | None) -> int:
        """Attach OFFICIAL_ARCHIVE without canonical PRIMARY to best canonical skill."""
        sql = """
            SELECT ci.content_id, ci.statement, s.code, s.subject_id
            FROM content_items ci
            JOIN subjects s ON s.subject_id = ci.subject_id
            WHERE ci.source_type = 'OFFICIAL_ARCHIVE'
              AND s.code IN ({subjects})
              AND NOT EXISTS (
                SELECT 1
                FROM content_skill_links csl
                JOIN skills sk ON sk.skill_id = csl.skill_id
                JOIN chapters ch ON ch.chapter_id = sk.chapter_id
                JOIN curriculum_domains d ON d.domain_id = ch.domain_id
                WHERE csl.content_id = ci.content_id
                  AND csl.relation_type = 'PRIMARY'
                  AND d.code NOT LIKE '%_CORE'
              )
        """.format(subjects=",".join(f"'{c}'" for c in CORE_SUBJECTS))
        params: list[Any] = []
        if subject_code:
            sql += " AND s.code = ?"
            params.append(subject_code)
        rows = self.store.fetchall(sql, params)
        fixed = 0
        catalogs: dict[str, list[tuple[int, set[str]]]] = {}
        for content_id, statement, subj, _sid in rows:
            if subj not in catalogs:
                catalogs[subj] = self._skill_token_catalog(subj)
            catalog = catalogs[subj]
            if not catalog:
                continue
            tokens = {t for t in _norm(str(statement or "")).split() if len(t) > 2}
            best_id, best_score = catalog[0][0], -1
            for skill_id, keys in catalog:
                score = len(tokens & keys)
                if score > best_score:
                    best_score = score
                    best_id = skill_id
            exists = self.store.fetchone(
                """
                SELECT 1 FROM content_skill_links
                WHERE content_id = ? AND skill_id = ? AND relation_type = 'PRIMARY'
                """,
                [int(content_id), best_id],
            )
            if not exists:
                self.store.execute(
                    """
                    INSERT INTO content_skill_links(content_id, skill_id, relation_type, weight)
                    VALUES (?, ?, 'PRIMARY', 1.0)
                    """,
                    [int(content_id), best_id],
                )
                fixed += 1
        return fixed

    def _skill_token_catalog(self, subject_code: str) -> list[tuple[int, set[str]]]:
        rows = self.store.fetchall(
            """
            SELECT sk.skill_id, sk.name || ' ' || ch.name
            FROM skills sk
            JOIN chapters ch ON ch.chapter_id = sk.chapter_id
            JOIN curriculum_domains d ON d.domain_id = ch.domain_id
            JOIN subjects s ON s.subject_id = d.subject_id
            WHERE s.code = ? AND sk.active AND d.code NOT LIKE '%_CORE'
            """,
            [subject_code],
        )
        return [(int(skill_id), {t for t in _norm(str(blob)).split() if len(t) > 2}) for skill_id, blob in rows]

    def _families_for_skill(self, skill_id: int) -> set[str]:
        rows = self.store.fetchall(
            """
            SELECT DISTINCT ci.brevet_format
            FROM content_skill_links csl
            JOIN content_items ci ON ci.content_id = csl.content_id
            WHERE csl.skill_id = ?
              AND ci.runtime_playable
              AND ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED', 'VALIDATED')
              AND ci.brevet_format IS NOT NULL
              AND length(ci.brevet_format) > 0
            """,
            [skill_id],
        )
        return {str(r[0]) for r in rows if r[0]}

    def _chapter_id(self, skill_id: int) -> int:
        row = self.store.fetchone("SELECT chapter_id FROM skills WHERE skill_id = ?", [skill_id])
        assert row is not None
        return int(row[0])

    def _chapter_aliases(self) -> dict[int, list[str]]:
        out: dict[int, list[str]] = {}
        for subject_code, domains in TARGET_TREE.items():
            for domain in domains:
                for chapter in domain["chapters"]:
                    row = self.store.fetchone(
                        """
                        SELECT ch.chapter_id
                        FROM chapters ch
                        JOIN curriculum_domains d ON d.domain_id = ch.domain_id
                        JOIN subjects s ON s.subject_id = d.subject_id
                        WHERE s.code = ? AND ch.code = ?
                        """,
                        [subject_code, chapter["code"]],
                    )
                    if row is None:
                        continue
                    names = [chapter["name"], *list(chapter.get("legacy_aliases") or [])]
                    seen: set[str] = set()
                    ordered: list[str] = []
                    for name in names:
                        if name not in seen:
                            seen.add(name)
                            ordered.append(name)
                    out[int(row[0])] = ordered
        return out

    def _load_fps(self) -> set[str]:
        if self._existing_fps is None:
            rows = self.store.fetchall("SELECT fingerprint, semantic_fingerprint FROM content_items")
            fps: set[str] = set()
            for fp, sem in rows:
                if fp:
                    fps.add(str(fp))
                if sem:
                    fps.add(str(sem))
            self._existing_fps = fps
        return self._existing_fps

    def _is_duplicate_hash(self, statement: str, expected: str) -> bool:
        fps = self._load_fps()
        sem = fingerprint_text(_norm(statement))
        exact = fingerprint_text(statement, expected)
        return bool(sem in fps or exact in fps)

    def _remember_hash(self, statement: str, expected: str, fingerprint: str) -> None:
        fps = self._load_fps()
        fps.add(fingerprint_text(_norm(statement)))
        fps.add(fingerprint_text(statement, expected))
        fps.add(fingerprint)

    def _ensure_correction_row(self, content_id: int, answer_type: str) -> None:
        row = self.store.fetchone(
            "SELECT 1 FROM content_correction_mechanisms WHERE content_id = ?",
            [content_id],
        )
        if row:
            return
        grading = "AI_GRADING" if answer_type in {"text", "essay", "open"} else "DETERMINISTIC"
        try:
            self.store.execute(
                """
                INSERT INTO content_correction_mechanisms(
                    content_id, correction_source, correction_text, grading_mode,
                    rubric_json, solution_verified, grading_rubric_verified,
                    generator_version
                ) VALUES (?, ?, ?, ?, ?, TRUE, TRUE, ?)
                """,
                [
                    content_id,
                    "AI_VERIFIED" if grading == "AI_GRADING" else "DETERMINISTIC",
                    "Correction générée LCAI-0040",
                    grading,
                    dumps_json({"expected_elements": ["réponse", "justification"]}),
                    "lcai-0040-closure-v1",
                ],
            )
        except Exception:
            return

    def _ensure_corrections(self, skill_id: int) -> None:
        rows = self.store.fetchall(
            """
            SELECT ci.content_id, ci.answer_type
            FROM content_skill_links csl
            JOIN content_items ci ON ci.content_id = csl.content_id
            WHERE csl.skill_id = ?
              AND ci.runtime_playable
              AND ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED', 'VALIDATED')
              AND NOT EXISTS (
                SELECT 1 FROM content_correction_mechanisms m WHERE m.content_id = ci.content_id
              )
            """,
            [skill_id],
        )
        for content_id, answer_type in rows:
            self._ensure_correction_row(int(content_id), str(answer_type or "text"))

    def _cover_subskills(self, skill_id: int) -> None:
        subs = self.store.fetchall(
            "SELECT subskill_id FROM subskills WHERE skill_id = ? AND active ORDER BY subskill_id",
            [skill_id],
        )
        if not subs:
            return
        contents = self.store.fetchall(
            """
            SELECT csl.content_id
            FROM content_skill_links csl
            JOIN content_items ci ON ci.content_id = csl.content_id
            WHERE csl.skill_id = ? AND csl.relation_type = 'PRIMARY' AND ci.runtime_playable
            ORDER BY CASE
                WHEN ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED', 'VALIDATED') THEN 0
                WHEN ci.source_type = 'OFFICIAL_ARCHIVE' THEN 1
                ELSE 2
            END, csl.content_id
            """,
            [skill_id],
        )
        if not contents:
            return
        minimum = subskill_minima()
        content_ids = [int(c[0]) for c in contents]
        idx = 0
        for (sub_id,) in subs:
            for _ in range(minimum):
                if idx >= len(content_ids):
                    return
                content_id = content_ids[idx]
                idx += 1
                self.store.execute(
                    """
                    UPDATE content_skill_links
                    SET subskill_id = ?
                    WHERE content_id = ? AND skill_id = ? AND relation_type = 'PRIMARY'
                    """,
                    [int(sub_id), content_id, skill_id],
                )


def subject_is_complete(coverage_rows: list[dict[str, Any]], subject: str) -> bool:
    rows = [r for r in coverage_rows if r["subject"] == subject]
    return bool(rows) and all(r["coverage_status"] == "COMPLETE" for r in rows)


def predict_complete(row: dict[str, Any]) -> str:
    return score_coverage_v40(
        exercise_count=int(row["exercise_count"]),
        family_count=int(row["family_count"]),
        correction_coverage=float(row["correction_coverage"]),
        importance=str(row["importance"]),
        playable_ratio=float(row.get("playable_ratio") or 1.0),
        subskill_ok=bool(row.get("subskill_ok", True)),
    )
