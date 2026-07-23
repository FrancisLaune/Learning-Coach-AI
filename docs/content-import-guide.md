# Guide d’import du curriculum et des contenus

Les importeurs LCAI-0005 JSON, CSV, Excel, Markdown et YAML restent disponibles. Le manifeste LCAI-0009 utilise JSON pour préserver les structures imbriquées (questions, solutions, indices et compatibilités).

## Commandes

```powershell
python scripts/import_catalog.py --source resources/catalog/lcai_0009_catalog.json --dry-run
python scripts/import_catalog.py --source resources/catalog/lcai_0009_catalog.json
```

Le dry-run parse, valide les références, contrôle les tags et détecte les cycles sans ouvrir de transaction d’écriture. Le rapport indique identifiant, lignes lues, créations simulées, erreurs et avertissements.

La clé d’import associe le nom de source et son SHA-256. Un réimport strictement identique est ignoré. Un même identifiant avec un contenu différent produit un conflit explicite. Les imports sont transactionnels : une erreur annule tout le lot.

L’import réel ne doit être exécuté qu’après revue du fichier source. Il ne transforme jamais automatiquement un contenu non validé en contenu Approved.

