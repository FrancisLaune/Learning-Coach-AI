# LCAI-0018B4 — Rapport G0 Discovery (gate avant code)

**Date :** 2026-07-29  
**Ticket :** Intelligent AI Exercise Completion — Epic LCAI-0018  
**Branche cible :** `feature/LCAI-0018B` (non créée — en attente validation Francis)  
**Statut G0 :** **PASS** — autorisation de coder sous réserve des contraintes ci-dessous

---

## 1. Documents de référence lus

| Volume | Fichier réel dans `docs/phase3/` | Contenu |
|--------|----------------------------------|---------|
| Vol. 1 Architecture | `archive/specifications/LCAI-0018B4_Volume_3_Validation_Qualification_Tests_CURSOR (3).docx` | Architecture & conception |
| Vol. 2 Implémentation | `archive/specifications/LCAI-0018B4_Volume_3_Validation_Qualification_Tests_CURSOR (2).docx` | **Normatif** — pipeline B4 |
| Vol. 3 Tests | `archive/specifications/LCAI-0018B4_Volume_3_Validation_Qualification_Tests_CURSOR (1).docx` | Validation & stratégie tests |
| Vol. 4 Annexes | `archive/specifications/LCAI-0018B4_Volume_3_Validation_Qualification_Tests_CURSOR (4).docx` | Référentiel technique |

Les noms de fichiers sur disque sont volontairement conservés tels quels ; seules les références internes au ticket utilisent ce mapping volume → fichier réel.

Extracts texte disponibles : `docs/phase3/archive/extracted_b4/vol*.txt`

---

## 2. Cartographie des 6 responsabilités (Table Vol. 2)

| Responsabilité spec | Symbole réel | Chemin |
|---------------------|--------------|--------|
| Orchestrateur devoirs | `HomeworkService` | `services/unified_experience.py` |
| Sélection catalogue | `select_approved_content_detailed` | `infrastructure/repositories/unified_experience.py` |
| Requête devoir (DTO existant) | `HomeworkRequest` | `domain/unified_experience/models.py` |
| Génération IA offline | `ContentFactoryService.generate_drafts` | `services/content/factory.py` |
| Provider LLM | `OpenAIContentGenerator` | `infrastructure/generators/openai_content.py` |
| Validation structurelle | `CandidateValidator` + `quality.py` gates | `services/content/factory.py`, `services/content/quality.py` |
| Publication contrôlée | `ai_controlled_publication.py` | **Hors runtime B4** (interdit auto-publish) |
| Feature flags | `FeatureFlagService.default_flags()` | `services/platform_runtime.py` |
| Disponibilité matière | `HomeworkAvailabilityService` | `services/content/homework_availability.py` |
| UI devoirs | `_homework_form` | `ui/unified_app.py` |

---

## 3. Point d'entrée runtime qui tronque aujourd'hui le devoir

**Fichier :** `services/unified_experience.py` — `HomeworkService.create()`

```python
selection = self.repository.select_approved_content_detailed(request)
if not selection.content_ids:
    raise ValueError(...)
return self.repository.create_homework(request, selection.content_ids)
```

