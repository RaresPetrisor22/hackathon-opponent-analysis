# Backend

FastAPI + SQLite backend for the Opponent Dossier.

## Setup

```bash
cd backend
uv sync
cp ../.env.example ../.env   # fill in API_FOOTBALL_KEY and OPENAI_API_KEY
```

## Running

```bash
uv run uvicorn app.main:app --reload --port 8000
```

## One-time data pipeline

```bash
uv run python scripts/ingest_season.py    # pulls SuperLiga 2024-25 (~100 reqs)
uv run python scripts/build_archetypes.py # fits KMeans, writes to DB
```

## Linting / type checking

```bash
uv run ruff check .
uv run mypy app
```
