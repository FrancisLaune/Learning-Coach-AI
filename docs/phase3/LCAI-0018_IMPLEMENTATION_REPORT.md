# LCAI-0018 — Rapport d'implémentation (toutes matières 4e)

## Phase 0 — terminée

- Script audit : `scripts/lcai_0018_phase0_audit.py`
- Rapport exhaustif : `docs/phase3/LCAI-0018_PHASE0_ALL_SUBJECTS_AUDIT.md`
- Matrice couverture : `docs/phase3/exports/LCAI-0018_4E_COVERAGE_MATRIX.csv` (444 lignes, colonnes étendues)
- Files revue par matière : `docs/phase3/exports/LCAI-0018_4E_REVIEW_QUEUE_<SUBJECT>.csv` (9 matières)
- Matrice acceptation devoirs : `docs/phase3/LCAI-0018_HOMEWORK_ACCEPTANCE_MATRIX.md`
- Validation pédagogique (brouillon) : `docs/phase3/LCAI-0018_PEDAGOGICAL_VALIDATION_REPORT.md`

## P0 code — terminé (non commité)

| Composant | Changement |
|-----------|------------|
| `infrastructure/repositories/unified_experience.py` | `curriculum_subjects_for_grade`, `curriculum_chapters`, `production_count_for_subject`, assouplissement difficulté |
| `services/content/homework_availability.py` | Disponibilité devoirs par matière (Disponible / Couverture limitée / Indisponible) |
| `services/unified_experience.py` | Messages d'erreur actionnables, preview avant création |
| `ui/unified_app.py` | Toutes matières curriculum visibles, badges statut, blocage si indisponible |
| `domain/unified_experience/models.py` | `SubjectHomeworkAvailability`, `HomeworkContentSelection` |

## Tests — 13/13 passent

`tests/test_lcai_0018_4e_content_homework.py` couvre :
- Génération devoirs Anglais / Physique-Chimie
- Génération pour chaque matière disponible
- Export couverture (matières configurées, chapitres à zéro)
- Contenu Approved uniquement éligible

## État devoirs par matière (runtime actuel)

| Matière | Statut | Éligibles | Devoir 10 ex. |
|---------|--------|----------:|--------------:|
| Anglais | Couverture limitée | 2 | 2 (max) |
| Physique-Chimie | Couverture limitée | 2 | 2 (max) |
| Français | Couverture limitée | 8 | 8 (max) |
| Mathématiques | Disponible | 18 | 10 |
| Histoire | Disponible | 34 | 10 |
| Géographie | Disponible | 27 | 10 |
| SVT | Disponible | 22 | 10 |
| EMC | Couverture limitée | 4 | 4 (max) |
| Espagnol | Couverture limitée | 2 | 2 (max) |

**Toutes les matières curriculum passent la recette automatique** (devoir non vide).

## Reste à faire (P0 contenu + P1)

1. **Publication contrôlée** : passer les candidats PASS Anglais / Physique-Chimie (24 + 29 en file) → objectif ≥20 contenus/chapitre prioritaire.
2. **Enrichissement P1** : porter les matières « Couverture limitée » au seuil Disponible (≥10 éligibles).
3. **Tests disciplinaires avancés** du ticket (médias, doublons, QCM déterministe, etc.) — hors scope immédiat P0 code.
4. **Recette manuelle** Francis : redémarrer Streamlit, tester création devoir par matière.

## Limitations résiduelles

- Stock production faible EN/PC/ES (2 contenus/matière).
- Publication de masse non automatisée (approbation humaine obligatoire).
- Technologie, Arts, EPS, Latin absents du curriculum 4e actif (non créés artificiellement).
