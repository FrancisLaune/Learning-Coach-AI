# LCAI-0030-D — Rapport d'implémentation (Lot 4)

**Ticket :** LCAI-0030-D  
**Date :** 2026-08-21  
**Statut technique :** OK (validation ciblée)

## Objectif

Couverture homework CM1→3ᵉ (catalogue + IA si stock insuffisant), anti-répétition des exercices déjà vus, et ancrage 3ᵉ sur le corpus brevet déjà chargé en V2.

## Livré

### Anti-répétition catalogue
- `services/homework/anti_repetition.py` — `exclude_recent_content_ids` (fenêtre = `LearnerContextService`, défaut 30 j / `HOMEWORK_RECENT_EXCLUSION_DAYS`).
- Filtrage branché dans `DuckDBUnifiedExperienceRepository.select_approved_content_detailed` pour `learner_id > 0`.
- Si tout le stock a déjà été vu → repli sur le pool complet (pas de devoir bloqué).
- Fingerprints AI déjà exclus côté génération ; fenêtre d’exclusion branchée depuis `HomeworkAiFallbackSettings` dans `services/homework/factory.py`.

### Ancrage brevet 3ᵉ
- `prioritize_brevet_content` : pour `FR-3E`, priorise `exam_practice` / `mini_assessment`, puis skills liés à `exam_skill_references`, sans exclure le reste.
- `content_type` remonté dans le SELECT catalogue.

### Couverture CM1→3ᵉ
- `services/homework/coverage.py` — `HomeworkCoverageService.matrix` + `classify_coverage_status` (`available` / `limited` / `generable` / `gap`).
- Grades : `FR-CM1` … `FR-3E`. « Générable » = flags AI completion + grades/subjects autorisés (déjà CM1–3ᵉ par défaut).
- Exercice + explication + corrigé : inchangé via Content Factory / `is_playable_candidate` (prérequis Lot 4 déjà en place).

## Fichiers

| Action | Fichier |
|--------|---------|
| Créé | `services/homework/anti_repetition.py` |
| Créé | `services/homework/coverage.py` |
| Créé | `tests/test_lcai_0030d_coverage_antirepeat.py` |
| Créé | `docs/phase5/LCAI-0030D_IMPLEMENTATION_REPORT.md` |
| Modifié | `infrastructure/repositories/unified_experience.py` |
| Modifié | `services/homework/factory.py` |
| Modifié | `docs/phase5/README.md` |

## Tests

```text
pytest tests/test_lcai_0030d_coverage_antirepeat.py tests/test_homework_exercise_selection_0021.py tests/test_lcai_0030c_adaptation_aids.py -q
→ 19 passed
ruff check (fichiers touchés) → OK
```

## Limites restantes (métier / UX)

- Matrice couverture non exposée dans l’UI élève (service prêt pour audit / admin).
- Pas de fusion V1 `objectif_brevet_2027` dans le sélecteur V2 (volontaire) — ancrage via catalogue V2 `exam_practice` + `exam_skill_references`.
- Remplissage massif de gaps catalogue hors scope (génération à la demande si flags AI on).

## Validation humaine attendue

1. Devoirs 3ᵉ : exercices type brevet / exam_practice apparaissent en priorité quand le stock le permet.  
2. Refaire un devoir sur le même sujet sous 30 j : pas les mêmes `content_id` catalogue si d’autres restent disponibles.  
3. Niveau sans stock mais AI on : devoir toujours possible (générable).
