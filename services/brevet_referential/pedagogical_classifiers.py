"""LCAI-0036 — deterministic pedagogical classifiers for official archive questions."""

from __future__ import annotations

import re
from typing import Any

SUBJECT_GROUP_BY_CODE = {
    "MATHEMATICS": "MATHEMATICS",
    "FRENCH": "FRENCH",
    "HISTORY": "HISTORY_GEOGRAPHY_EMC",
    "GEOGRAPHY": "HISTORY_GEOGRAPHY_EMC",
    "EMC": "HISTORY_GEOGRAPHY_EMC",
    "PHYSICS_CHEMISTRY": "SCIENCES",
    "SVT": "SCIENCES",
    "TECHNOLOGY": "SCIENCES",
}


def classify_subject_group(subject_code: str, statement: str = "", exam_code: str | None = None) -> str:
    code = (exam_code or "").upper()
    if "MAT" in code:
        return "MATHEMATICS"
    if "HGEMC" in code or re.search(r"HG(?!E)", code):
        return "HISTORY_GEOGRAPHY_EMC"
    if re.search(r"FR(?:QGC|QG|D|R)?", code):
        return "FRENCH"
    if "SC" in code:
        return "SCIENCES"
    return SUBJECT_GROUP_BY_CODE.get(subject_code.upper(), subject_code.upper())


def classify_discipline(subject_group: str, statement: str, exam_code: str | None = None) -> str:
    text = (statement or "").casefold()
    code = (exam_code or "").upper()
    if subject_group == "HISTORY_GEOGRAPHY_EMC":
        if "enseignement moral" in text or "citoyen" in text or "emc" in text:
            return "EMC"
        if "géographie" in text or "geographie" in text or "carte" in text:
            return "GEOGRAPHIE"
        if "histoire" in text or "chronolog" in text:
            return "HISTOIRE"
        return "HISTORY_GEOGRAPHY_EMC"
    if subject_group == "SCIENCES":
        if "technologie" in text or "chaine d" in text or "chaîne d" in text:
            return "TECHNOLOGIE"
        if "svt" in text or "vivant" in text or "cellule" in text or "séisme" in text or "volcan" in text:
            return "SVT"
        if "physique" in text or "chimie" in text or "newton" in text or "électrique" in text:
            return "PHYSIQUE_CHIMIE"
        if "SC" in code:
            return "SCIENCES_COMBINED"
        return "SCIENCES_COMBINED"
    if subject_group == "FRENCH":
        if "FRD" in code or "dictée" in text or "dictee" in text:
            return "DICTEE"
        if "FRR" in code or "rédaction" in text or "redaction" in text:
            return "REDACTION"
        if "FRQG" in code or "grammaire" in text:
            return "LANGUE"
        return "FRANCAIS"
    return subject_group


def classify_content_type(subject_group: str, statement: str, exam_code: str | None = None) -> str:
    text = (statement or "").casefold()
    code = (exam_code or "").upper()
    if subject_group == "FRENCH":
        if "FRD" in code or "dictée" in text or "dictee" in text:
            return "DICTATION"
        if "FRR" in code or "rédaction" in text or "redaction" in text:
            return "WRITING_PROMPT"
        if "réécr" in text or "reecr" in text:
            return "REWRITING"
        if "grammaire" in text or "conjug" in text or "accord" in text:
            return "GRAMMAR"
        if "interprétation" in text or "interpretation" in text:
            return "INTERPRETATION"
        if "compréhension" in text or "comprehension" in text or "document" in text:
            return "COMPREHENSION"
        return "LANGUAGE"
    if subject_group == "MATHEMATICS":
        if "automatisme" in text:
            return "AUTOMATISM"
        if "algorith" in text or "scratch" in text or "programme" in text:
            return "ALGORITHM"
        if "probabilit" in text:
            return "PROBABILITY"
        if "statisti" in text or "graphique" in text or "tableau" in text:
            return "DATA_ANALYSIS"
        if "fonction" in text:
            return "FUNCTION"
        if any(k in text for k in ("triangle", "cercle", "pythagore", "thalès", "thales", "aire", "volume")):
            return "GEOMETRY"
        if "qcm" in text or "choix multiple" in text:
            return "AUTOMATISM"
        if "justifi" in text:
            return "JUSTIFICATION"
        if "calcule" in text or "calculer" in text:
            return "CALCULATION"
        if "problème" in text or "probleme" in text:
            return "PROBLEM"
        return "REASONING"
    if subject_group == "HISTORY_GEOGRAPHY_EMC":
        if "développement construit" in text or "developpement construit" in text:
            return "DEVELOPPEMENT_CONSTRUIT"
        if "carte" in text:
            return "MAP"
        if "chronolog" in text or "repère" in text or "repere" in text:
            return "CHRONOLOGY"
        if "emc" in text or "citoyen" in text:
            return "EMC_DOCUMENT_ANALYSIS"
        if "document" in text:
            return "DOCUMENT_ANALYSIS"
        return "KNOWLEDGE"
    if "protocole" in text or "expérience" in text or "experience" in text:
        return "EXPERIMENT"
    if "graphique" in text:
        return "GRAPH_INTERPRETATION"
    if "schéma" in text or "schema" in text:
        return "DIAGRAM"
    if "calcule" in text or "calculer" in text:
        return "CALCULATION"
    if "document" in text:
        return "DOCUMENT_ANALYSIS"
    return "SCIENTIFIC_REASONING"


