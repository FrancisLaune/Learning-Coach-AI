# LCAI-0018 — Phase 0 : audit contenus et moteur de devoirs (4e)

## Bases et runtime

- Base V2 runtime : `C:\Users\Utilisateur\Documents\App_AILearning\Learning-Coach-AI\data\learning_coach_v2.duckdb`
- Chemin devoirs : `ui/unified_app._homework_form` → `UnifiedExperienceService.create_homework` → `DuckDBUnifiedExperienceRepository.select_approved_content`
- Filtre principal : table `production_learning_catalog` (contenus **publiés** uniquement)
- Matières visibles UI : celles présentes dans `production_learning_catalog` pour le niveau élève (`subjects_for_grade`)

## Synthèse production FR-4E par matière

| Matière | Prod. total | Practice | Assessment | Autres | Chapitres prod. | Chapitres curriculum |
|---------|------------:|---------:|-----------:|-------:|----------------:|---------------------:|
| Anglais | 2 | 0 | 0 | 2 | 1 | 2 |
| Physique-Chimie | 2 | 0 | 0 | 2 | 1 | 2 |
| Français | 25 | 0 | 0 | 25 | 6 | 6 |
| Mathématiques | 76 | 0 | 0 | 76 | 8 | 8 |
| EMC | 4 | 0 | 0 | 4 | 2 | 2 |
| Géographie | 27 | 0 | 0 | 27 | 3 | 3 |
| Histoire | 34 | 0 | 0 | 34 | 3 | 3 |
| Espagnol | 2 | 0 | 0 | 2 | 1 | 2 |
| SVT | 22 | 0 | 0 | 22 | 2 | 2 |

## Diagnostic Anglais / Physique-Chimie

- **Anglais FR-4E** : 2 contenu(s) en production ; 24 candidats dans la file qualité.
- **Physique-Chimie FR-4E** : 2 contenu(s) en production ; 29 candidats dans la file qualité.

### Cause exacte du blocage devoirs (P0)

**Filtre difficulté trop strict** : Anglais et Physique-Chimie FR-4E n'ont que des contenus publiés en **difficulté 2** (`exercise`, `exam_practice`).
L'UI propose par défaut **Moyen = difficulté 3**, ce qui retourne **0 contenu** au moteur (`select_approved_content`).

**Correctif P0 appliqué** : assouplissement automatique vers les difficultés disponibles + message UI explicite avant création.

- Ce n'est **pas** un problème de codes matière (`ENGLISH`, `PHYSICS_CHEMISTRY` cohérents).
- Ce n'est **pas** lié au commit/push Git.
- Le stock publié reste **faible** (2 contenus/matière) : les devoirs seront limités en taille jusqu'à publication du socle P0.

### Volumes production constatés

- **Anglais** : 2 contenu(s) publiés — un devoir limité est possible si la matière apparaît dans l'UI.
- **Physique-Chimie** : 2 contenu(s) publiés — devoir partiel possible.
- Les centaines de brouillons `draft` / `REVIEW` ne sont **pas** sélectionnables tant qu'ils ne sont pas approuvés et publiés.
- Ce n'est **pas** un bug de codes matière UI (`ENGLISH`, `PHYSICS_CHEMISTRY` cohérents en base).

## Livrables Phase 0

- Matrice : `docs/phase3/LCAI-0018_4E_COVERAGE_MATRIX.csv` (444 lignes)
- File Anglais : `docs/phase3/LCAI-0018_ENGLISH_REVIEW_QUEUE.csv` (24 lignes)
- File Physique-Chimie : `docs/phase3/LCAI-0018_PHYSICS_CHEMISTRY_REVIEW_QUEUE.csv` (29 lignes)

## Plan P0 immédiat

1. Publier les candidats **PASS** Anglais / Physique-Chimie déjà validés structurellement.
2. Compléter un socle minimal par chapitre prioritaire (practice + assessment).
3. Améliorer le message UI quand le stock est insuffisant (`select_approved_content` retourne moins que demandé).
4. Ajouter tests `tests/test_lcai_0018_4e_content_homework.py`.
