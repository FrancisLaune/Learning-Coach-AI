# LCAI-0015A — Authentication Functional Audit

**Date:** 2026-07-28  
**Scope:** Parent/Child authentication, family accounts, password recovery  
**Policy:** Audit before implementation — no redesign of working flows

---

## Executive summary

Estimated existing implementation: **~75% complete**.

Authentication is **Streamlit-only**, credentials live in the **V1 legacy database** (`users` table in `core/database.py`), and family pedagogy links use **V2** (`learner_guardian_links`). Parent registration, parent/student login, student account creation by parent, and role-based routing in `ui/unified_app.py` are implemented. Major gaps: **parent password recovery**, **child recovery via parent email**, **email delivery**, **adaptive password hashing**, and **V2 guardian enforcement on V1 student-account mutations**.

---

## Audit matrix

| Feature | Status | Implementation location | Test status | Gap | Recommended action |
|---|---|---|---|---|---|
| Streamlit entrypoint | IMPLEMENTED | `app.py`, `ui/streamlit_app.py` | PARTIAL | — | Keep |
| Parent login (email/username + password) | IMPLEMENTED | `core/database.py:authenticate`, `ui/streamlit_app.py:login_screen` | PASS | — | Keep |
| Student login | IMPLEMENTED | Same | PASS | — | Keep |
| Parent self-registration | IMPLEMENTED | `core/database.py:create_parent`, login expander | PASS | — | Keep |
| Student self-registration | NOT_IMPLEMENTED | — | N/A | By design | Keep (parent-managed) |
| Child creation by parent | IMPLEMENTED | `ui/unified_app.py`, `create_student_account` | PASS | Child email mandatory | Make email optional |
| Child password change (parent) | IMPLEMENTED | `reset_student_password`, `_reset_student_password` | PASS | No guardian check | Add V2 ownership check |
| Child deactivate/delete | IMPLEMENTED | `deactivate/delete_student_account` | PASS | No guardian check | Add V2 ownership check |
| Parent dashboard routing | IMPLEMENTED | `ui/unified_app.py:run_parent` | PARTIAL | — | Keep |
| Student dashboard routing | IMPLEMENTED | `ui/unified_app.py:run_student` | PARTIAL | — | Keep |
| Role enforcement at login | IMPLEMENTED | `authenticate(..., expected_role)` | PASS | — | Keep |
| Session management | PARTIALLY_IMPLEMENTED | `ui/session.py`, `st.session_state.user` | PARTIAL | No server session | Add auth_epoch invalidation |
| V2 guardian links | IMPLEMENTED | `migrations/v2/012_*.sql`, `unified_experience.py` | PASS | Not wired to V1 account ops | Wire authorization |
| Password hashing | PARTIALLY_IMPLEMENTED | `core/database.py:pin_hash` (SHA-256, no salt) | PASS (weak) | Not adaptive | PBKDF2 + legacy compat |
| Parent forgot password | NOT_IMPLEMENTED | — | FAIL | Full flow missing | Implement token + UI |
| Child recovery via parent | PARTIALLY_IMPLEMENTED | Parent UI reset only | PARTIAL | No email flow | Implement recovery request |
| Email service | NOT_IMPLEMENTED | Flags in `platform_runtime.py` only | FAIL | No sender/templates | Console/file/SMTP adapter |
| Password reset tokens | NOT_IMPLEMENTED | — | FAIL | No schema | V1 tables in `init_db` |
| Auth audit trail | NOT_IMPLEMENTED | — | FAIL | — | `authentication_audit_events` |
| Account enumeration protection | PARTIALLY_IMPLEMENTED | Generic login errors | PARTIAL | — | Neutral recovery responses |
| REST/API auth | NOT_IMPLEMENTED | — | N/A | Out of scope | Defer |
| Legacy PIN `create_user` | DUPLICATED | `core/database.py:create_user` | PARTIAL | 4-char PIN | Mark obsolete, keep compat |
| Triple UI shells | DUPLICATED | `streamlit_app`, `unified_app`, `v2_experience` | PARTIAL | Maintenance | Keep behind flags |
| Demo credentials | IMPLEMENTED | `core/config.py` | PASS | Dev only | Keep gated by env |

---

## Classification summary

| Classification | Count |
|---|---|
| IMPLEMENTED | 14 |
| PARTIALLY_IMPLEMENTED | 7 |
| NOT_IMPLEMENTED | 6 |
| DUPLICATED | 2 |
| BROKEN | 0 |
| OBSOLETE | 1 (`create_user` PIN flow) |

---

## Database audit

### V1 (`objectif_brevet_2027.duckdb`)

| Table / concept | Status |
|---|---|
| `users` (parent/student credentials) | EXISTS |
| `password_reset_tokens` | **MISSING** → add in `init_db` |
| `authentication_audit_events` | **MISSING** → add in `init_db` |
| `users.auth_epoch` | **MISSING** → add for session invalidation |

