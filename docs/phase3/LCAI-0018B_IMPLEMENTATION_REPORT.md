# LCAI-0018B — Rapport d'implémentation

**Statut :** clôturé (Phase 3 — jalon `Phase3_Completed`)  
**Date :** 2026-07-29

---

## Lot B0 — baseline (terminé)

- Audit baseline : `scripts/lcai_0018b_phase0_baseline.py`
- Rapports : `LCAI-0018B_PHASE0_BASELINE.md`, `LCAI-0018B_GAP_ANALYSIS.md`, `LCAI-0018B_COVERAGE_MATRIX.csv`
- Contrat fallback : `LCAI-0018B_AI_FALLBACK_CONTRACT.md`
- Discovery G0 : `LCAI-0018B_G0_DISCOVERY_REPORT.md` — **PASS**

## Lot B4 — fallback IA runtime (terminé, flag OFF)

### Composants livrés

| Composant | Fichier |
|-----------|---------|
| Migration table runtime | `migrations/v2/019_homework_runtime_exercises.sql` |
| Orchestrateur déficit/IA | `services/homework/ai_fallback.py` |
| Contexte élève | `services/homework/learner_context.py` |
| Configuration env | `services/homework/config.py` |
| Candidats runtime sans catalogue | `ContentFactoryService.generate_runtime_candidates()` |
| Intégration HomeworkService | `services/unified_experience.py` |
| Feature flag (défaut false) | `homework_ai_fallback_4e` dans `services/platform_runtime.py` |
| Persistance runtime | `DuckDBUnifiedExperienceRepository.persist_homework_runtime_exercises()` |
| Tests | `tests/test_homework_ai_fallback_4e.py` (3/3 PASS) |

### Décisions Francis appliquées

- Persistance via table dédiée `homework_runtime_exercises` (pas session-only).
- Flag OFF : comportement legacy (devoir tronqué si catalogue insuffisant).
- Jamais de statut Approved automatique pour les exercices IA runtime.

### Validation fonctionnelle

| Scénario | Résultat |
|----------|----------|
| Flag OFF, création devoir Anglais 4e | ✅ PASS |
| Flag ON + stub, persistance RUNTIME_ONLY | ✅ PASS |
| Pas de `persist_draft` catalogue | ✅ PASS |

### Dette Phase 4

1. Brancher `OpenAIContentGenerator` dans l'UI (`ui/unified_app.py`) derrière le flag.
2. Étendre `create_homework_proposal` pour les exercices runtime en séance.
3. Enrichissement contenu catalogue P0 (EN, PC, ES) — publication humaine.

---

## Fichiers documentation

- `docs/phase3/LCAI-0018B_ADAPTIVE_SCENARIOS.md`
- `docs/phase3/LCAI-0018B_HOMEWORK_ACCEPTANCE_MATRIX.md`
- `docs/phase3/exports/LCAI-0018B_GAP_BY_CHAPTER.csv`
- `docs/phase3/archive/specifications/` — docx sources
- `docs/phase3/archive/extracted_b4/` — extracts Vol. 1–4

## Script utilitaire

- `scripts/reset_family_to_demo_parent.py` — reset compte démo Parent/1234 (V1 + V2)
