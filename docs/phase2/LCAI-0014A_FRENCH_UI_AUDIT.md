# LCAI-0014A — Audit de l’interface française

## Périmètre

- 12 fichiers de présentation analysés dans `ui/` et `app.py`.
- 462 chaînes littérales visibles analysées par AST.
- Interfaces couvertes : connexion, élève, parent, séances, devoirs,
  progression, recommandations et file de validation.
- Les messages présentés par les contrôleurs et services ont également été
  examinés.

## Résultat

- Occurrences anglaises UI détectées avant correction : 7.
- Occurrences directement traduites : 7.
- Occurrences anglaises UI injustifiées après correction : 0.
- Exceptions UI justifiées détectées par l’auditeur : 0.

Les sept occurrences correspondaient au statut technique `Approved`, présenté
dans les messages du parcours unifié et la file de validation. L’interface
affiche maintenant « approuvé » ou « approuvée ».

Les valeurs dynamiques de matière, niveau, type de contenu, statut, priorité et
couverture passent par `ui/i18n.py`. Les identifiants techniques restent
inchangés.

## Éléments volontairement conservés

- La marque `Learning Coach AI`.
- Les acronymes officiels `EMC`, `SVT` et `DNB`.
- Les codes administratifs `P1` à `P5`.
- Les codes `Tier 1` à `Tier 3` uniquement entre parenthèses après une
  explication française.
- Les identifiants, clés JSON, enums, noms de colonnes et valeurs persistées.

## Limite du framework

Le contrôle visuel relève quelques libellés d’accessibilité fournis directement
par Streamlit (`Deploy`, `Main menu`, `Show password text`, `Choose options`,
`Clear all`, `close by backspace`, `Link to heading`). Ils ne proviennent
d’aucune chaîne du dépôt et ne peuvent pas être traduits par la couche de
présentation applicative. Les libellés fonctionnels adjacents de Learning Coach
AI sont tous en français. Le format des sélecteurs de date est explicitement
forcé à `DD/MM/YYYY`.

## Contrôle automatique

Commande :

```text
python scripts/audit_ui_language.py --json
```

Résultat final :

```text
files_analyzed: 12
visible_strings_analyzed: 462
residual_english_occurrences: 0
justified_exceptions: 0
```
