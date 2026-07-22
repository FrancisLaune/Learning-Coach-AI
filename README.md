# Objectif Brevet 2027 — V7.0

V7.0 introduit une architecture modulaire et un moteur pédagogique adaptatif.

## Nouveautés
- suivi du temps des devoirs et entraînements ;
- temps cible par exercice et vitesse moyenne ;
- difficulté enregistrée pour chaque question ;
- score de maîtrise combinant réussite, vitesse, difficulté et volume ;
- recommandation automatique du niveau suivant ;
- analyse globale, par matière, chapitre et devoir ;
- compatibilité avec la base DuckDB V6.x grâce aux migrations automatiques.

## Architecture
- `core/` : base DuckDB et moteur d'exercices ;
- `subjects/` : modules par matière ;
- `analytics/` : maîtrise et adaptation ;
- `ui/` : emplacement des futurs écrans séparés ;
- `ai/` : fondation du coach V7.1 ;
- `reports/` : fondation des rapports ;
- `migrations/` : documentation des évolutions DuckDB.

## Installation Windows
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Copier l'ancienne base dans `data/objectif_brevet_2027.duckdb` avant le premier lancement pour conserver les données.
