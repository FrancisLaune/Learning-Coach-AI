"""LCAI-0031 — DNB 2027 domain configuration (3e recentrage)."""

from domain.dnb.archives import ArchiveProvenance, ExamArchiveMeta, assert_not_official_ai, seed_archive_catalog
from domain.dnb.calendar import DnbExamCalendar, load_dnb_exam_calendar
from domain.dnb.config import (
    CONTINUOUS_ASSESSMENT_ONLY_SUBJECTS,
    DNB_ORAL,
    DNB_TERMINAL_SUBJECTS,
    PRIMARY_USER_GRADE_CODE,
    DnbProductConfig,
    load_dnb_product_config,
)
from domain.dnb.exam_builder import BrevetExamBlueprint, build_brevet_exam, build_global_mock_exam
from domain.dnb.exam_templates import BrevetExamCode, BrevetExamMode, BrevetExamTemplate, template_for
from domain.dnb.oral import OralProjectPlan, build_oral_project, generate_jury_questions
from domain.dnb.planner import BrevetStudyPlan, build_brevet_study_plan
from domain.dnb.prioritizer import (
    BrevetImportance,
    SkillPriorityInput,
    SkillPriorityResult,
    prioritize_skills,
)
from domain.dnb.readiness import BrevetReadinessScore, compute_brevet_readiness
from domain.dnb.remediation import PrerequisiteGap, RemediationPlan, build_remediation_plan
from domain.dnb.subject_capabilities import SubjectCapabilities, capabilities_for

__all__ = [
    "ArchiveProvenance",
    "BrevetExamBlueprint",
    "BrevetExamCode",
    "BrevetExamMode",
    "BrevetExamTemplate",
    "BrevetImportance",
    "BrevetReadinessScore",
    "BrevetStudyPlan",
    "CONTINUOUS_ASSESSMENT_ONLY_SUBJECTS",
    "DNB_ORAL",
    "DNB_TERMINAL_SUBJECTS",
    "DnbExamCalendar",
    "DnbProductConfig",
    "ExamArchiveMeta",
    "OralProjectPlan",
    "PRIMARY_USER_GRADE_CODE",
    "PrerequisiteGap",
    "RemediationPlan",
    "SkillPriorityInput",
    "SkillPriorityResult",
    "SubjectCapabilities",
    "assert_not_official_ai",
    "build_brevet_exam",
    "build_brevet_study_plan",
    "build_global_mock_exam",
    "build_oral_project",
    "build_remediation_plan",
    "capabilities_for",
    "compute_brevet_readiness",
    "generate_jury_questions",
    "load_dnb_exam_calendar",
    "load_dnb_product_config",
    "prioritize_skills",
    "seed_archive_catalog",
    "template_for",
]
