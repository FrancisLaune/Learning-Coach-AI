# LCAI-0014A — Rapport d’implémentation

## Réalisation

- Couche de présentation française centralisée dans `ui/i18n.py`.
- Matières, niveaux, types de contenu, statuts, difficultés, priorités et états
  de couverture traduits sans modifier leurs valeurs techniques.
- Parcours principal, V2 élève, parent et file de validation audités.
- Messages utilisateur contenant `Approved` remplacés par une formulation
  française naturelle.
- Formats français de date, nombre et durée disponibles dans la couche commune.
- Tous les sélecteurs de date applicatifs imposent `DD/MM/YYYY`.
- Prompt de génération existant vérifié : il exige déjà directement le français,
  sauf production linguistique attendue en anglais ou espagnol.
- Contrôle statique reproductible ajouté.
- Contenus pédagogiques Approved inspectés sans écriture.

## Garanties

- Aucune migration DuckDB.
- Aucun contenu pédagogique modifié.
- Aucun lifecycle, identifiant technique, algorithme adaptatif ou règle
  d’approbation modifié.
- Aucun Draft nouvellement exposé.
- Ressources Brevet, CM1, CM2, 6e, 5e et tickets hors périmètre conservés.

## Limite connue

Les libellés d’accessibilité intégrés au frontend Streamlit restent contrôlés
par la bibliothèque et non par le dépôt. Ils sont documentés dans le rapport
d’audit et ne correspondent pas à des chaînes applicatives.

## Validation finale

- `python scripts/audit_ui_language.py --json` : succès, 12 fichiers et
  462 chaînes visibles analysés, 0 occurrence anglaise applicative résiduelle.
- `python -m ruff check .` : succès.
- `python -m ruff format --check .` : succès, 204 fichiers conformes.
- `python -m mypy .` : succès, aucune erreur.
- `python -m pytest -q` : succès, 271 tests réussis.
- `python scripts/check_quality.py` : succès ; Ruff, formatage, MyPy et
  271 tests réussis.
- `python -m compileall . -q` : succès.
- `git diff --check` : succès.
- `python -m streamlit run app.py --server.headless=true --server.port=8521` :
  démarrage réussi, endpoint de santé HTTP 200.
- `python -m streamlit run ui/content_approval_app.py
  --server.headless=true --server.port=8522` : démarrage réussi, endpoint de
  santé HTTP 200.

## Conclusion

La couche applicative est prête pour la revue technique French-First.
La limite liée aux libellés natifs de Streamlit n’affecte ni les règles
pédagogiques ni les données.