def detect_automatism_flags(subject_group: str, content_type: str, statement: str) -> tuple[bool, str]:
    text = (statement or "").casefold()
    historical = subject_group == "MATHEMATICS" and (
        content_type in {"AUTOMATISM", "CALCULATION"} or "qcm" in text or "choix multiple" in text
    )
    if not historical:
        return False, "FALSE"
    if content_type in {"AUTOMATISM", "CALCULATION"} and len(text) < 1200:
        return True, "TRUE"
    return True, "REVIEW"


def statement_mentions_missing_support(statement: str) -> bool:
    text = (statement or "").casefold()
    markers = (
        "annexe",
        "voir la figure",
        "ci-contre",
        "ci dessous",
        "ci-dessous",
        "document 1",
        "document 2",
        "sur le graphique",
        "carte ci",
        "à rendre avec la copie",
        "a rendre avec la copie",
    )
    return any(m in text for m in markers)


def assess_segmentation(statement: str, question_number: str | None = None) -> tuple[bool, float, list[str]]:
    warnings: list[str] = []
    text = (statement or "").strip()
    if text in {"Question A", "Question B", "Question C"}:
        warnings.append("PLACEHOLDER_STATEMENT")
        return False, 0.05, warnings
    if len(text) < 40:
        warnings.append("TRUNCATED_OR_PLACEHOLDER")
        return False, 0.15, warnings
    confidence = 0.55
    if len(text) >= 120:
        confidence += 0.15
    if re.search(r"(?i)\b(exercice|question|document|calcule|explique|indique)\b", text):
        confidence += 0.15
    if question_number and str(question_number).strip():
        confidence += 0.05
    if len(re.findall(r"(?im)^\s*(?:question\s+)?\d+\s*[.)]", text)) >= 4 and len(text) > 2500:
        warnings.append("POSSIBLE_MERGED_QUESTIONS")
        confidence -= 0.15
    if statement_mentions_missing_support(text):
        warnings.append("SHARED_CONTEXT_OR_ASSET_REFERENCED")
        confidence -= 0.05
    confidence = max(0.05, min(0.98, confidence))
    ok = confidence >= 0.55 and "PLACEHOLDER_STATEMENT" not in warnings and "TRUNCATED_OR_PLACEHOLDER" not in warnings
    return ok, confidence, warnings


def mapping_confidence_from_links(
    *,
    skill_codes: list[str],
    statement: str,
    subject_group: str,
) -> tuple[float, str, str]:
    if not skill_codes:
        return 0.25, "NONE", "REVIEW"
    text = (statement or "").casefold()
    primary = skill_codes[0]
    tokens = [t for t in re.split(r"[_\s]+", primary.casefold()) if len(t) >= 4]
    hits = sum(1 for t in tokens if t in text)
    score = 0.55 + 0.12 * hits
    if subject_group == "MATHEMATICS" and any(
        k in primary.upper() for k in ("FRACTION", "EQUATION", "FONCTION", "PYTHAGORE")
    ):
        score += 0.05
    score = max(0.3, min(0.95, score))
    status = "AUTO_CHECKED" if score >= 0.90 else ("REVIEW" if score >= 0.70 else "WEAK")
    return score, "RULE_KEYWORD", status


