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
- `app.py` : point d'entrée Streamlit minimal ;
- `application/` : contrats et orchestration applicative en cours d'extraction ;
- `domain/` : vocabulaire métier minimal, sans framework ;
- `infrastructure/` : adaptateurs de configuration, logging et repositories DuckDB V1 ;
- `services/` : services techniques de démarrage ;
- `ui/` : application Streamlit et composants de présentation ;
- `core/` : implémentation V1 conservée pendant la migration progressive ;
- `subjects/` : modules par matière ;
- `analytics/` : maîtrise et adaptation ;
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

## Development setup

### Prerequisites

- Python 3.13 is recommended. Python 3.12 through 3.14 are supported by the project configuration.
- Git and a terminal (PowerShell on Windows or a POSIX shell on Linux/macOS).

Python 3.14 is currently usable with the tested runtime dependencies, but 3.13 remains the recommended stable baseline while the wider development toolchain matures.

### Create the virtual environment

Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Linux/macOS:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Install runtime dependencies only:

```console
python -m pip install -r requirements.txt
```

For development and tests, install the development requirements instead; they include the runtime requirements:

```console
python -m pip install -r requirements-dev.txt
```

### Configuration and secrets

The application requires no API key at present. It reads two optional environment variables:

- `LCAI_DATABASE_PATH`: DuckDB path, relative to the project root by default;
- `LCAI_LOG_LEVEL`: one of `CRITICAL`, `ERROR`, `WARNING`, `INFO`, or `DEBUG`.

See `.env.example` for fictitious values. The application does not load `.env` files automatically, so set variables in the process environment or in the launch environment. Never commit `.env` or `.streamlit/secrets.toml`; both are ignored.

### Run the application

```console
python -m streamlit run app.py
```

### Tests and code quality

Run all local checks with the cross-platform script:

```console
python scripts/check_quality.py
```

Individual commands:

```console
python -m ruff check .
python -m ruff format --check .
python -m ruff format .
python -m mypy
python -m pytest
python -m pytest --cov
```

The full pre-commit check is `python scripts/check_quality.py`. It stops at the first failure and returns a non-zero exit code.

MyPy currently enforces the typed infrastructure, analytics, tests, and scripts. Legacy database, exercise-engine, subject, and Streamlit modules remain outside the initial MyPy gate because typing them safely belongs to the architecture-refactoring work; the checked scope should expand as those boundaries are extracted.

### Documentation

The official technical reference is the [Architecture Blueprint v1.0](docs/architecture/LCAI-0001-architecture-blueprint.md). All architecture documents are under [`docs/architecture/`](docs/architecture/).

## Architecture documentation

- [Architecture blueprint](docs/architecture/LCAI-0001-architecture-blueprint.md)
- [Current-state audit](docs/architecture/current-state-audit.md)
- [Target project structure](docs/architecture/target-project-structure.md)
- [DuckDB V2 design](docs/architecture/duckdb-v2-design.md)
- [Learning Engine design](docs/architecture/learning-engine-design.md)
- [AI Coach design](docs/architecture/ai-coach-design.md)
- [Release 1.0 roadmap](docs/architecture/release-1-roadmap.md)
