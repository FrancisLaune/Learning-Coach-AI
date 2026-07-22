# Conversation Memory

Statut : référence Architecture Blueprint v1.0

## Définition

La **Conversation Memory** est une projection pédagogique contrôlée mise à disposition de l'AI Coach. Ce n'est ni la mémoire interne ni une mémoire permanente du LLM. Le fournisseur LLM est traité comme sans état : à chaque interaction, l'application reconstruit un contexte minimal depuis les données autorisées.

## Contenu pédagogique

| Élément | Source autoritative | Forme mémorisée |
|---|---|---|
| Sessions précédentes | `LearningSession`, `Attempt` | résumés datés, contenus couverts, résultats et aides utilisées |
| Recommandations précédentes | `Recommendation`, `Decision` | proposition, raisons, acceptation/refus et résultat ultérieur |
| Erreurs récurrentes | preuves et catégories d'erreur | `Skill`/`SubSkill`, catégorie, fréquence, dernière occurrence, confiance |
| Objectifs apprenant | `Objective` | cible, échéance, progression et priorité |
| Historique motivationnel | signaux autorisés du profil cognitif | tendance agrégée et confiance, jamais diagnostic ou jugement |
| Réussites récentes | `Attempt`, `Mastery`, `Progress` | accomplissements vérifiés, date et source |

La mémoire ne contient pas de credential, secret, conversation complète par défaut, donnée d'un autre apprenant ou inférence non traçable.

## Construction

1. Autoriser la demande et déterminer sa finalité.
2. Récupérer les faits via des ports de lecture filtrés par apprenant.
3. Choisir une fenêtre temporelle et un budget de contexte adaptés.
4. Classer les éléments par pertinence : question courante, décision liée, erreurs récurrentes, objectif, réussite récente.
5. Résumer de façon déterministe avec identifiants de source et niveau de confiance.
6. Pseudonymiser/minimiser, puis fournir un `PedagogicalMemoryContext` structuré au pipeline AI Coach.

## Bénéfices

Cette mémoire permet au Coach de ne pas répéter une explication inefficace, de relier une erreur à une difficulté récurrente, de rappeler un objectif proche, de célébrer une réussite réelle et d'adapter la profondeur de l'indice. Elle améliore la continuité sans autoriser le LLM à inventer une histoire de l'apprenant.

Exemple : si trois erreurs vérifiées concernent le cas direct de Thalès et qu'une recommandation précédente d'exemple guidé a été acceptée, le Coach peut rappeler la méthode et proposer un indice différent. Il ne peut pas conclure que l'apprenant « est mauvais en géométrie ».

## Persistance et cycle de vie

Les faits sources restent dans leurs tables métier. Les résumés de mémoire sont des projections recalculables, versionnées et expirables. Une politique définit : fenêtre récente, nombre maximal d'éléments, durée de rétention, droit d'accès, export et suppression. Les corrections de données invalident les résumés concernés.

Les messages bruts ne sont conservés que si une finalité approuvée l'exige, pour une durée courte et avec expurgation. Le contexte envoyé au fournisseur est journalisé par hash et références, pas nécessairement en clair.

## Garde-fous et tests

- isolation stricte entre apprenants et rôles;
- chaque fait est relié à une source; `unknown` si absent;
- les signaux motivationnels à faible confiance ne sont pas exposés comme faits;
- le LLM ne peut écrire directement dans la mémoire;
- seules des actions validées produisent événements/recommandations métier;
- tests d'autorisation, fuite inter-utilisateur, expiration, suppression, budget, classement et reconstruction;
- tests de factualité vérifiant chaque assertion contre le contexte fourni.

