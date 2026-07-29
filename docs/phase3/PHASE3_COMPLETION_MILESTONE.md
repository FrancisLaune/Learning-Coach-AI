# Phase 3 — Jalon de clôture (`Phase3_Completed`)

**Date :** 2026-07-29  
**Branche :** `develop`  
**Tag Git :** `Phase3_Completed`

---

## 1. Périmètre Phase 3

| Ticket | Livrable | Statut |
|--------|----------|--------|
| LCAI-0015A | Authentification parent / élève, reset mot de passe | ✅ Clôturé |
| LCAI-0015B | Gestion famille, CRUD élèves, autorisation parent | ✅ Clôturé |
| LCAI-0017 | Professeur virtuel V1 (sessions, messages, UI) | ✅ Clôturé |
| LCAI-0018 | Couverture devoirs 4e, disponibilité matière, UI | ✅ Clôturé |
| LCAI-0018B | Fallback IA runtime 4e (flag OFF par défaut) | ✅ Clôturé (fondation) |

---

## 2. Validation fonctionnelle — LCAI-0018B

### 2.1 Critères spec (Vol. 2)

| Critère | Résultat | Preuve |
|---------|----------|--------|
| Flag `homework_ai_fallback_4e` OFF → comportement legacy | ✅ PASS | `test_flag_off_preserves_legacy_homework_creation` |
| Flag ON + générateur stub → exercices runtime validés | ✅ PASS | `test_flag_on_persists_runtime_exercises_with_stub_generator` |
| Aucune persistance catalogue Draft/Approved depuis le runtime | ✅ PASS | `test_runtime_candidates_never_call_catalogue_persist` |
| Statut `RUNTIME_ONLY`, source `ai_runtime_fallback` | ✅ PASS | assertion SQL post-création |
| Table dédiée `homework_runtime_exercises` | ✅ PASS | migration `019_homework_runtime_exercises.sql` |
| Déficit = max(0, N − K), jamais génération de N entiers | ✅ PASS | `HomeworkAiFallbackOrchestrator.generate` |
| Grade 4e uniquement (`FR-4E`) | ✅ PASS | garde `_should_use_ai_fallback` + `is_four_e_grade` |
| Auto-publication Approved interdite | ✅ PASS | `generate_runtime_candidates` sans `persist_draft` |

### 2.2 LCAI-0018 (non-régression)

| Critère | Résultat |
|---------|----------|
| Devoir non vide pour chaque matière curriculum 4e | ✅ 13/13 tests |
| UI disponibilité Disponible / Couverture limitée / Indisponible | ✅ implémenté |
| Assouplissement difficulté catalogue | ✅ implémenté |

### 2.3 Hors périmètre clôture (dette documentée)

- Branchement UI production avec `OpenAIContentGenerator` réel (flag reste OFF).
- Extension `create_homework_proposal` pour jouer les exercices runtime en séance.
- Enrichissement contenu P0 EN/PC/ES (publication humaine requise).

---

## 3. Validation technique

### 3.1 Tests exécutés (2026-07-29)

```text
pytest tests/test_homework_ai_fallback_4e.py \
       tests/test_lcai_0018_4e_content_homework.py \
       tests/test_unified_experience.py \
       tests/test_platform_runtime.py \
       tests/test_content_factory.py
```

| Suite | Résultat |
|-------|----------|
| `test_homework_ai_fallback_4e.py` | **3/3 PASS** |
| `test_lcai_0018_4e_content_homework.py` | **13/13 PASS** |
| `test_unified_experience.py` | **PASS** |
| `test_platform_runtime.py` | **PASS** |
| `test_content_factory.py` | **14/15 PASS** — 1 échec local `WinError 32` (DuckDB verrouillée par un processus externe, non régression code) |
| **Total Phase 3 ciblé** | **56/57 PASS** (98,2 %) |

### 3.2 Couverture modules LCAI-0018B

| Module | Couverture |
|--------|------------|
| `services/homework/ai_fallback.py` | 85 % |
| `services/homework/config.py` | 92 % |
| `services/homework/learner_context.py` | 66 % |
| `services/unified_experience.py` (HomeworkService) | 35 % (fichier partagé, chemins non-B4 non exercés) |

Commande :

```bash
pytest tests/test_homework_ai_fallback_4e.py tests/test_lcai_0018_4e_content_homework.py \
  --cov=services.homework --cov=services.unified_experience --cov-report=term-missing
```

### 3.3 CI

- Pipeline locale : `pytest` + `ruff` (config `pyproject.toml`).
- Aucun workflow GitHub Actions présent dans le dépôt ; la validation CI repose sur l’exécution pytest stricte ci-dessus avant tag.
- Migration 019 incluse dans `migrations/v2/` — appliquée automatiquement par `apply_migrations` au démarrage / tests.

---

## 4. Livrables code Phase 3 (LCAI-0018B)

| Fichier | Rôle |
|---------|------|
| `migrations/v2/019_homework_runtime_exercises.sql` | Persistance exercices runtime |
| `services/homework/ai_fallback.py` | Orchestration déficit + validation |
| `services/homework/learner_context.py` | Contexte pédagogique élève |
| `services/homework/config.py` | Variables env fallback |
| `services/content/factory.py` | `generate_runtime_candidates()` |
| `services/unified_experience.py` | Pipeline HomeworkService + flag |
| `services/platform_runtime.py` | Feature flag `homework_ai_fallback_4e` |
| `tests/test_homework_ai_fallback_4e.py` | Tests B4 |
| `scripts/reset_family_to_demo_parent.py` | Reset démo Parent/1234 |

---

## 5. Archivage documentation

Structure :

```text
docs/phase3/
├── README.md                          ← index Phase 3
├── PHASE3_COMPLETION_MILESTONE.md     ← ce document
├── archive/
│   ├── README.md
│   ├── specifications/                ← docx sources
│   └── extracted_b4/                  ← extracts Vol. 1–4
├── exports/                           ← CSV audits
└── LCAI-*.md / *.csv                  ← rapports actifs
```

---

## 6. Critère de clôture

| Gate | Statut |
|------|--------|
| LCAI-0018B fondation livrée et testée | ✅ |
| Flag OFF = production safe | ✅ |
| Documentation à jour | ✅ |
| Archive phase3 structurée | ✅ |
| Tag `Phase3_Completed` | ✅ (avec ce commit) |

**Phase 3 est déclarée terminée.** Phase 4 pourra activer le fallback IA (`HOMEWORK_AI_FALLBACK_4E_ENABLED=true`) après recette Francis et branchement OpenAI UI.
