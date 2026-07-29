# LCAI-0018B — Contrat de fallback IA (état B0)

## Services existants à réutiliser (interdit : second moteur)

| Couche | Fichier | Rôle |
|--------|---------|------|
| Génération LLM | `infrastructure/generators/openai_content.py` | `OpenAIContentGenerator.generate()` |
| Factory | `services/content/factory.py` | `ContentFactoryService.generate_drafts()` |
| Contrat domaine | `domain/content/factory.py` | `ContentGenerationRequest`, `GeneratedContentCandidate` |
| Gaps offline | `services/content/expansion.py` | `coverage_gaps()`, `CoverageGap.request()` |
| Validation | `services/content/quality.py` | gates structurels |
| Revue IA | `services/content/ai_pedagogical_review.py` | pré-validation pédagogique |
| Publication | `services/content/ai_controlled_publication.py` | publication contrôlée |
| Sélection devoirs | `infrastructure/repositories/unified_experience.py` | `select_approved_content_detailed()` |

## Écart B0 identifié

**Aucun pont runtime** ne relie `HomeworkService` / `select_approved_content_detailed` à `ContentFactoryService`.

Comportement actuel lors d'un déficit :
1. Le moteur retourne moins de contenus que demandé.
2. L'UI affiche « Couverture limitée » ou limite la taille du devoir.
3. Aucun appel LLM à la demande n'est déclenché.

## Contrat d'entrée cible (Lot B4)

Réutiliser `ContentGenerationRequest` avec les champs du ticket :
`request_id`, `CurriculumTarget`, `primary_skill_code`, `pedagogical_intent`, `difficulty`,
`variation_constraints`, `language_code`, empreintes récentes.

## Contrat de sortie cible

Réutiliser `GeneratedContentCandidate` + validation `CandidateValidator` + gates `quality.py`.
Usage séance : autorisé après validation runtime ; **pas de publication catalogue automatique**.

## Conditions d'appel IA (Lot B4)

- Déficit mesuré entre quota demandé et stock éligible `production_learning_catalog`.
- Curriculum/chapitre/skill actifs résolus.
- LLM disponible ; sinon résultat dégradé explicite sans session corrompue.
