# LCAI-0015A — Authentication Completion Report

**Date:** 2026-07-28  
**Ticket:** Parent/Child authentication audit & completion  
**Status:** Ready for commit review (not committed)

---

## Summary

The existing Streamlit authentication stack (~75%) was preserved. The remaining ~25% was completed: adaptive password hashing, parent/child password recovery, email delivery adapter, V2 guardian enforcement on student-account mutations, session invalidation after reset, and targeted tests.

No second authentication system was introduced. V1 credentials remain in `users` (legacy DB); family links continue in V2.

---

## Completed gaps (audit → done)

| Gap (audit) | Resolution |
|---|---|
| SHA-256 without salt | PBKDF2-HMAC-SHA256 (390k iterations) + legacy SHA-256 verify/rehash |
| Parent forgot password | Token flow + UI in `ui/streamlit_app.py` |
| Child recovery via parent email | Neutral request → email to parent → shared reset page |
| Email service | `services/auth/email_delivery.py` (console/file/smtp/disabled) |
| Password reset tokens | `password_reset_tokens` table in V1 `init_db` |
| Auth audit trail | `authentication_audit_events` table + `_record_auth_event` |
| V2 guardian not checked on V1 ops | `_parent_owns_learner` on create/reset/deactivate/delete |
| Child email mandatory | Email optional in `create_student_account` |
| Session survives password reset | `users.auth_epoch` + `session_user_still_valid` in routing |

---

## User flows

### Parent registration
Unchanged entry: login expander → `create_parent`. Passwords hashed with PBKDF2; duplicate email/username rejected; minimum 8 characters.

### Child creation (authenticated parent)
Parent dashboard → student account form → `create_student_account`. Duplicate username blocked; V2 guardian link enforced when learner exists in V2.

### Parent login
Email/username + password → `authenticate(..., "parent")` → Parent dashboard (`ui/unified_app.py:run_parent`).

### Child login
Child username + password → `authenticate(..., "student")` → Student dashboard (`run_student`).

### Parent password recovery
1. Login screen → « Mot de passe oublié » → parent email  
2. Neutral confirmation (no enumeration)  
3. Email with secure link (`reset_token`, `purpose=parent`)  
4. Reset form validates token (expiry, one-time use)  
5. Password updated, `auth_epoch` incremented, sessions invalidated, audit event recorded  

### Child password recovery (via parent)
1. Login screen → child recovery → parent email + child username  
2. Neutral confirmation  
3. Email sent to **parent** with link (`purpose=child`)  
4. Parent completes reset; child password updated on token completion  
5. Child receives no direct email  

---

## Schema changes (V1 legacy DB)

Added idempotently in `core/database.py:init_db`:

- `users.auth_epoch INTEGER DEFAULT 0`
- `password_reset_tokens` (hashed token, purpose, expiry, one-time use)
- `authentication_audit_events` (event type, user, learner ref, detail)

**Migration file:** none separate — backward-compatible DDL in `init_db` on existing deployments.

---

## Security decisions

| Topic | Decision |
|---|---|
| Hashing | PBKDF2-HMAC-SHA256, per-password salt, `hmac.compare_digest` |
| Legacy passwords | SHA-256 hex still verified; rehashed on successful login |
| Reset tokens | `secrets.token_urlsafe(32)` stored as SHA-256 hash |
| Token lifetime | 60 minutes, single use, marked `used_at` on completion |
| Enumeration | Neutral French message for all recovery requests |
| Cross-family access | V2 `learner_guardian_links` checked when learner exists; legacy-only learners remain permissive for test compat |
| Sessions | Streamlit `st.session_state.user`; invalidated via `auth_epoch` mismatch |
| Secrets | SMTP credentials via env only; never committed |
| Logging | No passwords or raw tokens in logs |

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `LCAI_AUTH_EMAIL_MODE` | `console` | `console`, `file`, `smtp`, `disabled` |
| `LCAI_AUTH_EMAIL_OUTPUT_DIR` | `data/auth_emails` | File mode output |
| `LCAI_AUTH_EMAIL_FROM` | `noreply@learning-coach-ai.local` | Sender address |
| `LCAI_PASSWORD_RESET_BASE_URL` | `http://localhost:8501` | Base URL for reset links |
| `LCAI_SMTP_HOST` | — | SMTP host (smtp mode) |
| `LCAI_SMTP_PORT` | `587` | SMTP port |
| `LCAI_SMTP_USERNAME` | — | SMTP username |
| `LCAI_SMTP_PASSWORD` | — | SMTP password |
| `LCAI_SMTP_USE_TLS` | `true` | STARTTLS |

