# LCAI-0018B — Phase B0 Baseline (gelée)

**Date :** 2026-07-29 12:51 UTC  
**Base runtime :** `C:\Users\Utilisateur\Documents\App_AILearning\Learning-Coach-AI\data\learning_coach_v2.duckdb`  
**Ticket source :** `LCAI-0018B_COUVERTURE_4E_CONTENU_ET_GENERATION_ADAPTATIVE_IA_SPECIFICATION_CURSOR_V2.docx`

## Chemins applicatifs confirmés

| Flux | Chemin |
|------|--------|
| Devoirs UI | `ui/unified_app._homework_form` |
| Devoirs service | `HomeworkService` → `select_approved_content_detailed` |
| Catalogue éligible | `production_learning_catalog` + gates production |
| Génération offline | `ContentFactoryService` / `scripts/run_content_expansion.py` |
| Professeur IA | `AITeacherService` (explications, pas exercices devoirs) |
| Recommandations | `PersonalizedSessionService` |

## Synthèse recalculée (ne pas recopier l'historique)

| Matière | Priorité | Publiés | Brouillons | Devoir 10 ex. | Statut |
|---------|----------|--------:|-----------:|--------------:|--------|
| Anglais | P0 | 2 | 22 | 2 | LIMITED |
| EMC | P0 | 4 | 20 | 4 | LIMITED |
| Espagnol | P0 | 2 | 22 | 2 | LIMITED |
| Français | P1 | 25 | 114 | 8 | LIMITED |
| Géographie | P1 | 27 | 6 | 10 | PRODUCTION_READY |
| Histoire | P1 | 34 | 0 | 10 | PRODUCTION_READY |
| Mathématiques | P1 | 76 | 51 | 10 | PRODUCTION_READY |
| Physique-Chimie | P0 | 2 | 27 | 2 | LIMITED |
| SVT | P1 | 22 | 0 | 10 | PRODUCTION_READY |

## Métriques baseline

- Lignes matrice curriculum : **444**
- Chapitres actifs : **30**
- Chapitres vides : **3**
- Matières passant devoir 10 questions : **4/9**

## Tests de référence (avant modification B1+)

- Commande : `pytest tests/test_lcai_0018_4e_content_homework.py tests/test_content_factory.py`
- Code sortie : **1** (ÉCHEC)

```
 ce fichier est utilisé par un autre processus.

    
    File is already open in 
    C:\Users\Utilisateur\AppData\Local\Python\pythoncore-3.14-64\python.exe (PID 22500)
C:\Users\Utilisateur\Documents\App_AILearning\Learning-Coach-AI\infrastructure\database\v2.py:51: _duckdb.IOException: IO Error: Cannot open file "C:\Users\Utilisateur\Documents\App_AILearning\Learning-Coach-AI\data\learning_coach_v2.duckdb": Le processus ne peut pas accéder au fichier car ce fichier est utilisé par un autre processus.
E   PermissionError: [WinError 32] Le processus ne peut pas accéder au fichier car ce fichier est utilisé par un autre processus
C:\Users\Utilisateur\AppData\Local\Python\pythoncore-3.14-64\Lib\shutil.py:514: PermissionError: [WinError 32] Le processus ne peut pas accéder au fichier car ce fichier est utilisé par un autre processus
=========================== short test summary info ===========================
ERROR tests/test_lcai_0018_4e_content_homework.py::test_english_4e_subject_has_active_chapters
ERROR tests/test_lcai_0018_4e_content_homework.py::test_physics_chemistry_4e_subject_has_active_chapters
ERROR tests/test_lcai_0018_4e_content_homework.py::test_parent_can_generate_english_homework_for_4e
ERROR tests/test_lcai_0018_4e_content_homework.py::test_parent_can_generate_physics_chemistry_homework_for_4e
ERROR tests/test_lcai_0018_4e_content_homework.py::test_generated_homework_is_not_empty
ERROR tests/test_lcai_0018_4e_content_homework.py::test_insufficient_stock_returns_actionable_message
ERROR tests/test_lcai_0018_4e_content_homework.py::test_engine_never_falls_back_to_another_subject
ERROR tests/test_lcai_0018_4e_content_homework.py::test_homework_can_be_generated_for_each_available_4e_subject
ERROR tests/test_lcai_0018_4e_content_homework.py::test_curriculum_subjects_include_all_configured_4e_subjects
ERROR tests/test_lcai_0018_4e_content_homework.py::test_homework_never_returns_empty_when_subject_is_available
ERROR tests/test_lcai_0018_4e_content_homework.py::test_4e_coverage_export_contains_all_configured_subjects
ERROR tests/test_lcai_0018_4e_content_homework.py::test_4e_coverage_export_includes_zero_content_chapters
ERROR tests/test_lcai_0018_4e_content_homework.py::test_only_approved_active_content_is_eligible
FAILED tests/test_content_factory.py::test_real_curriculum_coverage_and_subskill_targeting
FAILED tests/test_content_factory.py::test_duckdb_adapter_persists_candidate_as_draft_without_approval
2 failed, 13 passed, 13 errors in 1.41s
```

## Divergence ticket vs implémentation

1. **Génération dynamique à la demande** : absente du runtime devoirs (voir `LCAI-0018B_AI_FALLBACK_CONTRACT.md`).
2. **Quotas par chapitre (Table 4)** : largement non atteints ; déficits calculés dans Gap Analysis.
3. **Français** : 25 publiés mais seulement ~8 éligibles au filtre devoir (difficulté/type).

## Livrables B0 gelés

- `LCAI-0018B_COVERAGE_MATRIX.csv`
- `LCAI-0018B_GAP_ANALYSIS.md`
- `exports/LCAI-0018B_GAP_BY_CHAPTER.csv`
- `LCAI-0018B_AI_FALLBACK_CONTRACT.md`
- `LCAI-0018B_ADAPTIVE_SCENARIOS.md`
- `LCAI-0018B_HOMEWORK_ACCEPTANCE_MATRIX.md`

## Prochain lot (B1 — sans démarrer sans validation Francis)

P0 : Anglais, Espagnol, Physique-Chimie, EMC → recette 10 questions + préparation fallback IA.
