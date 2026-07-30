# LCAI-0018D — Industrialisation complète du contenu pédagogique CM2

**Epic :** LCAI-0018 — Industrialisation du référentiel pédagogique

**Statut :** ✅ VALIDÉ (2026-07-30)

**Priorité :** Critique

**Version :** 1.0

**Auteur :** Architecture Learning Coach AI

---

# 1. Objectif

Le ticket LCAI-0018D a pour objectif d'industrialiser complètement le niveau **CM2** afin que celui-ci bénéficie exactement des mêmes capacités que le niveau 4e validé lors de la série LCAI-0018B.

Le ticket ne modifie pas l'architecture de Learning Coach AI.

Il exploite les composants existants afin de produire un patrimoine pédagogique complet, cohérent et publiable.

---

# 2. Objectifs fonctionnels

Le ticket doit permettre :

- la couverture complète des matières CM2 présentes dans le curriculum ;
- la production des contenus pédagogiques ;
- leur validation automatique ;
- leur validation pédagogique ;
- leur publication ;
- leur exploitation immédiate par tous les moteurs de Learning Coach AI.

Aucun développement spécifique au CM2 ne devra être introduit.

Le comportement devra rester entièrement piloté par les données.

---

# 3. Hors périmètre

Le ticket n'a pas vocation à :

- modifier la base DuckDB ;
- modifier les services Homework ;
- modifier Recommendation Engine ;
- modifier Revision Engine ;
- modifier Professor IA ;
- modifier Content Factory.

Les composants existants doivent uniquement être utilisés.

---

# 4. Dépendances

Le ticket nécessite :

- LCAI-0018A validé
- LCAI-0018B validé
- Curriculum CM2 disponible
- Content Factory V2 opérationnelle
- Quality Gates opérationnels
- Homework Engine V2
- Recommendation Engine
- Revision Engine
- Professor IA

---

# 5. Architecture

```text
Curriculum
        │
        ▼
Content Factory
        │
        ▼
Generation Pipeline
        │
        ▼
Automatic Validation
        │
        ▼
Pedagogical Review
        │
        ▼
Approved
        │
        ▼
Publication
        │
        ▼
Coverage Engine
        │
        ▼
Learning Engine
        │
        ├── Homework
        ├── Revision
        ├── Recommendation
        └── Professor IA
```

---

# 6. Curriculum

Le curriculum constitue la seule source de vérité.

Aucune matière ne peut être créée artificiellement.

Le ticket doit parcourir automatiquement :

```
CM2

→ Matière

→ Chapitre

→ Compétence

→ Sous-compétence
```

Le comportement doit être entièrement déterminé par les données présentes dans DuckDB.

---

# 7. Matières concernées

Toutes les matières CM2 présentes dans le curriculum.

Exemples :

- Français
- Mathématiques
- Histoire
- Géographie
- Sciences
- EMC
- Anglais

La liste exacte est déterminée automatiquement à partir du curriculum.

---

# 8. Catalogue pédagogique

Chaque compétence devra disposer d'un ensemble cohérent de contenus.

Minimum attendu :

- cours
- résumé
- fiche
- exercices simples
- exercices moyens
- exercices difficiles
- QCM
- vrai/faux
- texte à trous
- association
- remédiation
- consolidation
- évaluation diagnostique

---

# 9. Pipeline de génération

Chaque contenu suit obligatoirement :

```
Prompt Registry

↓

Generator

↓

Validator

↓

Metadata

↓

Duplicate Check

↓

Near Duplicate

↓

Automatic Review

↓

Pedagogical Review

↓

Approved

↓

Publication
```

Aucune génération directe ne doit être autorisée.

---

# 10. Quality Gates

Tous les contenus doivent satisfaire :

- validation JSON
- validation schéma
- validation pédagogique
- validation curriculum
- validation difficulté
- validation compétences
- validation métadonnées
- validation cohérence

En cas d'échec :

- rejet
- journalisation
- rapport détaillé

---

# 11. Coverage Engine

Le recalcul doit produire les indicateurs suivants :

- couverture par matière
- couverture par chapitre
- couverture par compétence
- couverture par difficulté
- couverture Approved
- couverture publiée

Les contenus Draft ne doivent jamais être pris en compte.

---

# 12. Homework Engine

Validation de la génération :

- devoir court
- devoir moyen
- devoir long
- devoir adaptatif
- consolidation
- révision

Le comportement doit être identique au niveau 4e.

---

# 13. Recommendation Engine

Chaque compétence doit disposer d'un nombre suffisant de contenus pour permettre :

- recommandations adaptatives ;
- progression automatique ;
- remédiation.

---

# 14. Professor IA

Le Professeur IA doit répondre exclusivement à partir :

- du curriculum ;
- des contenus Approved ;
- des compétences publiées.

Aucun contenu Draft ne peut être utilisé.

---

# 15. Tests obligatoires

Tests unitaires

Tests d'intégration

Tests de génération

Tests de validation

Tests de publication

Tests Coverage

Tests Homework

Tests Recommendation

Tests Revision

Tests Professor IA

Tests de non-régression

Tous les tests doivent être verts.

---

# 16. Livrables

- Rapport de génération
- Rapport de validation
- Rapport de publication
- Rapport Coverage
- Rapport Duplicate
- Rapport Near Duplicate
- Rapport final CM2

---

# 17. Critères d'acceptation

Le ticket est accepté uniquement si :

- 100 % des matières CM2 sont couvertes ;
- 100 % des chapitres disposent de contenus publiables ;
- 100 % des compétences disposent de contenus Approved ;
- les moteurs Homework, Revision, Recommendation et Professor IA fonctionnent sans adaptation spécifique au CM2 ;
- les rapports de couverture sont générés ;
- les tests sont entièrement validés.

---

# 18. Definition of Done

Le niveau CM2 est considéré comme industrialisé lorsque :

- le curriculum est intégralement couvert ;
- tous les contenus sont validés ;
- les contenus sont publiés ;
- les moteurs de Learning Coach AI exploitent ces contenus sans développement spécifique ;
- la couverture est certifiée par le Coverage Engine.

---

# 19. Checklist de validation

- [ ] Curriculum vérifié
- [ ] Matières couvertes
- [ ] Chapitres couverts
- [ ] Compétences couvertes
- [ ] Génération terminée
- [ ] Validation automatique OK
- [ ] Validation pédagogique OK
- [ ] Publication effectuée
- [ ] Coverage recalculé
- [ ] Homework validé
- [ ] Recommendation validée
- [ ] Revision validée
- [ ] Professor IA validé
- [ ] Tests verts
- [ ] Rapport final généré