**Comportement actuel :**
- Sélectionne jusqu'à `exercise_count` IDs depuis `production_learning_catalog`
- Si stock < N → devoir créé avec **moins de N exercices** (pas d'erreur si > 0)
- Si stock = 0 → `ValueError`
- **Aucun appel** à `ContentFactoryService`

**Repository :** `infrastructure/repositories/unified_experience.py`
- `_approved_content_rows` / `_finalize_content_selection`
- Assouplissement difficulté si 0 résultat au niveau demandé

---

## 4. Chemin IA existant (offline — réutilisable)

```
ContentGenerationRequest (domain/content/factory.py)
  → ContentFactoryService.generate_drafts()
    → OpenAIContentGenerator.generate()
      → CandidateValidator.validate()
      → persist_draft() via DuckDBContentFactoryRepository
```

**Scripts batch :** `scripts/run_content_expansion.py`, `scripts/run_real_content_pilot.py`

**Gap B4 :** exposer un **adaptateur runtime** (Vol. 2 §17 ordre 3) qui :
- construit `ContentGenerationRequest` depuis le déficit mesuré ;
- appelle `generate_drafts` **sans persister en Approved** ;
- retourne candidats `RuntimeOnly` / session-scoped.

---

## 5. Décisions G0 — interdictions confirmées

| Interdit par spec | État repo |
|-------------------|-----------|
| Nouveau client OpenAI parallèle | ✅ Aucun prévu — réutiliser `OpenAIContentGenerator` |
| Nouvelle Content Factory | ✅ Réutiliser `ContentFactoryService` |
| Appel LLM depuis UI | ✅ UI → `HomeworkService` uniquement |
| Auto-publication Approved | ✅ Draft / runtime only |
| Migration DuckDB | ✅ **Décision Francis** — table `homework_runtime_exercises` (migration 019) |

---

## 6. Feature flag (Vol. 2 §12)

| Clé code | Env | Défaut |
|----------|-----|--------|
| `homework_ai_fallback_4e` | `HOMEWORK_AI_FALLBACK_4E_ENABLED` | `false` |

**Implémentation :** ajouter `FeatureFlagDefinition` dans `default_flags()` (`services/platform_runtime.py`), dépendance `v2.enabled`.

Autres configs :
- `HOMEWORK_AI_FALLBACK_MAX_RETRY=1`
- `HOMEWORK_AI_FALLBACK_TIMEOUT_SECONDS=30`
- `HOMEWORK_RECENT_EXCLUSION_DAYS=30`
- `HOMEWORK_AI_MAX_GENERATED_PER_REQUEST=10`
- `HOMEWORK_AI_ALLOW_DEGRADED_RESULT=true`

---

## 7. Plan de fichiers (Vol. 2 §17 — avant modification)

| Ordre | Fichier | Action |
|------:|---------|--------|
| 1 | `domain/unified_experience/models.py` | Étendre DTOs : `HomeworkGenerationResult`, contexte déficit (non-breaking) |
| 2 | `services/homework/ai_fallback.py` | **Nouveau** — orchestration déficit + appel factory + validation (pas de dossier parallèle B4) |
| 3 | `services/homework/learner_context.py` | **Nouveau** — `LearnerPedagogicalContext` depuis mastery/historique |
| 4 | `services/unified_experience.py` | Brancher pipeline 15 étapes derrière feature flag |
| 5 | `services/content/factory.py` | Méthode runtime `generate_runtime_candidates()` si absente |
| 6 | `services/platform_runtime.py` | Feature flag + config |
| 7 | `core/config.py` ou module config existant | Variables env fallback |
| 8 | `infrastructure/repositories/unified_experience.py` | Exclusion récente / fingerprints si absent |
| 9 | `tests/test_homework_ai_fallback_4e.py` | **Nouveau** — Table 8 Vol. 2 |
| 10 | `tests/test_lcai_0018_4e_content_homework.py` | Non-régression flag OFF |
| 11 | `docs/phase3/LCAI-0018B_IMPLEMENTATION_REPORT.md` | Mise à jour continue |

**Hors scope :** refonte UI, auth, curriculum, remplacement modèle LLM.

---

## 8. Pipeline cible (Vol. 2 §5.1 — résumé)

1. Valider requête + `correlation_id`
2. Construire `LearnerPedagogicalContext`
3. Rechercher catalogue Approved (4e)
4. Filtrer compatibilité + exclure récents/doublons
5. Sélectionner jusqu'à N (sans IA)
6. `deficit = max(0, N - len(selected))`
7. Si `deficit > 0` et flag ON → `ContentFactoryService` pour **exactement deficit**
8. Valider V1–V7 sur candidats IA
9. Fusionner, plafonner à N
10. Persister via chemin existant
11. Retourner résultat enrichi (`degraded_mode` si partiel)
12. Logs structurés (`correlation_id`)

---

## 9. Tests baseline (avant modification)

Exécuter avec **Streamlit arrêté** (DuckDB non verrouillée) :

```bash
pytest tests/test_lcai_0018_4e_content_homework.py tests/test_content_factory.py -q
```

Dernière exécution B0 : échec lock fichier (13 errors + 2 failed) — **à rejouer** avant merge B4.

---

## 10. Ambiguïtés — tranchées

1. **Flag OFF :** conserver devoir tronqué (comportement actuel).
2. **Persistance exercices runtime :** table `homework_runtime_exercises` (migration 019).
3. **Grade code :** spec dit `4e` — repo utilise `FR-4E` (mapping confirmé en B0).
4. **`HOMEWORK_AI_MAX_GENERATED_PER_REQUEST` vs `requested_count` :** min des deux via `HomeworkAiFallbackSettings.generation_cap()`.

---

## 11. Critère G0

| Check | Statut |
|-------|--------|
| 6 responsabilités mappées | ✅ |
| Point de troncature identifié | ✅ |
| Chemin IA existant démontré | ✅ |
| Pas de nouveau client OpenAI prévu | ✅ |
| Plan fichiers rédigé | ✅ |
| **Autorisation de coder** | ✅ (sous contraintes ticket) |

---

## 12. Décisions Francis (2026-07-29)

| Sujet | Décision |
|-------|----------|
| Nettoyage données | Conserver uniquement Parent/1234 ; supprimer Francis, Michael, Clémence, tous les devoirs |
| Persistance runtime IA | **Table dédiée** `homework_runtime_exercises` (migration `019_homework_runtime_exercises.sql`) |
| Noms volumes docx | Conserver les noms de fichiers réels ; corriger les références dans le ticket |
| Flag OFF | Comportement historique conservé (devoir tronqué si stock catalogue insuffisant) |

**Prochaine étape :** brancher le fallback dans l'UI et étendre `create_homework_proposal` pour les exercices runtime.

**Aucun commit / push** sans validation explicite Francis.
