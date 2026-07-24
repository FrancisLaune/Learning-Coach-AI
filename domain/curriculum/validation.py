"""Deterministic curriculum, graph and editorial validation."""

from __future__ import annotations

from collections import Counter
from typing import Any

from domain.curriculum.models import (
    CatalogValidationIssue,
    CatalogValidationReport,
    ContentType,
    QualityAssessment,
)

STRUCTURED_TAGS = {
    "revision",
    "remediation",
    "transition_ready",
    "introductory",
    "prerequisite_bridge",
    "next_grade_preparation",
    "brevet",
    "bac",
    "diagnostic",
    "method",
    "challenge",
    "timed",
    "calculator",
    "no_calculator",
    "core_skill",
    "common_error",
    "mixed_skills",
}


class PrerequisiteCycleError(ValueError):
    """Raised when a prerequisite edge would make the graph cyclic."""


def assert_acyclic(relations: list[dict[str, Any]]) -> None:
    graph: dict[str, set[str]] = {}
    for relation in relations:
        source = str(relation["prerequisite"])
        target = str(relation["target"])
        if source == target:
            raise PrerequisiteCycleError(f"Self prerequisite: {source}")
        graph.setdefault(source, set()).add(target)
        graph.setdefault(target, set())
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise PrerequisiteCycleError(f"Prerequisite cycle involving {node}")
        if node in visited:
            return
        visiting.add(node)
        for following in graph.get(node, set()):
            visit(following)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


class CatalogValidator:
    """Validate the explicit, human-reviewed catalog manifest before persistence."""

    def validate(self, document: dict[str, Any]) -> CatalogValidationReport:
        issues: list[CatalogValidationIssue] = []
        programs = document.get("programs", [])
        chapters = document.get("chapters", [])
        skills = document.get("skills", [])
        subskills = document.get("subskills", [])
        relations = document.get("relations", [])
        contents = document.get("contents", [])
        for kind, items in (
            ("program", programs),
            ("chapter", chapters),
            ("skill", skills),
            ("subskill", subskills),
            ("content", contents),
        ):
            counts = Counter(str(item.get("code", "")) for item in items)
            issues.extend(
                CatalogValidationIssue("duplicate_code", f"Duplicate {kind} code", code)
                for code, count in counts.items()
                if not code or count > 1
            )
        chapter_codes = {str(item["code"]) for item in chapters}
        skill_codes = {str(item["code"]) for item in skills}
        program_codes = {str(item["code"]) for item in programs}
        for skill in skills:
            if skill.get("chapter_code") not in chapter_codes:
                issues.append(CatalogValidationIssue("unknown_chapter", "Skill chapter is unknown", skill.get("code")))
        for chapter in chapters:
            if chapter.get("program_code") not in program_codes:
                issues.append(
                    CatalogValidationIssue("unknown_program", "Chapter programme is unknown", chapter.get("code"))
                )
        for subskill in subskills:
            if subskill.get("skill_code") not in skill_codes:
                issues.append(
                    CatalogValidationIssue(
                        "unknown_subskill_parent", "Sub-skill parent is unknown", subskill.get("code")
                    )
                )
        try:
            assert_acyclic(relations)
        except PrerequisiteCycleError as exc:
            issues.append(CatalogValidationIssue("prerequisite_cycle", str(exc)))
        for relation in relations:
            if relation.get("prerequisite") not in skill_codes or relation.get("target") not in skill_codes:
                issues.append(CatalogValidationIssue("unknown_skill_relation", "Relation references an unknown skill"))
            threshold = relation.get("minimum_mastery_threshold", -1)
            if not 0 <= threshold <= 1:
                issues.append(CatalogValidationIssue("invalid_mastery_threshold", "Threshold must be between 0 and 1"))
            if relation.get("strength", 0) >= 0.8 and not str(relation.get("rationale", "")).strip():
                issues.append(
                    CatalogValidationIssue("missing_relation_rationale", "Strong relations require a rationale")
                )
        for content in contents:
            code = str(content.get("code", ""))
            if content.get("chapter_code") not in chapter_codes or content.get("skill_code") not in skill_codes:
                issues.append(CatalogValidationIssue("incomplete_curriculum_mapping", "Unknown chapter or skill", code))
            if content.get("content_type") not in {item.value for item in ContentType}:
                issues.append(CatalogValidationIssue("unknown_content_type", "Unknown content type", code))
            if not 1 <= int(content.get("difficulty", 0)) <= 5:
                issues.append(CatalogValidationIssue("invalid_difficulty", "Difficulty must be between 1 and 5", code))
            if int(content.get("duration_minutes", 0)) <= 0:
                issues.append(CatalogValidationIssue("invalid_duration", "Duration must be positive", code))
            unknown_tags = set(content.get("tags", [])) - STRUCTURED_TAGS
            if unknown_tags:
                issues.append(CatalogValidationIssue("unknown_tag", f"Unknown tags: {sorted(unknown_tags)}", code))
            question = content.get("question", {})
            if not str(question.get("statement", "")).strip():
                issues.append(CatalogValidationIssue("missing_statement", "Statement is required", code))
            evaluative = bool(question.get("evaluative", True))
            if evaluative and question.get("answer") in (None, "", [], {}):
                issues.append(CatalogValidationIssue("missing_answer", "Expected answer is required", code))
            solution = content.get("solution", {})
            if evaluative and not str(solution.get("explanation", "")).strip():
                issues.append(CatalogValidationIssue("missing_solution", "Evaluative content needs a solution", code))
            hints = content.get("hints", [])
            orders = [int(hint.get("order", 0)) for hint in hints]
            if orders != list(range(1, len(orders) + 1)):
                issues.append(CatalogValidationIssue("unordered_hints", "Hints must be contiguous", code))
            if content.get("status") == "approved":
                for field in ("reviewer", "approver", "author_source", "license_or_origin", "objective"):
                    if not str(content.get(field, "")).strip():
                        issues.append(CatalogValidationIssue("approval_metadata_missing", f"{field} is required", code))
                if content.get("reviewer") == content.get("author_source"):
                    issues.append(CatalogValidationIssue("self_approval", "Author and reviewer must differ", code))
        return CatalogValidationReport(tuple(issues))

    def quality(self, content: dict[str, Any], report: CatalogValidationReport) -> QualityAssessment:
        checks = {
            "curriculum_mapping": bool(content.get("chapter_code") and content.get("skill_code")),
            "learning_objective": bool(content.get("objective")),
            "statement": bool(content.get("question", {}).get("statement")),
            "solution": bool(content.get("solution", {}).get("explanation")),
            "metadata": bool(content.get("author_source") and content.get("license_or_origin")),
            "difficulty_rationale": bool(content.get("difficulty_rationale")),
            "duration": int(content.get("duration_minutes", 0)) > 0,
            "prerequisites": "prerequisites" in content,
            "common_errors": bool(content.get("common_errors")),
            "human_validation": bool(content.get("reviewer") and content.get("approver")),
        }
        passed = tuple(key for key, value in checks.items() if value)
        missing = tuple(key for key, value in checks.items() if not value)
        blocking = tuple(
            issue.code for issue in report.issues if issue.blocking and issue.entity_code == content.get("code")
        )
        score = max(0, len(passed) * 10 - len(blocking) * 20)
        level = (
            "excellent"
            if score >= 90
            else "publishable"
            if score >= 75
            else "developing"
            if score >= 50
            else "insufficient"
        )
        return QualityAssessment(score, level, passed, missing, blocking, ())
