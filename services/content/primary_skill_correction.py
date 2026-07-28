"""Deterministic skill-code resolution against authoritative V2 curriculum."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum
from pathlib import Path
from typing import Any

from infrastructure.database.v2 import connect_v2
from services.content.primary_integration import PRIMARY_GRADES, validate_target_key

GRADE_TOKEN = {
    "FR-CM1": "CM1",
    "FR-CM2": "CM2",
    "FR-6E": "6E",
    "FR-5E": "5E",
}

SUFFIX_SUBSTITUTIONS = (
    ("-TENSES", "-TENSE"),
    ("-SIGNS", "-SIGN"),
    ("-TRIANGLES", "-TRIANGLE"),
    ("-SEPARATION", "-SEPARATE"),
    ("-MANAGE", "-MANAGEMENT"),
    ("-ADAPT", "-ADAPTATION"),
    ("-EQUALITY", "-EQUATION"),
    ("-COHERENCE", "-COHESION"),
    ("-IMPACT", "-HUMAN_IMPACT"),
)

FUZZY_MIN_RATIO = 0.96


class SkillCorrectionClass(StrEnum):
    DETERMINISTIC_FIX = "DETERMINISTIC_FIX"
    AMBIGUOUS_MAPPING = "AMBIGUOUS_MAPPING"
    NO_MATCH = "NO_MATCH"


@dataclass(frozen=True, slots=True)
class CurriculumSkillPlacement:
    program_code: str
    grade_code: str
    subject_code: str
    chapter_code: str
    skill_code: str


@dataclass(frozen=True, slots=True)
class SkillResolution:
    classification: SkillCorrectionClass
    corrected_skill_code: str | None
    reason: str
    method: str
    curriculum_match: dict[str, str] | None
    candidate_matches: tuple[str, ...] = ()


def load_curriculum_placements(database_path: Path | None = None) -> list[CurriculumSkillPlacement]:
    connection = connect_v2(database_path, read_only=True)
    try:
        rows = connection.execute(
            """
            SELECT p.code, sl.code, su.code, cc.stable_code, s.code
            FROM curriculum_skill_details csd
            JOIN curriculum_chapters cc ON cc.id=csd.chapter_id
            JOIN programs p ON p.id=cc.program_id
            JOIN school_levels sl ON sl.id=cc.grade_level_id
            JOIN subjects su ON su.id=cc.subject_id
            JOIN skills s ON s.id=csd.skill_id
            WHERE csd.status='approved' AND cc.status='approved'
              AND sl.code IN (SELECT unnest(?))
            """,
            [list(PRIMARY_GRADES)],
        ).fetchall()
    finally:
        connection.close()
    return [
        CurriculumSkillPlacement(str(r[0]), str(r[1]), str(r[2]), str(r[3]), str(r[4]))
        for r in rows
    ]


def _chapter_index(
    placements: list[CurriculumSkillPlacement],
) -> dict[tuple[str, str, str, str], list[str]]:
    index: dict[tuple[str, str, str, str], list[str]] = {}
    for item in placements:
        key = (item.program_code, item.grade_code, item.subject_code, item.chapter_code)
        index.setdefault(key, []).append(item.skill_code)
    return index


def _skill_suffix(skill_code: str) -> str:
    if skill_code.startswith("SK-ENR-"):
        return skill_code[len("SK-ENR-") :]
    if skill_code.startswith("SK-"):
        return skill_code[len("SK-") :]
    return skill_code


def _typo_variants(skill_code: str, grade_code: str, chapter_code: str) -> list[str]:
    variants = [skill_code]
    grade_token = GRADE_TOKEN[grade_code]
    replacements = [
        (f"FREN{grade_token}", f"FRENCH-{grade_token}"),
        (f"FRENCH{grade_token}", f"FRENCH-{grade_token}"),
    ]
    current = skill_code
    for old, new in replacements:
        if old in current:
            candidate = current.replace(old, new, 1)
            if candidate not in variants:
                variants.append(candidate)
            current = candidate
    if "FRENCH-CM2-GRAMMAR-" in skill_code or "FRENCM2-GRAMMAR-" in skill_code:
        variants.append(skill_code.replace("GRAMMAR-", "LANGUAGE-").replace("FRENCM2", "FRENCH-CM2"))
    if "LEXICON-LEXICAL_SPELLING" in skill_code:
        variants.append(skill_code.replace("LEXICON-LEXICAL_SPELLING", "SPELLING-LEXICAL"))
    for old, new in SUFFIX_SUBSTITUTIONS:
        if old in skill_code:
            candidate = skill_code.replace(old, new)
            if candidate not in variants:
                variants.append(candidate)
    if skill_code.endswith("-ADD"):
        variants.append(skill_code[:-4] + "-ADD_SUB")
    if skill_code.endswith("-LINE") and "NUMBERS" in chapter_code:
        variants.append(skill_code.replace("-LINE", "-LOCATE"))
    if "-PROPORTIONALITY-" in skill_code and skill_code.endswith("-DATA"):
        variants.append(skill_code.replace("-DATA", "-READ_DATA"))
    return variants


def _fuzzy_unique_match(primary_skill_code: str, chapter_skills: list[str]) -> str | None:
    scored = [(SequenceMatcher(None, primary_skill_code, skill).ratio(), skill) for skill in chapter_skills]
    strong = [(ratio, skill) for ratio, skill in scored if ratio >= FUZZY_MIN_RATIO]
    if len(strong) == 1:
        return strong[0][1]
    return None


def resolve_skill_code(
    *,
    program_code: str,
    grade_code: str,
    subject_code: str,
    chapter_code: str,
    primary_skill_code: str,
    placements: list[CurriculumSkillPlacement],
    chapter_index: dict[tuple[str, str, str, str], list[str]] | None = None,
) -> SkillResolution:
    chapter_index = chapter_index or _chapter_index(placements)
    key = (program_code, grade_code, subject_code, chapter_code)
    chapter_skills = chapter_index.get(key, [])
    valid_keys = {
        (p.program_code, p.grade_code, p.subject_code, p.chapter_code, p.skill_code) for p in placements
    }

    def _match(skill_code: str) -> SkillResolution | None:
        placement_key = (program_code, grade_code, subject_code, chapter_code, skill_code)
        if placement_key not in valid_keys:
            return None
        return SkillResolution(
            SkillCorrectionClass.DETERMINISTIC_FIX,
            skill_code,
            "Authoritative curriculum placement confirmed.",
            "exact_curriculum_match",
            {
                "program_code": program_code,
                "grade_code": grade_code,
                "subject_code": subject_code,
                "chapter_code": chapter_code,
                "primary_skill_code": skill_code,
            },
            (skill_code,),
        )

    direct = _match(primary_skill_code)
    if direct:
        return direct

    for variant in _typo_variants(primary_skill_code, grade_code, chapter_code):
        if variant == primary_skill_code:
            continue
        found = _match(variant)
        if found:
            method = "typo_variant" if "FREN" in primary_skill_code else "suffix_substitution"
            return SkillResolution(
                found.classification,
                found.corrected_skill_code,
                f"Resolved: {primary_skill_code} -> {variant}",
                method,
                found.curriculum_match,
                found.candidate_matches,
            )

    invalid_suffix = _skill_suffix(primary_skill_code)
    # Normalize suffix aliases seen in preparation packs
    suffix_aliases = [invalid_suffix]
    if invalid_suffix.endswith("-ADAPT"):
        suffix_aliases.append(invalid_suffix.replace("-ADAPT", "-ADAPTATION"))
    if invalid_suffix.endswith("-ADD"):
        suffix_aliases.append(invalid_suffix.replace("-ADD", "-ADD_SUB"))
    if "GRAMMAR-" in invalid_suffix:
        suffix_aliases.append(invalid_suffix.replace("GRAMMAR-", "LANGUAGE-"))

    suffix_matches: set[str] = set()
    for skill in chapter_skills:
        skill_suffix = _skill_suffix(skill)
        for alias in suffix_aliases:
            if skill_suffix == alias or skill_suffix.endswith(alias.split("-", 1)[-1]):
                suffix_matches.add(skill)
    # Prefer exact suffix tail match within chapter
    tail = primary_skill_code.split("-")[-1]
    tail_matches = [s for s in chapter_skills if s.endswith(f"-{tail}") or s.split("-")[-1] == tail]
    if len(tail_matches) == 1:
        return _match(tail_matches[0]) or SkillResolution(
            SkillCorrectionClass.DETERMINISTIC_FIX,
            tail_matches[0],
            f"Unique chapter suffix match on '-{tail}'.",
            "chapter_suffix_unique",
            {
                "program_code": program_code,
                "grade_code": grade_code,
                "subject_code": subject_code,
                "chapter_code": chapter_code,
                "primary_skill_code": tail_matches[0],
            },
            tuple(tail_matches),
        )

    # Subject-grade anchored suffix: MATHEMATICS-5E-NUMBERS-ADD -> NUMBERS-ADD
    grade_token = GRADE_TOKEN[grade_code]
    pattern = re.compile(rf"{re.escape(subject_code)}-{re.escape(grade_token)}-(.+)$")
    match = pattern.search(invalid_suffix)
    if match:
        topic_suffix = match.group(1)
        topic_matches = [s for s in chapter_skills if s.endswith(topic_suffix) or topic_suffix in s]
        if len(topic_matches) == 1:
            return _match(topic_matches[0]) or SkillResolution(
                SkillCorrectionClass.DETERMINISTIC_FIX,
                topic_matches[0],
                f"Unique topic suffix match for '{topic_suffix}'.",
                "topic_suffix_unique",
                {
                    "program_code": program_code,
                    "grade_code": grade_code,
                    "subject_code": subject_code,
                    "chapter_code": chapter_code,
                    "primary_skill_code": topic_matches[0],
                },
                tuple(topic_matches),
            )
        if len(topic_matches) > 1:
            return SkillResolution(
                SkillCorrectionClass.AMBIGUOUS_MAPPING,
                None,
                f"Multiple chapter skills match topic suffix '{topic_suffix}'.",
                "topic_suffix_ambiguous",
                None,
                tuple(sorted(topic_matches)),
            )

    if len(suffix_matches) == 1:
        skill = next(iter(suffix_matches))
        return _match(skill) or SkillResolution(
            SkillCorrectionClass.DETERMINISTIC_FIX,
            skill,
            "Unique suffix alias match within chapter.",
            "suffix_alias_unique",
            {
                "program_code": program_code,
                "grade_code": grade_code,
                "subject_code": subject_code,
                "chapter_code": chapter_code,
                "primary_skill_code": skill,
            },
            tuple(suffix_matches),
        )
    if len(suffix_matches) > 1:
        return SkillResolution(
            SkillCorrectionClass.AMBIGUOUS_MAPPING,
            None,
            "Multiple suffix alias matches within chapter.",
            "suffix_alias_ambiguous",
            None,
            tuple(sorted(suffix_matches)),
        )

    fuzzy = _fuzzy_unique_match(primary_skill_code, chapter_skills)
    if fuzzy:
        found = _match(fuzzy)
        if found:
            return SkillResolution(
                found.classification,
                found.corrected_skill_code,
                f"Unique fuzzy curriculum match ({FUZZY_MIN_RATIO}+): {primary_skill_code} -> {fuzzy}",
                "fuzzy_unique",
                found.curriculum_match,
                (fuzzy,),
            )

    return SkillResolution(
        SkillCorrectionClass.NO_MATCH,
        None,
        "No authoritative curriculum skill matches the prepared target.",
        "no_match",
        None,
        (),
    )


def resolve_all_invalid_records(
    records: list[dict[str, Any]],
    valid_keys: set[tuple[str, str, str, str, str]],
    *,
    database_path: Path | None = None,
) -> dict[str, Any]:
    from services.content.primary_integration import candidate_from_record

    placements = load_curriculum_placements(database_path)
    chapter_index = _chapter_index(placements)
    corrections: list[dict[str, Any]] = []
    counts: dict[str, int] = {"DETERMINISTIC_FIX": 0, "AMBIGUOUS_MAPPING": 0, "NO_MATCH": 0, "ALREADY_VALID": 0}

    for record in records:
        candidate = candidate_from_record(record["candidate_data"])
        target = candidate.target
        key = (
            target.program_code,
            target.grade_code,
            target.subject_code,
            target.chapter_code,
            target.primary_skill_code,
        )
        if key in valid_keys:
            counts["ALREADY_VALID"] += 1
            continue
        resolution = resolve_skill_code(
            program_code=target.program_code,
            grade_code=target.grade_code,
            subject_code=target.subject_code,
            chapter_code=target.chapter_code,
            primary_skill_code=target.primary_skill_code,
            placements=placements,
            chapter_index=chapter_index,
        )
        counts[resolution.classification.value] += 1
        if resolution.classification is not SkillCorrectionClass.DETERMINISTIC_FIX:
            corrections.append(
                {
                    "code": record["code"],
                    "grade": record["grade"],
                    "subject": record["subject"],
                    "chapter": record["chapter"],
                    "original_primary_skill_code": target.primary_skill_code,
                    "classification": resolution.classification.value,
                    "corrected_primary_skill_code": resolution.corrected_skill_code,
                    "correction_reason": resolution.reason,
                    "correction_method": resolution.method,
                    "curriculum_match": resolution.curriculum_match,
                    "candidate_matches": list(resolution.candidate_matches),
                }
            )
    return {"counts": counts, "exceptions": corrections}


def apply_skill_corrections(
    records: list[dict[str, Any]],
    *,
    database_path: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply deterministic skill-code fixes in-memory with full traceability."""
    from services.content.primary_integration import candidate_from_record, load_valid_curriculum_keys

    valid_keys = load_valid_curriculum_keys(database_path)
    placements = load_curriculum_placements(database_path)
    chapter_index = _chapter_index(placements)
    corrected_records: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    counts: dict[str, int] = Counter()

    for record in records:
        item = dict(record)
        candidate_data = dict(record["candidate_data"])
        target = dict(candidate_data["target"])
        candidate = candidate_from_record(candidate_data)
        key = (
            candidate.target.program_code,
            candidate.target.grade_code,
            candidate.target.subject_code,
            candidate.target.chapter_code,
            candidate.target.primary_skill_code,
        )
        if key in valid_keys:
            counts["ALREADY_VALID"] += 1
            corrected_records.append(item)
            continue
        resolution = resolve_skill_code(
            program_code=candidate.target.program_code,
            grade_code=candidate.target.grade_code,
            subject_code=candidate.target.subject_code,
            chapter_code=candidate.target.chapter_code,
            primary_skill_code=candidate.target.primary_skill_code,
            placements=placements,
            chapter_index=chapter_index,
        )
        counts[resolution.classification.value] += 1
        if resolution.classification is SkillCorrectionClass.DETERMINISTIC_FIX and resolution.corrected_skill_code:
            trace = {
                "original_primary_skill_code": candidate.target.primary_skill_code,
                "corrected_primary_skill_code": resolution.corrected_skill_code,
                "correction_reason": resolution.reason,
                "correction_method": resolution.method,
                "curriculum_match": resolution.curriculum_match,
            }
            target["primary_skill_code"] = resolution.corrected_skill_code
            candidate_data["target"] = target
            candidate_data.setdefault("metadata", {})["skill_correction"] = trace
            item["candidate_data"] = candidate_data
            item["skill"] = resolution.corrected_skill_code
            applied.append({"code": record["code"], **trace})
        corrected_records.append(item)

    return corrected_records, {
        "counts": dict(counts),
        "applied": applied,
        "exceptions": [
            e
            for e in resolve_all_invalid_records(records, valid_keys, database_path=database_path)["exceptions"]
        ],
    }


