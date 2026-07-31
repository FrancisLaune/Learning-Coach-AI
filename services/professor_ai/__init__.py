"""Professor AI orchestration package (LCAI-0022A / 0022B / 0022C / 0022D)."""

from services.professor_ai.banner import (
    BannerPresenceState,
    ProfessorAIBannerView,
    build_banner_view,
    mode_label,
    parse_operating_mode,
    presence_label,
)
from services.professor_ai.decision_log import ProfessorAIDecisionLogService, new_correlation_id
from services.professor_ai.guided_cycle import (
    GuidedCycleSnapshot,
    GuidedCycleStep,
    diagnostic_required,
    progress_caption,
    resolve_guided_cycle,
    step_label,
)
from services.professor_ai.invariants import (
    ProfessorAIInvariantError,
    assert_no_score_fields_in_payload,
    forbid_direct_score_mutation,
)
from services.professor_ai.models import (
    DecisionLogRecord,
    DecisionTraceEntry,
    HomeworkCompositionResult,
    ProfessorOperatingMode,
    SessionClosureResult,
    SessionOpenResult,
    SessionPlan,
)
from services.professor_ai.orchestrator import ProfessorAIOrchestrator

__all__ = [
    "BannerPresenceState",
    "DecisionLogRecord",
    "DecisionTraceEntry",
    "GuidedCycleSnapshot",
    "GuidedCycleStep",
    "HomeworkCompositionResult",
    "ProfessorAIBannerView",
    "ProfessorAIDecisionLogService",
    "ProfessorAIInvariantError",
    "ProfessorAIOrchestrator",
    "ProfessorOperatingMode",
    "SessionClosureResult",
    "SessionOpenResult",
    "SessionPlan",
    "assert_no_score_fields_in_payload",
    "build_banner_view",
    "diagnostic_required",
    "forbid_direct_score_mutation",
    "mode_label",
    "new_correlation_id",
    "parse_operating_mode",
    "presence_label",
    "progress_caption",
    "resolve_guided_cycle",
    "step_label",
]
