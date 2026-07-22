# Migrations DuckDB

## V1 — application actuelle

La V7.0 applique encore ses colonnes complémentaires dans `core.database.init_db()`.
Cette base reste inchangée pendant la migration progressive.

## V2 — learning model foundation

Les migrations versionnées se trouvent dans `migrations/v2/` et ciblent uniquement
`data/learning_coach_v2.duckdb` ou le chemin fourni avec `--database`.

```console
python -m migrations --database data/learning_coach_v2.duckdb
```

Chaque migration est transactionnelle, journalisée dans `schema_versions` et vérifiée
par checksum. Une migration déjà appliquée ne doit jamais être modifiée.

La migration `005_content_management.sql` ajoute de façon additive le versionnement,
les médias, les tags et les rapports de validation de LCAI-0005.
La migration `006_content_media_links.sql` ajoute les associations ordonnées entre
les métadonnées média et les contenus, sans stockage de fichiers.
