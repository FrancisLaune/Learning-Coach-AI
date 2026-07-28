# LCAI-0017 — Virtual Teacher V1 Implementation Report

**Date:** 2026-07-28  
**Status:** Final technical review completed (not committed)

---

## Implementation status

Virtual Teacher V1 extends the existing Learning Coach AI architecture:

- Migration `018_virtual_teacher_v1.sql` (5 typed tables)
- Domain models independent of Streamlit and DuckDB
- Repository persistence only (`DuckDBVirtualTeacherRepository`)
- Business logic in services (`AITeacherService`, `AITeacherPreferencesService`, `AIConversationOrchestrator`, `PedagogicalGuardrails`)
- LLM via `LLMService` only; TTS via `TTSService` only
- Authorization enforced in services (student ownership, parent guardian link, `feature_enabled`, `parent_locked`)
- Canonical identity: `learner_id` → `learners(id)` — no `child_id` flow, no new `AuthRole`
- Streamlit UI delegates to services; no direct DuckDB access from UI
- **17** focused Virtual Teacher tests + full project regression suite

---

## Architecture decisions

| Decision | Rationale |
|---|---|
| AI Teacher is an application service, not an auth role | Keeps LCAI-0015A role model stable (`parent`, `student` only) |
| Typed `virtual_teacher_preferences` table | No generic KV preference storage (LCAI-0015A pre-commit option 3) |
| `feature_enabled` default `false` | Parent must explicitly activate before student usage |
| `DeterministicLLMService` default | App usable without external LLM credentials |
| `ConsoleTTSService` default | App usable without external TTS provider |
| No FK from messages/summaries/events → sessions | DuckDB blocks `UPDATE` on parent session row when child FKs exist |
| Application-level session ownership checks | `_required_session()` validates `session.learner_id` |
| Prompt sections separated in code | System template + pedagogical context block + message history + user message |
| Pedagogical context degrades safely | Optional fields (`subject`, `skill`, `exercise`, progress) omitted when unavailable — never fabricated |

---

## Database — five tables and relationships

```
learners(id)
    │
    ├── virtual_teacher_preferences (1:1, UNIQUE learner_id)
    │
    ├── virtual_teacher_sessions (1:N)
    │       ├── virtual_teacher_messages (1:N, no DB FK — app integrity)
    │       └── virtual_teacher_summaries (1:1 by session_id PK)
    │
    └── virtual_teacher_events (1:N audit, optional session_id)

subjects(id) ──optional──► virtual_teacher_sessions.subject_id
skills(id)   ──optional──► virtual_teacher_sessions.skill_id
```

| Table | Purpose | Key constraints |
|---|---|---|
| `virtual_teacher_preferences` | Typed per-learner settings | CHECK enums, `help_level` 1–3, `feature_enabled` DEFAULT FALSE, UNIQUE `learner_id` |
| `virtual_teacher_sessions` | Conversation sessions | CHECK `actor_type`, `status`; optional subject/skill refs |
| `virtual_teacher_messages` | Ordered messages | CHECK `message_role`, optional `response_type` |
| `virtual_teacher_summaries` | Post-session summary | PK = `session_id`; JSON arrays for skills/difficulties/successes |
| `virtual_teacher_events` | Audit trail | FK to `learners`; optional `session_id` (no FK) |

**Indexes:** `(learner_id, status)` on sessions; `(session_id, created_at)` on messages; `(learner_id, created_at)` on events.

**Migration conventions:** Sequential `018_*.sql`; applied once via `schema_versions`; idempotent re-run returns `[]`.

---

## Files created

- `migrations/v2/018_virtual_teacher_v1.sql`
- `domain/virtual_teacher/__init__.py`
- `domain/virtual_teacher/enums.py`
- `domain/virtual_teacher/models.py`
- `infrastructure/repositories/virtual_teacher.py`
- `services/virtual_teacher/__init__.py`
- `services/virtual_teacher/authorization.py`
- `services/virtual_teacher/ai_teacher_preferences_service.py`
- `services/virtual_teacher/ai_teacher_service.py`
- `services/virtual_teacher/ai_conversation_orchestrator.py`
- `services/virtual_teacher/pedagogical_guardrails.py`
- `services/virtual_teacher/llm_service.py`
- `services/virtual_teacher/tts_service.py`
- `ui/virtual_teacher.py`
- `prompts/virtual_teacher_system.md`
- `tests/test_virtual_teacher_0017.py`

## Files modified

- `ui/unified_app.py` — student page **Mon professeur**, parent settings in **Paramètres**
- `tests/test_duckdb_v2.py` — migration 018 counts and rollback test version
- `tests/test_session_integration.py` — expects migration level 18
- `docs/phase3/LCAI-0017_VIRTUAL_TEACHER_V1_IMPLEMENTATION_REPORT.md`