def assess_compatibility_2027(
    *,
    year: int | None,
    subject_group: str,
    segmentation_ok: bool,
    mapping_conf: float,
    assets_complete: bool,
    warnings: list[str],
) -> tuple[str, str, float, str]:
    """Return compatible, reason, confidence, method — conservative by design."""
    if not segmentation_ok or "PLACEHOLDER_STATEMENT" in warnings or "TRUNCATED_OR_PLACEHOLDER" in warnings:
        return "FALSE", "INCOMPLETE_CONTEXT", 0.9, "RULE"
    if not assets_complete:
        return "REVIEW", "ASSET_MISSING", 0.75, "RULE"
    if mapping_conf < 0.70:
        return "REVIEW", "MAPPING_UNCERTAIN", 0.7, "RULE"
    if year is not None and year < 2018:
        return "FALSE", "OBSOLETE_FORMAT", 0.8, "RULE"
    # Never auto-TRUE: certified 2027 pool requires human confirmation.
    if year is not None and year >= 2024 and mapping_conf >= 0.85 and subject_group in {
        "MATHEMATICS",
        "FRENCH",
        "HISTORY_GEOGRAPHY_EMC",
        "SCIENCES",
    }:
        return "REVIEW", "IN_PROGRAM_2027", 0.82, "RULE_CANDIDATE"
    if year is not None and year >= 2018 and mapping_conf >= 0.70:
        return "REVIEW", "RELEVANT_SKILL_FORMAT_CHANGED", 0.7, "RULE"
    return "REVIEW", "REQUIRES_REVIEW", 0.6, "RULE"


def reliability_score(
    *,
    source_integrity: float,
    segmentation_confidence: float,
    asset_completeness: float,
    mapping_confidence: float,
    compatibility_confidence: float,
    correction_quality: float,
    validation_status: str,
) -> tuple[float, str]:
    weights = (0.2, 0.2, 0.15, 0.15, 0.15, 0.1, 0.05)
    status_score = {
        "VALIDATED": 1.0,
        "AUTO_CHECKED": 0.85,
        "REVIEW": 0.55,
        "PENDING": 0.4,
        "REJECTED": 0.1,
    }.get(validation_status, 0.5)
    parts = (
        source_integrity,
        segmentation_confidence,
        asset_completeness,
        mapping_confidence,
        compatibility_confidence,
        correction_quality,
        status_score,
    )
    score = sum(w * p for w, p in zip(weights, parts, strict=True))
    score = max(0.0, min(1.0, score))
    if score >= 0.90:
        klass = "A"
    elif score >= 0.80:
        klass = "B"
    elif score >= 0.65:
        klass = "C"
    else:
        klass = "D"
    return score, klass


def review_priority_score(row: dict[str, Any]) -> float:
    priority = 0.0
    subject = row.get("subject_group") or ""
    if subject in {"SCIENCES", "HISTORY_GEOGRAPHY_EMC"}:
        priority += 25
    importance = str(row.get("skill_importance") or "MEDIUM")
    if importance == "CRITICAL":
        priority += 30
    elif importance == "HIGH":
        priority += 20
    mapping = float(row.get("mapping_confidence") or 0)
    if mapping < 0.70:
        priority += 25
    elif mapping < 0.90:
        priority += 10
    if not row.get("assets_complete", True):
        priority += 20
    if row.get("correction_source") in {None, "NONE"}:
        priority += 10
    if row.get("pedagogical_validation_status") == "REJECTED":
        priority += 5
    reliability = float(row.get("pedagogical_reliability_score") or 0)
    priority += max(0.0, (0.8 - reliability) * 40)
    return round(priority, 2)


def decide_validation_status(
    *,
    segmentation_ok: bool,
    mapping_conf: float,
    assets_complete: bool,
    warnings: list[str],
) -> str:
    if "PLACEHOLDER_STATEMENT" in warnings:
        return "REJECTED"
    if not segmentation_ok:
        return "REVIEW"
    if segmentation_ok and assets_complete and mapping_conf >= 0.90 and not warnings:
        return "AUTO_CHECKED"
    return "REVIEW"