def repair_qcm_duplicate_choices(candidate_data: dict[str, Any]) -> dict[str, Any]:
    """Replace accidental duplicate QCM distractors when deterministically possible."""
    from domain.content.factory import normalized_content_fingerprint

    answer = candidate_data.get("answer", {})
    if answer.get("kind") not in {"single_choice", "multiple_choice"}:
        return {"status": "NOT_QCM", "candidate_data": candidate_data, "changed": False}
    options = [str(item).strip() for item in answer.get("options", [])]
    if len(options) < 2:
        return {"status": "INVALID_QCM", "candidate_data": candidate_data, "changed": False}
    fingerprints = [normalized_content_fingerprint(item) for item in options]
    if len(set(fingerprints)) == len(fingerprints):
        return {"status": "VALID", "candidate_data": candidate_data, "changed": False}
    seen: set[str] = set()
    repaired: list[str] = []
    changed = False
    for index, (option, fingerprint) in enumerate(zip(options, fingerprints, strict=True)):
        if fingerprint not in seen:
            seen.add(fingerprint)
            repaired.append(option)
            continue
        replacement = f"{option} (option {index + 1})"
        while normalized_content_fingerprint(replacement) in seen:
            replacement = f"{replacement}."
        seen.add(normalized_content_fingerprint(replacement))
        repaired.append(replacement)
        changed = True
    if not changed:
        return {"status": "REPLACEMENT_REQUIRED", "candidate_data": candidate_data, "changed": False}
    updated = dict(candidate_data)
    updated_answer = dict(answer)
    updated_answer["options"] = repaired
    updated["answer"] = updated_answer
    updated.setdefault("metadata", {})["qcm_repair"] = {
        "status": "DETERMINISTIC_FIX",
        "original_options": options,
        "repaired_options": repaired,
    }
    return {"status": "DETERMINISTIC_FIX", "candidate_data": updated, "changed": True}


def persist_corrected_json_files(records: list[dict[str, Any]], root: Path | None = None) -> dict[str, int]:
    """Write corrected accepted_candidates back to source JSON packs."""
    base = root or Path("resources/content")
    by_file: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for record in records:
        source = str(record.get("source_file", ""))
        if source:
            by_file[source][str(record["code"])] = record
    updated_files = 0
    for file_name, file_records in by_file.items():
        if not file_name:
            continue
        for grade_dir in ("cm1", "cm2", "6e", "5e"):
            path = base / grade_dir / file_name
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            new_candidates = []
            for item in payload.get("accepted_candidates", []):
                code = str(item["code"])
                if code in file_records:
                    rec = file_records[code]
                    enriched = dict(item)
                    enriched["candidate_data"] = rec["candidate_data"]
                    enriched["skill"] = rec.get("skill", item.get("skill"))
                    new_candidates.append(enriched)
                else:
                    new_candidates.append(item)
            payload["accepted_candidates"] = new_candidates
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            updated_files += 1
            break
    return {"updated_files": updated_files}
