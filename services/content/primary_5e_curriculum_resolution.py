"""LCAI-0012E — semantic 5e curriculum resolution for unmapped preparation records."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from services.content.primary_integration import (
    PRIMARY_GRADES,
    audit_draft_quality,
    audit_prepared_resources,
    build_primary_review_queue,
    candidate_from_record,
    candidate_sources_from_records,
    import_prepared_candidates,
    load_integration_statuses,
    load_prepared_candidates,
    load_valid_curriculum_keys,
    validate_target_key,
)
from services.content.primary_full_integration import (
    AI_HANDOFF_CAMPAIGN,
    FULL_ISOLATED_DB,
    build_ai_review_handoff,
    compute_skill_slot_coverage,
)
from services.content.primary_skill_correction import (
    SkillCorrectionClass,
    SkillResolution,
    _chapter_index,
    _typo_variants,
    apply_skill_corrections,
    load_curriculum_placements,
    persist_corrected_json_files,
    repair_qcm_duplicate_choices,
    resolve_skill_code,
)
from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository
from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from services.content.quality import qcm_issues

CURRICULUM_REFERENCE_DB = Path("data/learning_coach_v2.duckdb")


class CurriculumAnalysisClass(StrEnum):
    EXACT_CURRICULUM_MATCH_FOUND = "EXACT_CURRICULUM_MATCH_FOUND"
    CURRICULUM_SKILL_EXISTS_UNDER_DIFFERENT_CODE = "CURRICULUM_SKILL_EXISTS_UNDER_DIFFERENT_CODE"
    CONTENT_CAN_BE_MAPPED_TO_EXISTING_CLOSE_SKILL = "CONTENT_CAN_BE_MAPPED_TO_EXISTING_CLOSE_SKILL"
    CONTENT_REQUIRES_NEW_CURRICULUM_SKILL = "CONTENT_REQUIRES_NEW_CURRICULUM_SKILL"
    CONTENT_INVALID_OR_OUT_OF_SCOPE = "CONTENT_INVALID_OR_OUT_OF_SCOPE"
    CURRICULUM_DECISION_REQUIRED = "CURRICULUM_DECISION_REQUIRED"


# Wrong preparation chapter → authoritative V2 chapter (same subject/grade).
CHAPTER_REMAPPINGS: dict[tuple[str, str], str] = {
    ("HISTORY", "CH-HISTORY-5E-SOCIETY"): "CH-HISTORY-5E-FEUDAL",
}

# Audited semantic aliases: (subject, chapter, prepared_skill) → authoritative skill.
# Only entries with exactly one defensible curriculum target are listed.
SEMANTIC_SKILL_ALIASES: dict[tuple[str, str, str], tuple[str, str]] = {
    # FREN5E typo variants resolve via _typo_variants; semantic tail below.
    ("FRENCH", "CH-FRENCH-5E-LANGUAGE", "SK-ENR-FRENCH-5E-LANGUAGE-COMPLEX"): (
        "SK-ENR-FRENCH-5E-LANGUAGE-CLAUSES",
        "Phrase simple/complexe → clauses.",
    ),
    ("FRENCH", "CH-FRENCH-5E-LEXICON", "SK-ENR-FRENCH-5E-LEXICON-FIELDS"): (
        "SK-ENR-FRENCH-5E-LEXICON-RELATIONS",
        "Construire un champ lexical → relations lexicales.",
    ),
    ("FRENCH", "CH-FRENCH-5E-LEXICON", "SK-ENR-FRENCH-5E-LEXICON-REUSE"): (
        "SK-ENR-FRENCH-5E-LEXICON-PRECISE",
        "Réemployer un lexique précis → lexique précis.",
    ),
    ("FRENCH", "CH-FRENCH-5E-READING", "SK-ENR-FRENCH-5E-READING-JUSTIFY"): (
        "SK-ENR-FRENCH-5E-READING-INTERPRET",
        "Justifier une lecture par le texte → interprétation.",
    ),
    ("FRENCH", "CH-FRENCH-5E-READING", "SK-ENR-FRENCH-5E-READING-PROCESS"): (
        "SK-ENR-FRENCH-5E-READING-INTERPRET",
        "Identifier un procédé d'écriture → interprétation.",
    ),
    ("FRENCH", "CH-FRENCH-5E-WRITING", "SK-ENR-FRENCH-5E-WRITING-COHERENCE"): (
        "SK-ENR-FRENCH-5E-WRITING-COHESION",
        "Cohérence/progression → cohésion.",
    ),
    ("ENGLISH", "CH-ENGLISH-5E-CULTURE", "SK-ENR-ENGLISH-5E-CULTURE-LOCATE"): (
        "SK-ENR-ENGLISH-5E-CULTURE-IDENTIFY",
        "Localiser des espaces anglophones → identifier des éléments culturels.",
    ),
    ("GEOGRAPHY", "CH-GEOGRAPHY-5E-RESOURCES", "SK-ENR-GEOGRAPHY-5E-RESOURCES-TENSION"): (
        "SK-ENR-GEOGRAPHY-5E-RESOURCES-CONFLICT",
        "Tension sur une ressource → conflit d'usage.",
    ),
    ("HISTORY", "CH-HISTORY-5E-FEUDAL", "SK-ENR-HISTORY-5E-SOCIETY-CHURCH"): (
        "SK-ENR-HISTORY-5E-FEUDAL-CHURCH",
        "Société féodale — place de l'Église → compétence féodale Église.",
    ),
    ("HISTORY", "CH-HISTORY-5E-FEUDAL", "SK-ENR-HISTORY-5E-SOCIETY-FEUDAL"): (
        "SK-ENR-HISTORY-5E-FEUDAL-SOCIETY",
        "Relations féodales → société féodale.",
    ),
    ("HISTORY", "CH-HISTORY-5E-FEUDAL", "SK-ENR-HISTORY-5E-SOCIETY-POWER"): (
        "SK-ENR-HISTORY-5E-FEUDAL-POWER",
        "Pouvoir dans l'Occident féodal → pouvoir féodal.",
    ),
    ("HISTORY", "CH-HISTORY-5E-RENAISSANCE", "SK-ENR-HISTORY-5E-RENAISSANCE-EXPLORATION"): (
        "SK-ENR-HISTORY-5E-RENAISSANCE-DISCOVERY",
        "Grandes explorations → découvertes.",
    ),
    ("MATHEMATICS", "CH-MATHEMATICS-5E-ALGEBRA", "SK-ENR-MATHEMATICS-5E-ALGEBRA-SIMPLIFY"): (
        "SK-ENR-MATHEMATICS-5E-ALGEBRA-REDUCE",
        "Simplifier une expression → réduire.",
    ),
    ("MATHEMATICS", "CH-MATHEMATICS-5E-GEOMETRY", "SK-ENR-MATHEMATICS-5E-GEOMETRY-SOLIDS"): (
        "SK-ENR-MATHEMATICS-5E-GEOMETRY-VOLUME",
        "Volume d'un solide → volume.",
    ),
    ("MATHEMATICS", "CH-MATHEMATICS-5E-NUMBERS", "SK-ENR-MATHEMATICS-5E-NUMBERS-COMPARE"): (
        "SK-ENR-MATHEMATICS-5E-NUMBERS-LOCATE",
        "Ranger des relatifs → repérer/ordonner.",
    ),
    ("MATHEMATICS", "CH-MATHEMATICS-5E-PROPORTIONALITY", "SK-ENR-MATHEMATICS-5E-PROPORTIONALITY-CHANCE"): (
        "SK-ENR-MATHEMATICS-5E-PROPORTIONALITY-PROBABILITY",
        "Probabilité d'un dé → probabilité.",
    ),
    ("MATHEMATICS", "CH-MATHEMATICS-5E-PROPORTIONALITY", "SK-ENR-MATHEMATICS-5E-PROPORTIONALITY-FREQUENCY"): (
        "SK-ENR-MATHEMATICS-5E-PROPORTIONALITY-PERCENT",
        "Fréquence en pourcentage → pourcentages.",
    ),
    ("MATHEMATICS", "CH-MATHEMATICS-5E-PROPORTIONALITY", "SK-ENR-MATHEMATICS-5E-PROPORTIONALITY-PROPORTION"): (
        "SK-ENR-MATHEMATICS-5E-PROPORTIONALITY-COEFFICIENT",
        "Proportionnalité par coefficient unitaire.",
    ),
    ("PHYSICS_CHEMISTRY", "CH-PHYSICS_CHEMISTRY-5E-MATTER", "SK-ENR-PHYSICS_CHEMISTRY-5E-MATTER-DISSOLUTION"): (
        "SK-ENR-PHYSICS_CHEMISTRY-5E-MATTER-MIXTURE",
        "Dissolution → mélange.",
    ),
    ("SPANISH", "CH-SPANISH-5E-LANGUAGE", "SK-ENR-SPANISH-5E-LANGUAGE-TENSES"): (
        "SK-ENR-SPANISH-5E-LANGUAGE-PRESENT",
        "Formes verbales de base → présent.",
    ),
    ("SVT", "CH-SVT-5E-BODY", "SK-ENR-SVT-5E-BODY-EFFORT"): (
        "SK-ENR-SVT-5E-BODY-RESPIRATION",
        "Réponses du corps à l'effort → respiration.",
    ),
    ("SVT", "CH-SVT-5E-BODY", "SK-ENR-SVT-5E-BODY-PREVENT"): (
        "SK-ENR-SVT-5E-BODY-HEALTH",
        "Comportement favorable à la santé → santé.",
    ),
    ("SVT", "CH-SVT-5E-PLANET", "SK-ENR-SVT-5E-PLANET-ACTION"): (
        "SK-ENR-SVT-5E-PLANET-HUMAN_IMPACT",
        "Action humaine sur l'environnement → impact humain.",
    ),
}

# Groups requiring human curriculum decision — no automatic skill creation.
CURRICULUM_DECISION_GROUPS: dict[tuple[str, str, str], str] = {
    ("FRENCH", "CH-FRENCH-5E-WRITING", "SK-ENR-FREN5E-WRITING-PLAN"): (
        "Planifier un texte : aucune compétence V2 « plan » ; choix entre REVISE / objectif rédactionnel."
    ),
    ("FRENCH", "CH-FRENCH-5E-WRITING", "SK-ENR-FRENCH-5E-WRITING-PLAN"): (
        "Planifier un texte : aucune compétence V2 « plan » ; choix entre REVISE / objectif rédactionnel."
    ),
    ("HISTORY", "CH-HISTORY-5E-FEUDAL", "SK-ENR-HISTORY-5E-SOCIETY-CITIES"): (
        "Essor des villes : pas de compétence « cities » ; FEUDAL-SOCIETY ou MEDIEVAL-LOCATE."
    ),
    ("HISTORY", "CH-HISTORY-5E-SOCIETY", "SK-ENR-HISTORY-5E-SOCIETY-CITIES"): (
        "Essor des villes : chapitre SOCIETY absent du V2 ; décision curriculum requise."
    ),
    ("PHYSICS_CHEMISTRY", "CH-PHYSICS_CHEMISTRY-5E-MATTER", "SK-ENR-PHYSICS_CHEMISTRY-5E-MATTER-CHANGE"): (
        "Distinguer transformations physiques/chimiques : PHYSICAL vs CHEMICAL."
    ),
    ("SVT", "CH-SVT-5E-PLANET", "SK-ENR-SVT-5E-PLANET-DATA"): (
        "Interpréter des données : pas de compétence DATA ; WEATHER_CLIMATE vs RISK."
    ),
    ("SVT", "CH-SVT-5E-PLANET", "SK-ENR-SVT-5E-PLANET-PHENOMENON"): (
        "Phénomène terrestre : WEATHER_CLIMATE vs TECTONICS selon le phénomène visé."
    ),
}

OUT_OF_SCOPE_GROUPS: dict[tuple[str, str, str], str] = {
    ("SPANISH", "CH-SPANISH-5E-CULTURE", "SK-ENR-SPANISH-5E-CULTURE-COMPARE"): (
        "Comparer une pratique culturelle : compétence COMPARE absente du chapitre culture espagnol V2."
    ),
}


@dataclass(frozen=True, slots=True)
class SemanticAnalysis:
    analysis_class: CurriculumAnalysisClass
    corrected_skill_code: str | None
    corrected_chapter_code: str | None
    reason: str
    method: str
    candidate_matches: tuple[str, ...] = ()


def _normalize_fren5e(skill_code: str, grade_code: str) -> str:
    token = grade_code.replace("FR-", "")
    for variant in _typo_variants(skill_code, grade_code, ""):
        if variant != skill_code:
            return variant
    return skill_code.replace(f"FREN{token}", f"FRENCH-{token}")


def _lookup_key(subject: str, chapter: str, skill: str, grade_code: str) -> tuple[str, str, str]:
    normalized_skill = _normalize_fren5e(skill, grade_code)
    remapped_chapter = CHAPTER_REMAPPINGS.get((subject, chapter), chapter)
    return subject, remapped_chapter, normalized_skill


def resolve_skill_code_semantic(
    *,
    program_code: str,
    grade_code: str,
    subject_code: str,
    chapter_code: str,
    primary_skill_code: str,
    prompt: str = "",
    expected: Any = None,
    placements: list | None = None,
    chapter_index: dict | None = None,
) -> SemanticAnalysis:
    """Semantic resolution layer for remaining 5e unmapped records."""
    if grade_code != "FR-5E":
        return SemanticAnalysis(
            CurriculumAnalysisClass.CONTENT_INVALID_OR_OUT_OF_SCOPE,
            None,
            None,
            "Semantic resolver scoped to FR-5E only.",
            "out_of_scope_grade",
        )

    placements = placements or load_curriculum_placements()
    chapter_index = chapter_index or _chapter_index(placements)
    normalized_skill = _normalize_fren5e(primary_skill_code, grade_code)
    remapped_chapter = CHAPTER_REMAPPINGS.get((subject_code, chapter_code), chapter_code)
    lookup = (subject_code, remapped_chapter, normalized_skill)
    raw_lookup = (subject_code, chapter_code, primary_skill_code)

    for key, reason in OUT_OF_SCOPE_GROUPS.items():
        if key == raw_lookup or key == lookup or (
            key[0] == subject_code and key[2] in {primary_skill_code, normalized_skill}
        ):
            return SemanticAnalysis(
                CurriculumAnalysisClass.CONTENT_REQUIRES_NEW_CURRICULUM_SKILL,
                None,
                remapped_chapter if remapped_chapter != chapter_code else None,
                reason,
                "missing_curriculum_skill",
            )

    for key, reason in CURRICULUM_DECISION_GROUPS.items():
        if key == raw_lookup or key == lookup or (
            key[0] == subject_code and key[2] in {primary_skill_code, normalized_skill}
        ):
            chapter_skills = chapter_index.get((program_code, grade_code, subject_code, remapped_chapter), [])
            return SemanticAnalysis(
                CurriculumAnalysisClass.CURRICULUM_DECISION_REQUIRED,
                None,
                remapped_chapter if remapped_chapter != chapter_code else None,
                reason,
                "curriculum_decision_required",
                tuple(sorted(chapter_skills)),
            )

    alias = SEMANTIC_SKILL_ALIASES.get(lookup)
    if alias is None and normalized_skill != primary_skill_code:
        alias = SEMANTIC_SKILL_ALIASES.get((subject_code, remapped_chapter, primary_skill_code))
    if alias:
        target_skill, reason = alias
        valid = (program_code, grade_code, subject_code, remapped_chapter, target_skill)
        valid_keys = {
            (p.program_code, p.grade_code, p.subject_code, p.chapter_code, p.skill_code) for p in placements
        }
        if valid in valid_keys:
            return SemanticAnalysis(
                CurriculumAnalysisClass.CONTENT_CAN_BE_MAPPED_TO_EXISTING_CLOSE_SKILL,
                target_skill,
                remapped_chapter if remapped_chapter != chapter_code else None,
                reason,
                "semantic_alias",
                (target_skill,),
            )

    # Fall back to deterministic string resolver on remapped chapter + normalized skill.
    base = resolve_skill_code(
        program_code=program_code,
        grade_code=grade_code,
        subject_code=subject_code,
        chapter_code=remapped_chapter,
        primary_skill_code=normalized_skill,
        placements=placements,
        chapter_index=chapter_index,
    )
    if base.classification is SkillCorrectionClass.DETERMINISTIC_FIX and base.corrected_skill_code:
        analysis = CurriculumAnalysisClass.CURRICULUM_SKILL_EXISTS_UNDER_DIFFERENT_CODE
        if base.method == "exact_curriculum_match":
            analysis = CurriculumAnalysisClass.EXACT_CURRICULUM_MATCH_FOUND
        return SemanticAnalysis(
            analysis,
            base.corrected_skill_code,
            remapped_chapter if remapped_chapter != chapter_code else None,
            base.reason,
            base.method,
            base.candidate_matches,
        )
    if base.classification is SkillCorrectionClass.AMBIGUOUS_MAPPING:
        return SemanticAnalysis(
            CurriculumAnalysisClass.CURRICULUM_DECISION_REQUIRED,
            None,
            remapped_chapter if remapped_chapter != chapter_code else None,
            base.reason,
            base.method,
            base.candidate_matches,
        )

    return SemanticAnalysis(
        CurriculumAnalysisClass.CONTENT_INVALID_OR_OUT_OF_SCOPE,
        None,
        None,
        base.reason,
        "no_semantic_match",
        base.candidate_matches,
    )


def analyze_unmapped_5e_records(
    records: list[dict[str, Any]] | None = None,
    *,
    database_path: Path | None = None,
) -> dict[str, Any]:
    records = records or load_prepared_candidates()[0]
    valid_keys = load_valid_curriculum_keys(database_path)
    placements = load_curriculum_placements(database_path)
    chapter_index = _chapter_index(placements)
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)

    for record in records:
        candidate = candidate_from_record(record["candidate_data"])
        target = candidate.target
        if target.grade_code != "FR-5E":
            continue
        key = (
            target.program_code,
            target.grade_code,
            target.subject_code,
            target.chapter_code,
            target.primary_skill_code,
        )
        if key in valid_keys:
            continue
        group_key = (target.subject_code, target.chapter_code, target.primary_skill_code, target.program_code)
        groups[group_key].append(record)

    group_analyses: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    recoverable_codes: list[str] = []

    for (subject, chapter, skill, program), items in sorted(groups.items()):
        sample = items[0]["candidate_data"]
        analysis = resolve_skill_code_semantic(
            program_code=program,
            grade_code="FR-5E",
            subject_code=subject,
            chapter_code=chapter,
            primary_skill_code=skill,
            prompt=str(sample.get("prompt", "")),
            expected=sample.get("answer", {}).get("expected"),
            placements=placements,
            chapter_index=chapter_index,
        )
        counts[analysis.analysis_class.value] += 1
        recoverable = analysis.corrected_skill_code is not None
        if recoverable:
            recoverable_codes.extend(item["code"] for item in items)
        group_analyses.append(
            {
                "grade": "FR-5E",
                "subject": subject,
                "chapter": chapter,
                "original_primary_skill_code": skill,
                "analysis_class": analysis.analysis_class.value,
                "corrected_primary_skill_code": analysis.corrected_skill_code,
                "corrected_chapter_code": analysis.corrected_chapter_code,
                "reason": analysis.reason,
                "method": analysis.method,
                "candidate_matches": list(analysis.candidate_matches),
                "record_count": len(items),
                "sample_code": items[0]["code"],
                "sample_prompt": str(sample.get("prompt", ""))[:160],
                "sample_expected": sample.get("answer", {}).get("expected"),
            }
        )

    return {
        "unmapped_before": sum(len(v) for v in groups.values()),
        "unique_groups": len(groups),
        "group_analyses": group_analyses,
        "counts_by_class": dict(counts),
        "recoverable_record_codes": recoverable_codes,
    }


def apply_5e_semantic_corrections(
    records: list[dict[str, Any]],
    *,
    database_path: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply deterministic 5e semantic fixes with full traceability."""
    valid_keys = load_valid_curriculum_keys(database_path)
    placements = load_curriculum_placements(database_path)
    chapter_index = _chapter_index(placements)
    corrected: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    exceptions: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()

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
            corrected.append(item)
            continue

        if candidate.target.grade_code != "FR-5E":
            counts["NON_5E_UNMAPPED"] += 1
            exceptions.append({"code": record["code"], "classification": "NON_5E_UNMAPPED"})
            corrected.append(item)
            continue

        analysis = resolve_skill_code_semantic(
            program_code=candidate.target.program_code,
            grade_code=candidate.target.grade_code,
            subject_code=candidate.target.subject_code,
            chapter_code=candidate.target.chapter_code,
            primary_skill_code=candidate.target.primary_skill_code,
            prompt=candidate.prompt,
            expected=candidate.answer.expected,
            placements=placements,
            chapter_index=chapter_index,
        )
        counts[analysis.analysis_class.value] += 1

        if analysis.corrected_skill_code:
            trace = {
                "original_primary_skill_code": candidate.target.primary_skill_code,
                "original_chapter_code": candidate.target.chapter_code,
                "corrected_primary_skill_code": analysis.corrected_skill_code,
                "corrected_chapter_code": analysis.corrected_chapter_code,
                "correction_reason": analysis.reason,
                "correction_method": analysis.method,
                "analysis_class": analysis.analysis_class.value,
                "curriculum_match": {
                    "program_code": candidate.target.program_code,
                    "grade_code": candidate.target.grade_code,
                    "subject_code": candidate.target.subject_code,
                    "chapter_code": analysis.corrected_chapter_code or candidate.target.chapter_code,
                    "primary_skill_code": analysis.corrected_skill_code,
                },
            }
            target["primary_skill_code"] = analysis.corrected_skill_code
            if analysis.corrected_chapter_code:
                target["chapter_code"] = analysis.corrected_chapter_code
            candidate_data["target"] = target
            candidate_data.setdefault("metadata", {})["skill_correction"] = trace
            item["candidate_data"] = candidate_data
            item["skill"] = analysis.corrected_skill_code
            if analysis.corrected_chapter_code:
                item["chapter"] = analysis.corrected_chapter_code
            applied.append({"code": record["code"], **trace})
        else:
            exceptions.append(
                {
                    "code": record["code"],
                    "grade": record.get("grade"),
                    "subject": record.get("subject"),
                    "chapter": candidate.target.chapter_code,
                    "original_primary_skill_code": candidate.target.primary_skill_code,
                    "classification": analysis.analysis_class.value,
                    "correction_reason": analysis.reason,
                    "correction_method": analysis.method,
                    "candidate_matches": list(analysis.candidate_matches),
                }
            )
        corrected.append(item)

    return corrected, {
        "applied": applied,
        "exceptions": exceptions,
        "counts": dict(counts),
    }


