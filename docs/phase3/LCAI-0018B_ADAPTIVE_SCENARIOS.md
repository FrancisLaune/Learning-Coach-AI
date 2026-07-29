# LCAI-0018B — Scénarios adaptatifs (baseline B0)

Scénarios à valider au Lot B5. Sources de signaux déjà présentes en V2 :

| Signal | Table / service |
|--------|-----------------|
| Maîtrise skill | `longitudinal_mastery_current` |
| Historique séances | `learning_sessions`, `session_activities` |
| Difficulté adaptative devoirs | `HomeworkRequest` + `_difficulty()` |
| Recommandations | `PersonalizedSessionService` |

## Scénarios obligatoires

| Situation | Décision attendue | État B0 |
|-----------|-------------------|---------|
| Échecs répétés | Remédiation / prérequis | Partiel (moteur recommandation, pas devoirs) |
| Réussites stables | Augmenter difficulté | Partiel |
| Réussite après indices | Consolidation | Partiel |
| Notion ancienne | Révision espacée | Partiel |
| Prérequis non maîtrisé | Bloquer avancé | À vérifier Lot B5 |
| Deux élèves différents | Séquences différentes | Non garanti pour devoirs catalogue seul |
