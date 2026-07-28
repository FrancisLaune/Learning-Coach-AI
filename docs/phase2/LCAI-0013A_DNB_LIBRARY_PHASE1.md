# LCAI-0013A — DNB Official Exam Library — Phase 1

## État
**IN PROGRESS**

## Objectif
Construire une bibliothèque traçable de sujets DNB série générale, distincte des contenus pédagogiques générés.

## Sources officielles retenues
1. Ministère de l'Éducation nationale — sujets 2026.
2. Éduscol — annales officielles proposées depuis 2018.
3. Éduscol — définition actuelle des épreuves du DNB.

## Règle de provenance
Les catégories doivent rester distinctes :
- `OFFICIAL_EXAM`
- `OFFICIAL_ZERO_SUBJECT`
- `MOCK_EXAM`
- `GENERATED_MOCK_EXAM`

Un brevet blanc trouvé sur un site tiers ne doit jamais être présenté comme un sujet officiel.

## Rupture de format à conserver
### 2026
Mathématiques :
- 20 min automatismes, sans calculatrice, 6 points ;
- 1 h 40 raisonnement/résolution, calculatrice autorisée, 14 points.

Français :
- compréhension/grammaire/interprétation ;
- dictée ;
- rédaction.

Histoire-Géographie-EMC :
- histoire-géographie ;
- EMC.

Sciences :
- deux disciplines parmi physique-chimie, SVT, technologie.

### 2027+
Les écrits portent sur les programmes de la classe de 3e. Les annales antérieures restent utilisables pour l'entraînement, mais devront être marquées avec un niveau de compatibilité avec le référentiel 3e actuel.

## Première base indexée
- DNB 2026 Métropole — Mathématiques.
- DNB 2026 Métropole — Français, composante compréhension/grammaire.
- DNB 2026 Métropole — Histoire-Géographie-EMC.
- DNB 2026 Métropole — Sciences.
- Sujet zéro officiel Mathématiques A.
- Sujet zéro officiel Mathématiques B.

## Structure Learning Coach proposée

```text
Exam
→ Component
→ Exercise
→ Question
→ Skill mapping
→ Student attempt
→ Score
→ Skill evidence
→ Remediation
```

Chaque question pourra être reliée à une ou plusieurs Skills 3e LCAI-0011C, avec :
- Skill primaire ;
- Skills secondaires ;
- difficulté ;
- points ;
- temps indicatif ;
- confiance du mapping ;
- statut de revue.

## Prochain lot
1. Indexer 2025 → 2018, série générale.
2. Priorité Métropole, puis Amérique du Nord, Asie, centres étrangers.
3. Compléter 2017/2016 uniquement à partir d'archives fiables clairement étiquetées.
4. Décomposer les sujets en exercices/questions.
5. Mapper les questions vers les Skills 3e.
6. Constituer ensuite une collection séparée de brevets blancs.
