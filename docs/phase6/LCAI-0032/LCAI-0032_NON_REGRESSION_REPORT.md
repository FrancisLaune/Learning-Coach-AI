# LCAI-0032 — Non-Regression Report

| Zone | Impact |
|------|--------|
| Auth / users objectif_brevet | Inchangé (tables legacy conservées) |
| LCAI-0031 V2 `learning_coach_v2` | Non modifié par ce ticket |
| Streamlit runtime | Pas de scraping Éduscol ajouté |
| Banques `subjects/*.py` | Toujours présentes comme générateurs ; catalogue DuckDB = source de vérité contenu |

Risque résiduel : double source temporaire (Python generators + DuckDB) jusqu’à bascule complète homework engine sur `search_exercises`.
