# Learning Engine — architecture conceptuelle

## Responsabilité

Le Learning Engine transforme des preuves d'apprentissage en `Mastery`, oubli estimé et **Learner Cognitive Profile**. Il ne choisit pas à lui seul le parcours : le [Decision Engine](decision-engine.md) orchestre le calendrier et les contenus à partir de ses projections. Il ne rend pas l'UI, n'écrit pas directement en base et n'appelle pas de LLM.

## Représentation pédagogique

Le référentiel suit `Program → Subject → Domain → Skill → SubSkill`, avec prérequis séparés. Chaque `Question` référence une ou plusieurs `Skill`/`SubSkill` pondérées et appartient à un `Exercise`. Le moteur travaille au niveau le plus fin disponible et agrège vers les parents par moyenne pondérée, sans laisser une bonne note globale masquer une lacune critique. Voir le [Domain Model](architecture-domain-model.md).

État minimal par couple apprenant/compétence :

- `mastery_score` dans `[0,1]`;
- `confidence` dans `[0,1]`, fonction de quantité/diversité des preuves;
- date de dernière preuve et prochaine révision;
- demi-vie ou stabilité estimée;
- historique récent des erreurs et difficultés;
- version de modèle ayant produit l'état.

## Mise à jour de la maîtrise

Une première version déterministe peut utiliser une mise à jour exponentielle :

```text
evidence = correctness_or_partial_score
           × difficulty_weight
           × time_quality
           × question_skill_weight

learning_rate = base_rate × (1 - confidence_floor_adjustment)
new_mastery = clamp(old_mastery + learning_rate × (evidence - old_mastery), 0, 1)
```

- `difficulty_weight` augmente la valeur d'une réussite difficile, mais évite de punir deux fois un échec difficile.
- `time_quality` est borné; une réponse rapide ne compense jamais une erreur.
- Les tentatives répétées sur la même question ont un poids décroissant.
- La confiance croît avec le nombre, la récence et la diversité des questions, pas seulement avec le volume.
- Toute constante appartient à un ruleset versionné et testé.

Le score actuel de `analytics/mastery.py` sert de baseline de comparaison, pas de vérité à recopier : il agrège au niveau chapitre/difficulté et n'applique pas la récence.

## Récence, oubli et répétition espacée

Entre deux preuves, la maîtrise disponible est estimée par une courbe d'oubli :

```text
retention(t) = mastery_at_evidence × 2 ^ (-elapsed_days / half_life_days)
```

La demi-vie augmente après un rappel réussi et diminue après un échec, avec bornes configurées. La prochaine échéance est le premier instant où la rétention prédite passe sous le seuil cible. Une compétence jamais vue ou à faible confiance reçoit une échéance proche.

La planification doit éviter la sur-sollicitation : limites quotidiennes, espacement minimal, alternance de matières et reprise différée après plusieurs échecs. Les objectifs proches peuvent avancer une échéance mais ne doivent pas supprimer les prérequis.

## Signaux fournis au Decision Engine

Le pipeline de priorité et de sélection ci-dessous appartient désormais au `Decision Engine`; il est conservé ici comme contrat de données fourni par le Learning Engine :

1. Construire les compétences candidates : dues, lacunes ouvertes, objectifs actifs, prérequis nécessaires.
2. Éliminer le contenu archivé, déjà présenté trop récemment, hors niveau ou incompatible avec la durée.
3. Le `Decision Engine` calcule pour chaque candidat :

```text
priority = due_urgency
         + mastery_gap
         + goal_urgency × goal_weight
         + prerequisite_value
         + uncertainty_bonus
         + variety_bonus
         - recent_exposure_penalty
         - overload_penalty
```

4. Choisir d'abord la compétence, puis une activité d'une difficulté située dans la zone de défi appropriée.
5. Départager de façon pseudo-aléatoire avec graine enregistrée afin de rester reproductible.
6. Retourner décision, alternatives classées, facteurs et codes de raison.

La difficulté monte après une maîtrise fiable, reste stable en consolidation et descend ou propose une fiche guidée après échecs répétés. Un objectif daté augmente progressivement son poids; un prérequis faible bloque les activités qui le supposent.

## Explicabilité

Chaque décision produit une structure indépendante du texte :

```json
{
  "reason_codes": ["REVIEW_DUE", "GOAL_SOON", "LOW_MASTERY"],
  "factors": {"predicted_retention": 0.54, "target": 0.80, "days_to_goal": 12},
  "selected": {"skill_id": 42, "activity_id": 301, "difficulty": 2},
  "alternatives": [{"activity_id": 298, "score": 0.71}],
  "ruleset_version": "engine-v1"
}
```

L'UI peut traduire ces codes avec des gabarits. Le LLM peut reformuler la même explication, sans changer les faits ou la sélection.

Le `Scheduler` calcule uniquement les échéances. Le `Selector` filtre et classe uniquement les contenus demandés. Le `Decision Engine` arbitre l'ensemble.

## Learner Cognitive Profile

En plus de `Mastery`, le moteur maintient un profil cognitif versionné : vitesse d'apprentissage, rétention, stabilité de confiance, sensibilité à la fatigue, modalité préférée, temps de réponse, régularité, récurrence d'erreur, tendance motivationnelle et résistance à l'oubli. Les calculs, niveaux de confiance et garde-fous sont définis dans [Learner Cognitive Profile](learner-cognitive-profile.md).

## Interfaces

- Entrée : profil, objectifs, états de maîtrise, erreurs récentes, activités éligibles, temps disponible, horloge et configuration versionnée.
- Sortie : nouvelles projections `Mastery`, profil cognitif, oubli estimé et observations structurées consommables par le `Decision Engine`.
- Dépendances injectées : horloge, générateur pseudo-aléatoire, repositories via le cas d'usage.

## Tests et suivi

- unitaires sur bornes, monotonie, récence, difficulté, demi-vie et priorités;
- tests par propriétés : scores bornés, pas d'activité inéligible, décision reproductible;
- scénarios pédagogiques « golden » validés par un expert;
- simulation de cohortes synthétiques pour détecter boucles, famine de compétence et progression trop rapide;
- comparaison offline au baseline actuel avant activation;
- métriques : taux de rappel, calibration maîtrise/réussite, diversité, délai des activités dues, taux de refus et dérive par matière.

Le moteur est activé derrière un feature flag et peut fonctionner en mode « shadow » : il journalise ce qu'il aurait choisi sans modifier le parcours.