Existing: `LCAI_DATABASE_PATH`, `LCAI_V2_DATABASE_PATH`, `LCAI_ENABLE_DEMO_CREDENTIALS`.

---

## Files changed

### Created
- `services/auth/__init__.py`
- `services/auth/passwords.py`
- `services/auth/password_reset.py`
- `services/auth/email_delivery.py`
- `services/auth/email_templates.py`
- `services/auth/authorization.py`
- `tests/test_authentication_0015a.py`
- `docs/phase3/LCAI-0015A_AUTHENTICATION_AUDIT.md`
- `docs/phase3/LCAI-0015A_AUTHENTICATION_COMPLETION_REPORT.md`

### Modified
- `core/database.py` — hashing, schema, recovery APIs, guardian checks, optional child email
- `core/config.py` — email/SMTP/reset URL helpers
- `infrastructure/database/repositories.py` — UserRepository adapters
- `infrastructure/database/legacy_gateway.py` — export new functions
- `ui/streamlit_app.py` — forgot password + reset UI
- `ui/unified_app.py` — `session_user_still_valid` before routing
- `tests/test_parent_account_and_school_year.py` — PBKDF2 verify assertion

### Not modified (ticket scope)
- Curriculum, publication, Brevet content, Virtual Teacher

---

## Test results

| Suite | Result |
|---|---|
| `tests/test_authentication_0015a.py` | 10 passed |
| `tests/test_parent_account_and_school_year.py` | 5 passed |
| `tests/test_session_integration.py` | passed |
| `tests/test_unified_experience.py` | passed |
| Auth-related subset (post pre-commit) | **38 passed** |
| **Full suite** (prior run) | **404 passed, 3 skipped** |

Static analysis:
- **Ruff:** PASS (auth files)
- **Mypy:** PASS (`services/auth`, `core/database.py`)
- **compileall:** PASS
- **Streamlit import:** PASS (`run_app`, `run_unified_app`)

---

## Known limitations

1. **No rate limiting** on recovery endpoints (Streamlit UI; defer to reverse proxy or future middleware).
2. **Legacy learners without V2 record** skip guardian enforcement (backward compatibility).
3. **SMTP production** requires operator configuration; default dev mode is console/file.
4. **Email verification** for parents not implemented (out of ticket scope).
5. **Streamlit session model** remains client-side; `auth_epoch` mitigates stale sessions after reset but is not a server-side session store.
6. **Child login design** unchanged: globally unique child username + password (existing design retained).

---

## Commit policy

**Commit:** NOT COMMITTED  
**Push:** NOT PERFORMED  

Suggested message after authorization:

```
feat(LCAI-0015A): complete parent and child authentication workflows
```

---

## PRE-COMMIT ARCHITECTURE CHECK (LCAI-0015A-FINAL)

### Preference system

| Question | Answer |
|---|---|
| Existing generic preference mechanism | **NO** (partial typed domain tables only) |
| Implementation location | `learner_journey_preferences`, `learner_experience_profiles`, onboarding models — see audit doc |
| Reusable for AI Teacher | **NO** (without extension); typed feature table preferred |
| Recommended decision | **OPTION 3** |
| Reason | Project uses typed per-feature tables; AI Teacher fields are known; no KV convention exists |
| Changes made | **NONE** |

### Role model

| Question | Answer |
|---|---|
| Current login roles | `parent`, `student` |
| Role declaration | `services/auth/roles.py` (`AuthRole`) |
| Roles centralized | **YES** (auth layer; other domains keep separate actor enums) |
| Unknown roles safely rejected | **PASS** |
| Role escalation protection | **PASS** (session role re-validated against DB) |
| Service-level authorization | **PASS** (`require_parent_role`, `require_student_role`, guardian checks) |
| Future human roles without auth redesign | **YES** |
| AI Teacher as service, not auth role | **YES** |

