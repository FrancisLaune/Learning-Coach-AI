# LCAI-0011C — Rapport de réalisation

## Résumé

Le curriculum de référence est passé d'une structure essentiellement
navigationnelle à un modèle mesurable. Les 166 chapitres et toutes les
références historiques sont conservés. Une matrice explicite définit la
décomposition disciplinaire des 152 chapitres auparavant génériques, en
complément des 14 overrides, sans créer de contenu éducatif ni modifier les
mappings Approved.

## Git pre-flight

- Branche : `develop`.
- Commit de départ : `2f6c82e Configure DuckDB files for Git LFS`.
- `develop` synchronisée avec `origin/develop`.
- Arbre initial propre.
- LFS : `data/learning_coach_v2.duckdb` et
  `data/objectif_brevet_2027.duckdb`.

## Architecture

Le service d'import existant résout désormais un artefact d'enrichissement
différentiel contre les datasets validés. Il :

1. charge LCAI-0009 et LCAI-0011B ;
2. déduplique leurs références stables ;
3. applique une décomposition explicite ou un override de chapitre ;
4. produit le contrat plat existant ;
5. valide l'ensemble ;
6. persiste dans la transaction existante ;
7. conserve les projections `program_skills` et `skill_prerequisites`.

Le checksum d'un enrichissement porte sur le document résolu, donc une
évolution d'un dataset de base entraîne un nouvel identifiant sémantique.

Le read model `CurriculumService.quality_metrics()` expose les mesures globales
et la ventilation niveau/matière sans SQL d'interface.

## Validation pédagogique

Le validateur détecte désormais :

- relation dupliquée ;
- type de relation invalide ;
- sous-compétence identique à sa compétence ;
- compétence qui répète simplement son chapitre ;
- formulations génériques potentiellement non mesurables, en avertissement.

Ces signaux complètent la validation humaine et ne prétendent pas la
remplacer.

## Import et base

- Import correctif : 1 247 lignes résolues, 715 objets créés et 532
  inchangés. La réconciliation retire les profils refusés du curriculum actif.
- Réimport idempotent : validé automatiquement sur base isolée, sans
  duplication ni changement sémantique.
- Migration structurelle : aucune.
- Migrations historiques : aucune modification.
- Base V2 : données de référence et projections de compatibilité uniquement.
- Bases V1 : aucune modification.

## Avant / après

| Mesure | Avant | Après |
|---|---:|---:|
| Chapitres | 166 | 166 |
| Compétences stockées | 191 | 1 227 |
| Compétences actives ou historiques utiles | 191 | 944 |
| Placements | 166 | 919 |
| Sous-compétences | 42 | 78 |
| Relations enrichies | 69 | 88 |
| Approved | 68 | 68 |
| Tests | 182 | 193 |

## Compatibilité

- `curriculum_skill_details` reste l'autorité de placement.
- Placements sans `program_skills` : 0.
- `curriculum_skill_relations` reste l'autorité des prérequis.
- Relations orphelines ou auto-référentes : 0.
- Graphe cyclique : non.
- Approved résolus : 68/68.
- Maîtrises avant/après : 0/0 dans les deux projections de la base contrôlée.
- Aucun score n'est synthétisé.

## Tests ajoutés

`tests/test_curriculum_skill_enrichment.py` contrôle :

- provenance et absence de contenu ;
- validation structurelle complète et graphe acyclique ;
- plusieurs compétences par chapitre ;
- métriques déterministes ;
- sous-compétences optionnelles et distinctes ;
- tranche précise des fractions en 5e ;
- idempotence ;
- compatibilité Approved, programme, graphe et maîtrise ;
- navigation sur un curriculum sans contenu.

## Fichiers

Créés :

- `resources/curriculum/lcai_0011c_curriculum_enriched_2026_2027.json`
- `resources/curriculum/lcai_0011c_chapter_competencies_2026_2027.json`
- `tests/test_curriculum_skill_enrichment.py`
- `docs/phase2/LCAI-0011C_CURRICULUM_QUALITY_REPORT.md`
- `docs/phase2/LCAI-0011C_SKILL_ENRICHMENT_MAPPING.md`
- `docs/phase2/LCAI-0011C_PEDAGOGICAL_AUDIT.md`
- `docs/phase2/LCAI-0011C_IMPLEMENTATION_REPORT.md`

Modifiés :

- `domain/curriculum/repositories.py`
- `domain/curriculum/validation.py`
- `infrastructure/repositories/curriculum.py`
- `services/curriculum/services.py`
- `data/learning_coach_v2.duckdb`

## Limites

- Les 152 chapitres hors overrides ont désormais une décomposition propre.
  Une validation éditoriale humaine demeure nécessaire avant de présenter les
  formulations Learning Coach comme définitivement approuvées.
- Les 283 compétences provenant des profils refusés sont non placées et
  retirées de `program_skills`. Elles restent physiquement présentes pendant
  la migration progressive, sans contenu, maîtrise, session ou recommandation.
- Les compétences nouvelles n'ont généralement pas de contenu Approved et ne
  deviennent donc pas exécutables.
- Les compétences historiques ne sont pas dépréciées faute de lifecycle
  explicite et afin de préserver les références.
- Aucun Content Factory n'est commencé.

## Quality gates

- `python -m ruff check .` : succès.
- `python -m ruff format --check .` : 173 fichiers conformes.
- `python -m mypy .` : succès, 173 fichiers contrôlés.
- `python -m pytest` via le contrôle consolidé : 193 tests réussis en
  185,70 s.
- `python scripts/check_quality.py` : succès complet.
- `python -m compileall ...` : succès.
- `git diff --check` : succès.
- Streamlit : démarrage réussi sur le port de contrôle 8519.
- Endpoint `/_stcore/health` : HTTP 200, réponse `ok`.

Une première passe MyPy avait détecté une annotation trop générale dans un
helper de test. L'annotation a été corrigée ; les deux relances MyPy passent.

## Conclusion

**READY FOR CONTENT TAXONOMY / CONTENT FACTORY PREPARATION**