### V2 (`learning_coach_v2.duckdb`)

| Table | Status |
|---|---|
| `learners` | EXISTS |
| `learner_guardian_links` | EXISTS |
| `learner_experience_profiles` | EXISTS |

No V2 password tables — auth remains V1 by design.

---

## Security findings

1. **SHA-256 without salt** — weak; upgrade to PBKDF2-HMAC-SHA256 with per-password salt.
2. **No timing-safe compare** on legacy hashes.
3. **Any authenticated parent** can reset any student account in V1 layer (guardian link not checked).
4. **No password recovery** — operational gap.
5. **Streamlit session only** — mitigated by `auth_epoch` check after password change.

---

## Implementation plan (missing 25%)

1. `services/auth/passwords.py` — PBKDF2 + legacy SHA-256 verification  
2. `services/auth/password_reset.py` — secure tokens, expiry, one-time use  
3. `services/auth/email_delivery.py` + templates — dev console/file mode  
4. `services/auth/authorization.py` — guardian ownership + role guards  
5. Extend `core/database.py` — schema, recovery APIs, ownership checks  
6. Extend `ui/streamlit_app.py` — forgot password + reset flows  
7. `tests/test_authentication_0015a.py` — recovery, security, authorization  
8. Config helpers in `core/config.py` for email mode  

**Out of scope:** API auth, bcrypt dependency, full SMTP production setup, UI shell consolidation.

---

## PRE-COMMIT ARCHITECTURE CHECK (LCAI-0015A-FINAL)

### Preference system audit

| Concept | Location | Scope | Value types | Owner | Auth | Reusable for AI Teacher | Gaps |
|---|---|---|---|---|---|---|---|
| `learner_journey_preferences` | `migrations/v2/008_decision_engine.sql` | Per-learner journey | Typed columns + JSON arrays | Learner (V2) | V2 services | NO — learning-plan specific | Not for UI/AI teacher prefs |
| `learner_experience_profiles` | `migrations/v2/015_unified_learning_experience.sql` | Per-learner onboarding | Typed columns + JSON | Learner (V2) | Unified experience repo | PARTIAL — help/format only | No voice, tone, teacher profile |
| `StudyPreferences` / onboarding models | `domain/onboarding/models.py` | Onboarding flow | Typed dataclasses | Learner | Onboarding service | NO | Ephemeral onboarding input |
| `platform_configuration_snapshots` | `migrations/v2/014_*.sql` | Platform runtime | JSON feature flags | System | Platform runtime | NO | Operator config, not user prefs |
| Generic key/value user preferences | — | — | — | — | — | NO | Does not exist |

**Classification:** **C — NO_SUITABLE_GENERIC_PREFERENCE_SYSTEM** (typed domain tables are the established pattern).

**Decision for LCAI-0017:** **OPTION 3** — do not add preference infrastructure in LCAI-0015A; introduce a typed `virtual_teacher_preferences` table in LCAI-0017.

**Reason:** Existing preference-like tables are feature-specific and typed. AI Teacher fields are known and benefit from schema validation, referential integrity, and parent-lock semantics. No generic KV store matches project conventions.

**Changes made:** NONE (no preference tables added).

### Role model audit

| Component | Implementation | Hard-coded roles | Extensible | Risk | Action |
|---|---|---|---|---|---|
| V1 `users.role` | `core/database.py` | VARCHAR `parent`/`student` | Partial | Unknown DB role could login | Reject unknown roles at authenticate |
| `AuthRole` enum | `services/auth/roles.py` | Centralized parent/student | Yes | — | Added in pre-commit check |
| Session validation | `session_user_still_valid` | — | Yes | Session role tampering | Re-read role from DB |
| UI routing | `ui/unified_app.py` | Was implicit else→student | Yes | Unknown role fell through | Explicit parent/student/ reject |
| Service guards | `services/auth/authorization.py` | Uses `AuthRole` | Yes | — | Centralized helpers |
| Session actor roles | `application/session_application.py:ActorRole` | Includes `administrator` | Yes | Separate from login auth | Document as future human role path |
| Onboarding creator | `domain/onboarding/enums.py:CreatorRole` | Includes `administrator` | Yes | Not login role | Keep separate |
| AI Teacher | — | Not an auth role | N/A | — | Service-only in LCAI-0017 |

**Future human roles:** extend `AuthRole` + `users.role` values, add login entrypoint and dashboard branch, reuse existing password/session stack. Do not conflate with `ActorRole` session actors or AI services.

**AI Teacher:** confirmed application service (e.g. `AITeacherService`), not an authenticated user account.

**Changes made (pre-commit):**
- `services/auth/roles.py` — `AuthRole` enum + helpers
- `core/database.py` — unknown-role rejection; session role re-validation from DB
- `services/auth/authorization.py` — centralized role guards
- `ui/unified_app.py` — explicit routing for known roles only
- `tests/test_authentication_0015a.py` — role escalation / unknown role tests
