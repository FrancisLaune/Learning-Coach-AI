# Learner Cognitive Profile

Statut : référence Architecture Blueprint v1.0

## Finalité

Le **Learner Cognitive Profile** décrit comment un apprenant apprend, indépendamment de ce qu'il maîtrise. La maîtrise répond à « que sait-il faire ? »; le profil cognitif répond à « dans quelles conditions apprend-il, retient-il et progresse-t-il ? ».

Il s'agit d'une estimation pédagogique évolutive, non d'un diagnostic médical, psychologique ou d'une caractéristique immuable. Chaque indicateur porte une valeur, un niveau de confiance, une fenêtre d'observation, une date de calcul et une version de modèle. Une donnée insuffisante produit `unknown`, jamais une valeur inventée.

## Indicateurs canoniques

Les valeurs normalisées sont dans `[0,1]`, sauf les durées. Les estimations peuvent exister globalement et, lorsqu'il y a assez de preuves, par `Subject`, `Domain` ou modalité.

| Indicateur | Définition et calcul initial | Évolution | Influence sur les recommandations |
|---|---|---|---|
| `learning_speed` | Pente robuste de progression de `Mastery` par unité de pratique utile, corrigée de la difficulté et des indices | Mise à jour après un minimum de sessions distinctes; lissage exponentiel | Taille des pas de difficulté, quantité de répétitions et durée estimée d'un parcours |
| `retention_capability` | Taux de réussite aux rappels différés, corrigé du délai, de la difficulté et de la maîtrise initiale | Mise à jour uniquement sur des rappels espacés, pas sur répétitions immédiates | Intervalle de révision et proportion de rappels dans une session |
| `confidence_stability` | Stabilité de la confiance de maîtrise face à des preuves variées; inverse de la variance des mises à jour, pondérée par la diversité | Décroît si les performances oscillent entre contextes; augmente avec résultats cohérents | Préfère validation sur contenus variés avant montée de difficulté |
| `fatigue_sensitivity` | Dégradation intra-session de précision/temps par rapport au baseline, après correction de la difficulté | Calcul par fenêtres de position et durée; pas d'inférence sur une session isolée | Durée de session, pauses, alternance et placement des activités exigeantes |
| `preferred_learning_modality` | Performance et engagement comparés entre modalités disponibles (`worked_example`, `guided_practice`, `recall`, etc.) | Distribution probabiliste avec exploration minimale; jamais une étiquette fixe | Ajuste la composition, sans exclure durablement les autres modalités |
| `average_response_time` | Médiane robuste du temps de réponse par difficulté/type, hors valeurs invalides et abandons | Fenêtre récente + baseline longue; segmentation lorsque les volumes suffisent | Estimation de durée, nombre de questions et détection d'écarts inhabituels |
| `regularity` | Régularité des jours actifs et respect des révisions planifiées sur une fenêtre glissante | Recalcul quotidien/hebdomadaire; tolère vacances et indisponibilités déclarées | Plans plus courts et fréquents ou regroupés, rappels et marge avant objectif |
| `error_recurrence` | Probabilité qu'une catégorie d'erreur réapparaisse sur une même `Skill` après correction | Décroît après rappels réussis espacés; augmente sur erreurs similaires | Priorise remédiation, exemple guidé et variation de contexte |
| `motivation_trend` | Tendance de signaux observables : démarrage/achèvement, abandons, choix de continuer, auto-évaluation facultative | Fenêtre courte comparée à une baseline; faible confiance sans déclaration explicite | Ton, longueur de session, difficulté progressive et objectifs intermédiaires |
| `forgetting_resistance` | Résistance estimée à l'oubli, dérivée de la demi-vie des `Mastery` par compétence et agrégée avec confiance | Mise à jour lors des rappels différés; distincte de la réussite immédiate | Date de prochaine révision et dosage consolidation/nouveauté |

## Calcul et qualité des observations

Le pipeline est déterministe :

1. Valider l'événement (`Attempt`, durée, difficulté, modalité, position dans la session).
2. Transformer l'événement en observation normalisée, sans modifier directement le profil.
3. Corriger les facteurs connus : difficulté, aide reçue, répétition de la même question et maîtrise préalable.
4. Agréger avec estimateurs robustes et fenêtres courte/longue.
5. Calculer la confiance selon volume, diversité, récence et qualité des données.
6. Émettre un événement de profil et reconstruire la projection courante.

Les premières versions privilégient des règles interprétables. Un modèle statistique ultérieur doit battre ces baselines, rester calibré et conserver une explication exploitable.

## Dynamique et garde-fous

- Le profil évolue lentement; une tentative isolée ne change pas une tendance.
- Les signaux récents pèsent davantage sans effacer la baseline longue.
- Les indicateurs contextuels ne sont généralisés que si les preuves couvrent plusieurs contenus.
- Toute recommandation indique quels indicateurs ont compté et leur confiance.
- La modalité « préférée » optimise l'apprentissage observé, pas seulement le confort déclaré.
- Fatigue et motivation sont des hypothèses pédagogiques à faible portée; elles ne servent jamais à étiqueter l'apprenant.
- L'apprenant peut corriger ses préférences déclarées et demander la réinitialisation des signaux non nécessaires.

## Interaction avec `Mastery` et le `Decision Engine`

`Mastery` reste calculée par `Skill`/`SubSkill`. Le profil cognitif module les paramètres de décision, mais ne remplace ni les preuves ni les objectifs :

```text
Decision inputs
  = due Mastery reviews
  + active Objectives
  + eligible content
  + Learner Cognitive Profile
  + session constraints
```

Exemples : une faible résistance à l'oubli rapproche les rappels; une forte sensibilité à la fatigue limite la durée; une confiance instable demande des contextes variés; une récurrence d'erreur élevée sélectionne une remédiation ciblée; une tendance de motivation descendante réduit la taille du prochain palier sans abaisser artificiellement les exigences finales.

## Persistance et confidentialité

Conserver des observations immuables et une projection `learner_cognitive_profiles`. Les facteurs détaillés sont historisés avec version du modèle. Les indicateurs sensibles sont accessibles uniquement aux cas d'usage autorisés, soumis à rétention et export/suppression. Aucun indicateur cognitif n'est envoyé au LLM sans nécessité explicite et minimisation.

## Tests

- bornes, confiance minimale et comportement `unknown`;
- invariance à l'ordre pour agrégations qui doivent l'être;
- résistance aux valeurs extrêmes et durées manquantes;
- scénarios longitudinaux synthétiques;
- absence d'influence lorsque la confiance est insuffisante;
- audits de biais entre matières, modalités et rythmes d'apprentissage;
- explication reproductible pour chaque contribution au `Decision`.

