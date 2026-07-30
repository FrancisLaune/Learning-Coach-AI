# LCAI-0018B5 — Runtime Generated Homework Playability

**Statut :** ✅ VALIDÉ (2026-07-30)  
**Date :** 2026-07-30  
**Prérequis :** LCAI-0018B4 (`38197e5`)  
**Commit :** `4f9d84d` (develop)

---

## 1. Objectif

Fermer la boucle fonctionnelle du fallback IA devoirs 4e : un exercice généré au runtime est immédiatement intégré à la proposition courante, matérialisé en séance élève, corrigeable et historisé — sans second clic parent.

---

## 2. Flux avant B5

```text
Parent demande devoir
  → sélection catalogue
  → déficit détecté
  → OpenAI génère / valide / persiste (JSON + homework_runtime_exercises)
  → devoir créé avec IDs catalogue uniquement
  → create_homework_proposal ignore les runtime rows
  → séance élève sans exercices IA
```

---

## 3. Flux après B5

```text
Parent demande devoir
  → sélection catalogue (N exercices)
  → déficit = demandé − N
  → OpenAI génère uniquement le déficit
  → persist_playable_homework_exercise() crée entité catalogue session-playable
     (exercises, content_questions, content_solutions, editorial_approvals,
      content_production_gates production_enabled=FALSE)
  → homework_runtime_exercises lié (content_id, content_version_id, chapter_id, skill_id)
  → create_homework_proposal fusionne catalogue + runtime
  → devoir matérialisé en séance standard
  → élève répond / corrige / progression mise à jour
  → rerun idempotent : runtime existant réutilisé, pas de double génération
```

---

## 4. Architecture

| Couche | Changement |
|--------|------------|
| Domain | `GeneratedHomeworkExerciseResult` ; `HomeworkGenerationResult.generated_exercises` |
| Service | `HomeworkAiFallbackOrchestrator` : persistance playable, réutilisation runtime, idempotence |
| Persistance | `services/homework/runtime_persistence.py` (nouveau) |
| Repository | `create_homework_proposal` merge catalogue + runtime ; `load_homework_runtime_results` |
| Séance | `load_execution_proposal` branche homework sans `production_learning_catalog` |
| Exécution | `current_question` : skill via `exercise_questions` + `question_skills` (legacy) |
| UI | Spinner création + feedback catalogue/IA |
| Migrations | `020` colonnes runtime ; `021` relaxation FK DuckDB sur `homework_id` |

### Contrat exercice runtime

- Même schéma qu'un exercice catalogue approuvé pour la séance.
- `content_production_gates.production_enabled = FALSE`, reason `LCAI-0018B-homework-runtime-only` → exclu de la sélection devoirs catalogue, jouable en homework.
- Types supportés : `EXACT_TEXT`, `NUMERIC`, `SINGLE_CHOICE`, `BOOLEAN`.

### Déduplication

- `homework_assignments.stable_key` (idempotence devoir).
- `homework_runtime_exercises` UNIQUE `(homework_id, position)` et `(homework_id, stable_key)`.
- Empreintes contenu + known fingerprints dans `_generate_validated`.
- Rerun : `load_homework_runtime_results` évite regénération si déficit déjà comblé.

### Transactions

- `persist_playable_homework_exercise` : BEGIN/COMMIT/ROLLBACK atomique.
- Échec validation : rien persisté.
- Échec après persistance exercice : exercice conservé, pas d'item devoir orphelin supplémentaire.

---

## 5. Fichiers

### Créés

- `services/homework/runtime_persistence.py`
- `migrations/v2/020_homework_runtime_playability.sql`
- `migrations/v2/021_homework_runtime_duckdb_fk_relax.sql`
- `tests/test_homework_ai_runtime_playability_0018b5.py`
- `docs/phase3/LCAI-0018B_B5_IMPLEMENTATION_REPORT.md`

### Modifiés

- `services/homework/ai_fallback.py`
- `domain/unified_experience/models.py`
- `infrastructure/repositories/unified_experience.py`
- `infrastructure/repositories/recommendation.py`
- `infrastructure/repositories/unified_session_execution.py`
- `ui/unified_app.py`
- `tests/test_homework_ai_fallback_4e.py`
- `docs/phase3/LCAI-0018B_IMPLEMENTATION_REPORT.md`

---

## 6. Tests

### Ciblés (PASS)

```text
python -m pytest tests/test_homework_ai_fallback_4e.py -q          → 6 passed
python -m pytest tests/test_homework_ai_runtime_playability_0018b5.py -q → 8 passed
python -m pytest tests/test_lcai_0018_4e_content_homework.py -q  → 13 passed
```

Scénarios B5 couverts : déficit seul, proposition mixte, séance jouable, correction, idempotence, traçabilité, fallback OFF, rejet non-jouable.

### Suite complète

```text
python -m pytest -q → 378 passed, 25 failed, 72 errors
```

Les échecs/erreurs concernent des tests contenu/migration hors périmètre B5 (verrous DuckDB, campagnes D4, etc.). Aucune régression introduite sur les suites homework B4/B5/4e.

---

## 7. Qualité statique

| Outil | Résultat B5 |
|-------|-------------|
| Ruff (homework + tests B5) | Warnings préexistants `factory.py`, `unified_app.py` ; corrections mineures `runtime_persistence.py` |
| Mypy `services/homework` | 6 erreurs préexistantes dans `ai_fallback.py` (Protocol/Optional factory) — aucune nouvelle dans `runtime_persistence.py` |
| compileall | OK |
| `import app` | OK |

---

## 8. Validation manuelle Streamlit

**Non exécutée dans cet environnement automatisé** — scénario recommandé :

1. Parent 4e, fallback activé, devoir 8 exercices (catalogue insuffisant).
2. Vérifier message complément IA + création immédiate.
3. Élève : ouvrir devoir, répondre catalogue + IA, terminer séance.
4. Parent : vérifier résultats et progression.

---

## 9. Limites résiduelles

- Validation manuelle Parent→Élève à confirmer par Francis.
- Mypy strict sur `ai_fallback.py` non corrigé (hors scope B5).
- Exercices runtime exclus du catalogue production (volontaire).
- Migration 021 supprime FK `homework_id` (contrainte DuckDB UPDATE parent).

---

## 10. Verdict

**READY FOR REVIEW**

- Commit : NOT PERFORMED  
- Push : NOT PERFORMED