**How to add a future human role (e.g. Administrator):**
1. Add value to `AuthRole` and migration/seed if needed in `users.role`.
2. Add login entrypoint with `authenticate(..., expected_role)`.
3. Add dashboard branch in `run_unified_app` (or dedicated shell).
4. Add service guards; reuse password reset and session invalidation unchanged.
5. Do **not** create AI Teacher as a login role.

**Pre-commit changes:**
- `services/auth/roles.py` (new)
- `core/database.py` — role validation hardening
- `services/auth/authorization.py` — `AuthRole` guards + `require_known_auth_role`
- `services/auth/__init__.py` — exports
- `ui/unified_app.py` — explicit role routing
- `tests/test_authentication_0015a.py` — 3 role-security tests

**Tests executed (pre-commit):** 38 passed (auth subset); Ruff PASS; Mypy PASS; compileall PASS; startup PASS.

---

## LCAI-0017 SPECIFICATION COMPATIBILITY REVIEW

**Reference:** `docs/phase3/LCAI-0017_V1_Professeur_Virtuel_Specification.docx` (review only — not implemented)

| Verification point | Result | Notes |
|---|---|---|
| Parent/Child ownership model matches implementation | **PASS** | Spec §13: Parent configures/locks; Child uses own profile; cross-family denied. Maps to `AuthRole`, `parent_owns_learner`, V2 `learner_guardian_links`. |
| AI Teacher as application service, not authenticated user | **PASS** | Spec §13: « ne doit pas créer un second système d'utilisateurs ». Services only (`TeacherService`, `ConversationOrchestrator`, etc.). No login/password/AuthRole entry. |
| `virtual_teacher_preferences` can reference current learner identity | **PASS** | Spec §8 uses `child_id` → implement as `learner_id BIGINT REFERENCES learners(id)` in V2. Bridge from student session via `users.learner_external_ref`. No fictional AI user FK. |
| No authentication redesign required for LCAI-0017 | **PASS** | Spec §13 and §17.1 depend on LCAI-0015A identity/session; reuse existing session + service guards. |
| No blocker for proposed AI Teacher architecture | **PASS** | V1 scope (static avatar, chat, TTS, preferences) fits existing Streamlit + V2 learner model. |

### Minor spec ↔ codebase notes (non-blocking)

1. **Naming:** Spec §8 says `child_id`; project canonical key is V2 `learners.id`. Use `learner_id` in migrations for consistency with `learner_experience_profiles`, `learner_guardian_links`.
2. **Preference fields:** Spec §8 table lists core fields; ticket §18 adds `teacher_name`, `response_length`, `feature_enabled`. Typed `virtual_teacher_preferences` should include the full §18 set — documentation gap only.
3. **Service naming:** Spec uses `TeacherService` / `TeacherPreferencesService` under `services/virtual_teacher/`; recommended aliases `AITeacherService` / `AITeacherPreferencesService` are equivalent — align naming in LCAI-0017, not in auth.
4. **Guardian enforcement edge case:** Legacy learners without a V2 record skip guardian check in V1 auth (LCAI-0015A compat). Virtual Teacher requires onboarded V2 learner — LCAI-0017 should require `learner_id` resolution and reject otherwise (stricter than legacy auth paths).
5. **UI preferences:** Spec §14.3 mentions adjustable font size « via paramètres existants si disponibles » — no generic UI preference store exists (see OPTION 3). Defer to Streamlit/theme or future UI ticket; not an auth blocker.

### AI Teacher architecture confirmation

The AI Teacher must **never** receive:
- an `AuthRole` entry;
- a `users` row or password;
- an autonomous session owning learner data.

It operates **on behalf of** authenticated actors via:
- `AuthRole` + `st.session_state.user`;
- `parent_owns_learner` / `require_parent_role` / `require_student_role`;
- future `AITeacherService` / `AITeacherPreferencesService` / `AIConversationOrchestrator` / `PedagogicalGuardrails` / `TTSService`.

**Verdict:** No LCAI-0015A code changes required. **READY FOR LCAI-0015A COMMIT** from an LCAI-0017 compatibility perspective.
