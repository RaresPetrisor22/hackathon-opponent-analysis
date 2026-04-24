# Opponent Dossier — FC Universitatea Cluj

Pre-match scouting tool for the coaching staff. Select the next opponent and receive a structured dossier with seven analytical sections generated from API-Football data.

## Quickstart

### Backend

```bash
cd backend
uv sync
cp ../.env.example ../.env   # fill in keys
uv run uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
# set NEXT_PUBLIC_API_URL=http://localhost:8000 in frontend/.env.local
npm run dev
```

Open http://localhost:3000.

## Architecture

```
opponent_analysis/
├── backend/          FastAPI + SQLAlchemy (SQLite)
│   ├── app/
│   │   ├── ingestion/    Pull & cache API-Football JSON
│   │   ├── analysis/     Deterministic stat modules (one per section)
│   │   ├── llm/          LangChain/OpenAI orchestration & prompts
│   │   ├── models/       SQLAlchemy 2.0 ORM models
│   │   ├── schemas/      Pydantic v2 request/response schemas
│   │   └── routes/       FastAPI routers
│   └── scripts/          CLI ingest & cluster scripts
└── frontend/         Next.js 14 App Router + shadcn/ui + Recharts
```

## Dossier Sections

1. **Form & Momentum** — last 5/10 match results, goals scored/conceded trend
2. **Tactical Identity** — average formation, possession style, pressing metrics
3. **Matchup Intelligence** — archetype clustering (hero feature): how they play vs different opponent styles, and which archetype U Cluj maps to
4. **Player Threat & Vulnerability Cards** — key attackers and defensive weak spots
5. **Game State Intelligence** — how they perform when winning/drawing/losing
6. **Referee Context** — cards, fouls, and tendencies for the assigned referee
7. **Gameplan Narrative** — LLM-synthesised tactical recommendation

## Data Sources

- **API-Football v3** (`https://v3.football.api-sports.io`) — fixtures, events, team/player stats, standings, H2H, referee info. 100 req/day on free tier; all responses cached to disk.

## One-time Data Setup

```bash
cd backend
uv run python scripts/ingest_season.py     # pulls SuperLiga 2024-25 from API-Football
uv run python scripts/build_archetypes.py  # runs KMeans, writes archetypes to DB
```

## Branch Rules

- Nobody pushes to main. Create feature branches: `initials/feature-name` (e.g. `pr/eda-form`).
- One teammate review before merge.
- One person per notebook at a time.
- Add any `pip install` packages to `backend/pyproject.toml` (managed by uv).
