# LCAI-0018 — Phase 0 : audit exhaustif toutes matières (4e)

## Runtime

- Base V2 : `C:\Users\Utilisateur\Documents\App_AILearning\Learning-Coach-AI\data\learning_coach_v2.duckdb`
- Chemin devoirs : `ui/unified_app._homework_form` → `HomeworkService` → `DuckDBUnifiedExperienceRepository.select_approved_content_detailed`
- Catalogue production : vue/table `production_learning_catalog`
- Matières UI devoirs : `curriculum_subjects_for_grade` (toutes matières curriculum, pas seulement celles avec stock)

## Synthèse par matière

| Matière | Statut devoir | Prod. | Éligibles | Chapitres prod. | Chapitres curriculum | Diagnostic |
|---------|---------------|------:|----------:|----------------:|---------------------:|------------|
| Anglais | Couverture limitée | 2 | 2 | 1 | 2 | Contenu insuffisant pour un devoir standard |
| EMC | Couverture limitée | 4 | 4 | 2 | 2 | Contenu insuffisant pour un devoir standard |
| Espagnol | Couverture limitée | 2 | 2 | 1 | 2 | Contenu insuffisant pour un devoir standard |
| Français | Couverture limitée | 25 | 8 | 6 | 6 | Contenu insuffisant pour un devoir standard |
| Géographie | Disponible | 27 | 27 | 3 | 3 | OK |
| Histoire | Disponible | 34 | 34 | 3 | 3 | OK |
| Mathématiques | Disponible | 76 | 18 | 8 | 8 | OK |
| Physique-Chimie | Couverture limitée | 2 | 2 | 1 | 2 | Contenu insuffisant pour un devoir standard |
| SVT | Disponible | 22 | 22 | 2 | 2 | OK |

## Métriques couverture

- Lignes matrice curriculum : **444**
- Combinaisons skill/type à zéro contenu publié : **250**
- Matières curriculum configurées : **9**

## Cause P0 Anglais / Physique-Chimie

Contenus publiés uniquement en **difficulté 2** alors que l'UI propose **Moyen = 3**.
Correctif : assouplissement automatique + états UI Disponible / Couverture limitée / Indisponible.

## Files de revue exportées

- `EMC` (EMC) : 24 candidat(s) → `exports/LCAI-0018_4E_REVIEW_QUEUE_EMC.csv`
- `ENGLISH` (Anglais) : 24 candidat(s) → `exports/LCAI-0018_4E_REVIEW_QUEUE_ENGLISH.csv`
- `FRENCH` (Français) : 158 candidat(s) → `exports/LCAI-0018_4E_REVIEW_QUEUE_FRENCH.csv`
- `GEOGRAPHY` (Géographie) : 38 candidat(s) → `exports/LCAI-0018_4E_REVIEW_QUEUE_GEOGRAPHY.csv`
- `HISTORY` (Histoire) : 38 candidat(s) → `exports/LCAI-0018_4E_REVIEW_QUEUE_HISTORY.csv`
- `MATHEMATICS` (Mathématiques) : 210 candidat(s) → `exports/LCAI-0018_4E_REVIEW_QUEUE_MATHEMATICS.csv`
- `PHYSICS_CHEMISTRY` (Physique-Chimie) : 29 candidat(s) → `exports/LCAI-0018_4E_REVIEW_QUEUE_PHYSICS_CHEMISTRY.csv`
- `SPANISH` (Espagnol) : 24 candidat(s) → `exports/LCAI-0018_4E_REVIEW_QUEUE_SPANISH.csv`
- `SVT` (SVT) : 26 candidat(s) → `exports/LCAI-0018_4E_REVIEW_QUEUE_SVT.csv`

## Livrables

- `docs/phase3/exports/LCAI-0018_4E_COVERAGE_MATRIX.csv`
- `docs/phase3/LCAI-0018_HOMEWORK_ACCEPTANCE_MATRIX.md`
- Files `exports/LCAI-0018_4E_REVIEW_QUEUE_<SUBJECT>.csv`
