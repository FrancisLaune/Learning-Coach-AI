# LCAI-0021 — Rapport d'implémentation

## Verdict

**READY FOR REVIEW**

## Résumé

Le filtrage bloquant par difficulté a été retiré de la constitution des devoirs. Tous les exercices compatibles (matière, classe, chapitre, compétence) sont désormais chargés, classés et panachés via un service dédié. La difficulté reste une métadonnée interne utilisée pour le classement adaptatif, pas pour exclure du catalogue.

## Changements principaux

### `services/homework/exercise_selection.py` (nouveau)

- `HomeworkSelectionStrategy` : parts configurables de panachage (consolidation, niveau courant, stretch).
- `rank_catalog_rows` / `panachage_select` : classement non bloquant par proximité à la cible.
- `HomeworkExerciseSelectionService` : préparation du pool catalogue avant finalisation.

### `infrastructure/repositories/unified_experience.py`

- Suppression de `difficulty=?` dans `_approved_content_filters`.
- `count_eligible_content` compte l'ensemble du catalogue compatible.
- `select_approved_content_detailed` charge tout le catalogue, classe/panache, puis finalise.

### `ui/unified_app.py`

- Messages parent mis à jour : panachage pédagogique au lieu d'« assouplissement de difficulté ».
- Suppression de la suggestion « choisir une autre difficulté » comme filtre bloquant.

## Preuves

- Aucun `difficulty=?` restant dans le chemin devoirs (`unified_experience.py`).
- Filtre `difficulty=?` conservé uniquement dans `content.py` (recherche catalogue admin, hors devoirs).

## Tests exécutés

```text
pytest tests/test_homework_exercise_selection_0021.py \
      tests/test_lcai_0018_4e_content_homework.py \
      tests/test_curriculum_selectors.py \
      tests/test_unified_experience.py::test_global_homework_uses_only_approved_content_and_is_idempotent -q
→ 24 passed
```

## Limites résiduelles

- La génération IA de déficit (LCAI-0018B5/B7) utilise encore `target_difficulty` comme cible de génération, pas comme filtre catalogue — conforme au ticket.
- `difficulty_band` dans `learner_context.py` reste calculé mais non exploité pour rotation multi-niveaux en génération IA (amélioration future).
- Pas de migration additive : les colonnes existantes suffisent.
- Traçabilité événementielle étendue (`HomeworkCompositionStarted`, etc.) non implémentée dans ce lot (hors scope minimal).

## Fichiers modifiés / créés

| Fichier | Action |
|---------|--------|
| `services/homework/exercise_selection.py` | créé |
| `infrastructure/repositories/unified_experience.py` | modifié |
| `ui/unified_app.py` | modifié |
| `tests/test_homework_exercise_selection_0021.py` | créé |
| `docs/phase3/LCAI-0021_IMPLEMENTATION_REPORT.md` | créé |
