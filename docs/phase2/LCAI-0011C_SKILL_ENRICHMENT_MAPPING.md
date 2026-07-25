# LCAI-0011C — Cartographie de l'enrichissement

## Principe de lecture

Chaque chapitre conserve sa compétence LCAI-0011B ou LCAI-0009. Elle est
classée `KEEP / LEGACY_REFERENCED`. Deux compétences fines sont ajoutées par
profil disciplinaire, sauf pour les quatorze chapitres explicitement détaillés
ci-dessous. Aucun identifiant historique n'est renommé ou supprimé.

La cartographie complète et machine-readable est définie dans
`resources/curriculum/lcai_0011c_curriculum_enriched_2026_2027.json` :

```text
base_datasets
→ chapitre stable existant
→ profil de matière ou override de chapitre
→ code SK-ENR-{chapitre}-{suffixe}
→ sous-compétence SUB-ENR-{chapitre}-{skill}-{suffixe}
```

Cette règle couvre chacun des 166 chapitres sans recopier ni altérer le
référentiel LCAI-0011B.

## Mapping chapitre par chapitre

Les anciens profils standard par matière ont été refusés lors de l'audit
pédagogique. Ils ne sont plus utilisés pour produire le curriculum actif.

Les 152 chapitres concernés sont maintenant décrits individuellement dans :

`resources/curriculum/lcai_0011c_chapter_competencies_2026_2027.json`

Chaque entrée contient le code stable du chapitre et une liste de compétences
disciplinaires propres à son contenu. Les quantités varient selon le besoin :
deux à sept compétences nouvelles, sans objectif numérique uniforme.

Les 14 overrides détaillés restent dans le manifeste principal. L'union :

```text
152 décompositions explicites
+ 14 overrides
= 166 chapitres couverts
```

## Overrides de chapitre

| Chapitre stable | Compétence historique | Nouvelles compétences |
|---|---|---|
| `CH-MATHEMATICS-CM1-FRACTIONS` | conservée | représenter ; comparer |
| `CH-FRENCH-CM2-GRAMMAR` | conservée | classes ; fonctions ; accords |
| `CH-MATHEMATICS-6E-NUMBERS` | conservée | décimaux ; fractions ; calcul |
| `CH-FRENCH-6E-LANGUAGE` | conservée | phrase ; verbes ; accords |
| `CH-MATHEMATICS-5E-FRACTIONS` | conservée | quotient ; équivalence ; opérations ; problèmes |
| `CH-HISTORY-5E-MEDIEVAL` | conservée | repères ; comparaison ; source |
| `CH-GEOGRAPHY-5E-POPULATION` | conservée | indicateurs ; carte ; explication |
| `CH-MATHEMATICS-4E-PYTH` | conservée | configuration ; calcul ; réciproque |
| `CH-FRENCH-4E-GRAMMAR` | conservée | propositions ; fonctions ; transformation |
| `CH-MATHEMATICS-3E-EQUATIONS` | conservée | modéliser ; résoudre ; interpréter |
| `CH-FRENCH-3E-TEXTANALYSIS` | conservée | explicite ; inférence ; procédé |
| `CH-ENGLISH-3E-PAST` | conservée | formes ; questions/négations ; récit |
| `CH-PHYSICS_CHEMISTRY-3E-SPEED` | conservée | données ; calcul ; graphique |
| `CH-SVT-3E-CELL` | conservée | observation ; organisation ; preuve |

## Réconciliation

- Les 166 compétences larges placées restent présentes.
- Les compétences spécifiques sont ajoutées sans héritage de maîtrise.
- Les sous-compétences sont réservées aux décompositions qui améliorent
  réellement le diagnostic.
- Les relations enrichies existantes et les relations justifiées des overrides
  restent autoritatives.
- Les 283 compétences issues des profils refusés sont retirées de
  `curriculum_skill_details` et `program_skills`. Leurs enregistrements sont
  conservés non placés durant la migration progressive.
- Les 68 contenus Approved restent sur leur mapping antérieur.
- Les 25 compétences historiques non placées restent
  `LEGACY_REFERENCED`; aucune suppression ou fusion automatique.
