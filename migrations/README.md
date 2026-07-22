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
