# Migrations DuckDB

La V7.0 applique automatiquement les colonnes complémentaires avec `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.
La base V6.x reste compatible et les comptes, devoirs et résultats existants sont conservés.