def _qcm_structurally_valid(candidate_data: dict[str, Any]) -> bool:
    answer = candidate_data.get("answer", {})
    if answer.get("kind") not in {"single_choice", "multiple_choice"}:
        return True
    issues = [i for i in qcm_issues(candidate_data, None) if i != "choices_not_persisted"]
    return not issues


def prepare_all_corrected_records(
    *,
    database_path: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """CM1–5e corrections: base typo resolver + 5e semantic layer + QCM repair."""
    records, _ = load_prepared_candidates()
    base_corrected, base_report = apply_skill_corrections(records, database_path=database_path)
    semantic_corrected, semantic_report = apply_5e_semantic_corrections(base_corrected, database_path=database_path)
    qcm_repairs: list[dict[str, Any]] = []
    output: list[dict[str, Any]] = []
    for record in semantic_corrected:
        item = dict(record)
        repair = repair_qcm_duplicate_choices(item["candidate_data"])
        if repair["changed"]:
            item["candidate_data"] = repair["candidate_data"]
        qcm_repairs.append({"code": record["code"], "status": repair["status"], "changed": repair["changed"]})
        output.append(item)
    validation = audit_prepared_resources(
        DuckDBContentFactoryRepository(database_path),
        output,
        integration_statuses=load_integration_statuses(),
    )
    return output, {
        "base_skill_corrections": base_report,
        "semantic_5e_corrections": semantic_report,
        "qcm_repairs": qcm_repairs,
        "validation": {
            "curriculum_valid": validation["curriculum_valid"],
            "curriculum_mapping_errors": len(validation["curriculum_mapping_errors"]),
            "malformed_records": len(validation["malformed_records"]),
        },
    }


def filter_importable_records_extended(
    records: list[dict[str, Any]],
    *,
    database_path: Path | None = None,
) -> list[dict[str, Any]]:
    valid_keys = load_valid_curriculum_keys(database_path)
    statuses = load_integration_statuses()
    importable: list[dict[str, Any]] = []
    for record in records:
        status = statuses.get(record["code"], {}).get("integration_status")
        if status == "BLOCKED" and not _qcm_structurally_valid(record["candidate_data"]):
            continue
        candidate = candidate_from_record(record["candidate_data"])
        if validate_target_key(candidate.target, valid_keys):
            continue
        importable.append(record)
    return importable


def run_incremental_recovery(
    db_path: Path | None = None,
    *,
    quality_results_path: Path | None = None,
) -> dict[str, Any]:
    """Import/QC only newly recovered records; merge with existing QC artifacts."""
    db_path = db_path or FULL_ISOLATED_DB
    quality_path = quality_results_path or Path("resources/content/quality/lcai_0012e_quality_results.json")

    corrected, prep = prepare_all_corrected_records(database_path=CURRICULUM_REFERENCE_DB)
    importable = filter_importable_records_extended(corrected, database_path=CURRICULUM_REFERENCE_DB)
    previously_importable = 1224  # baseline from last full run
    blocked_recovered = [
        r
        for r in importable
        if load_integration_statuses().get(r["code"], {}).get("integration_status") == "BLOCKED"
        and _qcm_structurally_valid(r["candidate_data"])
    ]

    factory = DuckDBContentFactoryRepository(db_path)
    quality_repo = DuckDBContentQualityRepository(db_path)
    import_result = import_prepared_candidates(factory, importable, include_review=True)

    existing_quality: list[dict[str, Any]] = []
    if quality_path.exists():
        existing_quality = json.loads(quality_path.read_text(encoding="utf-8"))

    existing_qc_codes = {item["code"] for item in existing_quality}
    in_db_codes = _existing_exercise_codes(db_path)
    needs_qc = [r for r in importable if r["code"] in in_db_codes and r["code"] not in existing_qc_codes]
    incremental_records = needs_qc
    incremental_codes = {r["code"] for r in incremental_records}
    recovered_import = (
        {"counters": {"imported": import_result["counters"]["imported"], "qc_refreshed": len(incremental_records)}}
        if incremental_records
        else None
    )
    retained_quality = [item for item in existing_quality if item["code"] not in incremental_codes]
    all_candidates = candidate_sources_from_records(importable)

    if incremental_records:
        incremental_qc = audit_draft_quality(quality_repo, factory, all_candidates, apply_qcm=True)
        fresh_results = [item for item in incremental_qc["results"] if item["code"] in incremental_codes]
        merged_results = retained_quality + fresh_results
        merged_decisions = Counter(item["decision"] for item in merged_results)
    else:
        merged_results = existing_quality
        merged_decisions = Counter(item["decision"] for item in merged_results)

    coverage_rows = [
        {
            "grade": row.target.grade_code,
            "subject": row.target.subject_code,
            "chapter": row.target.chapter_code,
            "skill": row.target.primary_skill_code,
            "skill_name": row.skill_label,
            "approved_practice": sum(
                c for slot, c in row.approved.items() if slot.content_type.value in {"practice", "guided_practice"}
            ),
            "approved_assessment": sum(c for slot, c in row.approved.items() if slot.content_type.value == "assessment"),
        }
        for row in factory.active_skill_coverage(grade_codes=PRIMARY_GRADES)
    ]
    slot_coverage = compute_skill_slot_coverage(merged_results, database_path=db_path)
    review_queue = build_primary_review_queue(merged_results, all_candidates, coverage_rows)
    ai_handoff = build_ai_review_handoff(merged_results, review_queue, candidates=all_candidates)

    semantic = prep["semantic_5e_corrections"]
    recovered = len(semantic["applied"])
    remaining_unmapped = len(semantic["exceptions"])

    return {
        "database": str(db_path),
        "production_db_modified": False,
        "preparation": prep,
        "importable_count": len(importable),
        "import_result": import_result["counters"],
        "recovered_import": recovered_import["counters"] if recovered_import else None,
        "quality": dict(merged_decisions),
        "slot_coverage": slot_coverage,
        "review_queue_size": review_queue["queue_size"],
        "ai_handoff_count": len(ai_handoff),
        "recovered_candidates": recovered,
        "remaining_unmapped": remaining_unmapped,
        "quality_results": merged_results,
        "review_queue": review_queue,
        "ai_handoff": ai_handoff,
        "analysis": analyze_unmapped_5e_records(corrected, database_path=CURRICULUM_REFERENCE_DB),
    }


def _existing_exercise_codes(database_path: Path) -> set[str]:
    from services.content.primary_integration import _existing_exercise_codes as existing

    return existing(database_path)


def write_resolution_artifacts(payload: dict[str, Any], root: Path | None = None) -> None:
    base = root or Path(".")
    integration = base / "resources/content/integration"
    quality = base / "resources/content/quality"
    integration.mkdir(parents=True, exist_ok=True)
    quality.mkdir(parents=True, exist_ok=True)

    (integration / "lcai_0012e_5e_curriculum_resolution_v1.json").write_text(
        json.dumps(payload["analysis"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        k: v
        for k, v in payload.items()
        if k not in {"quality_results", "review_queue", "ai_handoff", "analysis"}
    }
    (integration / "lcai_0012e_full_integration_summary_v1.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (quality / "lcai_0012e_quality_results.json").write_text(
        json.dumps(payload["quality_results"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (quality / "lcai_0012e_review_queue.json").write_text(
        json.dumps(payload["review_queue"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (quality / "lcai_0012e_slot_coverage.json").write_text(
        json.dumps(payload["slot_coverage"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (integration / "lcai_0012e_ai_review_handoff.jsonl").open("w", encoding="utf-8") as handle:
        for item in payload["ai_handoff"]:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