## Files modified during final review (defect fixes only)

- `services/virtual_teacher/ai_teacher_preferences_service.py` — authorized read paths for student/parent
- `services/virtual_teacher/ai_teacher_service.py` — `list_session_messages`, message length guard
- `services/virtual_teacher/pedagogical_guardrails.py` — prompt-injection patterns
- `ui/virtual_teacher.py` — service-only access, `build_llm_service()`, destructive-action confirmations
- `tests/test_virtual_teacher_0017.py` — 6 additional security tests (17 total)

---

## Environment variables

| Variable | Required | Effect |
|---|---|---|
| `OPENAI_API_KEY` | No | When set, enables `OpenAILLMService`; otherwise deterministic LLM |
| OpenAI model env (via `load_openai_model()`) | No | Overrides default `gpt-4o-mini` when API key present |

No TTS credentials required in V1 (`ConsoleTTSService`).

---

## Startup and migration instructions

```powershell
# From repository root
Set-Location C:\Users\Utilisateur\Documents\App_AILearning\Learning-Coach-AI

# Apply migrations (creates/updates data/learning_coach_v2.duckdb)
python -c "from migrations.runner import apply_migrations; apply_migrations()"

# Launch application
streamlit run app.py
```

**Clean database:** `apply_migrations` on empty file applies migrations 1–18 (121 tables, 69 indexes).  
**Existing database at level 17:** next `apply_migrations()` applies only migration 018.

---

## Test commands

```powershell
python -m pytest tests/test_virtual_teacher_0017.py -q
python -m pytest -q
python -m ruff check services/virtual_teacher ui/virtual_teacher.py tests/test_virtual_teacher_0017.py
python -m mypy services/virtual_teacher ui/virtual_teacher.py tests/test_virtual_teacher_0017.py ui/unified_app.py
python -m compileall app.py application domain infrastructure services ui migrations tests -q
python -c "import ui.unified_app; print('startup ok')"
```

---

## Tests executed (final review)

| Suite | Result |
|---|---|
| `tests/test_virtual_teacher_0017.py` | **17 passed** |
| **Full project** `python -m pytest -q` | **425 passed, 3 skipped** |
| `tests/test_duckdb_v2.py` | 7 passed |
| `tests/test_session_integration.py` | 7 passed |
| Auth + navigation smoke (`test_authentication_0015a`, `test_streamlit_navigation`, unified navigation) | 20 passed |

---

## Static analysis (final review)

| Check | Virtual Teacher scope | Full project |
|---|---|---|
| Ruff | **PASS** | 40 pre-existing errors (unrelated modules) |
| Mypy | **PASS** | 27 pre-existing errors (unrelated modules) |
| compileall | **PASS** | PASS |
| Application startup import | **PASS** | PASS |

---

## GUI (code-verified; Streamlit manual walkthrough recommended before production)

### Student — **Mon professeur**

- Navigation item present in `unified_app.py`
- Feature-disabled info state when `feature_enabled = false`
- Empty conversation bootstrap on first visit (session auto-created when enabled)
- Quick actions: Explique-moi / indice / exemple
- Chat rendering with loading via rerun
- Error mapping via `_friendly_error`
- Optional **Écouter** per assistant message when `audio_enabled`
- Student preference panel hidden when `parent_locked`

### Parent — **Paramètres**

- Linked learner selection (existing parent flow)
- Activation, lock, full teacher configuration
- Reset and history deletion require explicit confirmation checkbox
- Success/error feedback via Streamlit messages

---

## Known limitations (V1 — not defects)

1. **TTS V1** — `ConsoleTTSService` stub; no external TTS provider
2. **Avatar** — static emoji placeholder
3. **Homework deep-link** — exercise context not injected from Devoirs UI
4. **Deterministic LLM** — used when `OPENAI_API_KEY` absent
5. **Default `feature_enabled = false`** — parent activation required
6. **Pedagogical context V1** — grade label and display name wired; subject/skill/progress fields supported in model but populated only when caller provides them (safe degradation)
7. **No child-table FK to sessions** — DuckDB limitation; integrity enforced in services

---

## Known issues

- Full-project Ruff/Mypy failures pre-date LCAI-0017 and remain in unrelated scripts/UI modules.
- Streamlit GUI was verified by code inspection during review; interactive manual QA on both roles is recommended before release.

---

## Commit / push

**Commit:** NOT PERFORMED  
**Push:** NOT PERFORMED

Suggested message after authorization:

```
feat(LCAI-0017): add Virtual Teacher V1 with auth, preferences and chat
```

---

## Verdict

**VALIDATED** — full pytest suite green; Virtual Teacher scope passes static analysis; review corrections applied.
