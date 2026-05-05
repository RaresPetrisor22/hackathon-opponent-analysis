# U-PPONENT ARCHIVE

Pre-match scouting tool for **FC Universitatea Cluj**. Pick the next SuperLiga opponent, get back a full tactical dossier — form, identity, archetype matchup, player cards, game-state patterns, referee context, media intel, and an LLM-written gameplan.

![Python](https://img.shields.io/badge/python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688)
![Next.js](https://img.shields.io/badge/Next.js-14-black)
![SQLite](https://img.shields.io/badge/db-SQLite-003B57)
![LangChain](https://img.shields.io/badge/LLM-LangChain%20%2B%20OpenAI-1c3c3c)
![Status](https://img.shields.io/badge/status-hackathon-orange)

> SuperLiga 2024/25 · league `283` · FCU team `2599`

---

## What it does

Coach picks the opponent from a dropdown. Backend pulls cached API-Football data, runs six deterministic stat modules in parallel, retrieves Romanian football media from Pinecone, then asks GPT-4o to synthesise a one-page gameplan. Frontend renders eight panels and a chat widget you can grill about the dossier.

The hero feature is **archetype matchup intelligence**: every team in the league is clustered (KMeans) into one of four behavioural archetypes, and the dossier predicts how the opponent's archetype plays against U Cluj's.

The four archetypes:
- Dominant Possession Elite
- Defensive / Low Output
- Long-Range Specialists
- Counter-Attacking Pressing Side

## Stack

**Backend** — FastAPI, SQLAlchemy 2.0 async, aiosqlite, Pydantic v2, httpx, LangChain (`langchain-openai`, `langchain-pinecone`), scikit-learn, pandas. Managed with `uv`. Lint/type via `ruff` + `mypy --strict`. Tests with `pytest-asyncio`.

**Frontend** — Next.js 14 App Router, TypeScript, Tailwind, shadcn/ui, Radix, Recharts, Mermaid, lucide-react.

**Data** — API-Football v3 (everything cached to disk before parsing — the free tier is 100 req/day, you don't get to be wasteful). Pinecone for the media RAG.

## Repo layout

```
backend/
  app/
    main.py                FastAPI app + lifespan init_db
    config.py              pydantic-settings, reads root .env
    db.py                  Async engine + ALTER TABLE shims
    ingestion/             API-Football client + raw JSON cache
    models/                SQLAlchemy 2.0 (Mapped[] style)
    analysis/              6 stat modules + media_intel (Pinecone)
    llm/                   client, prompts, orchestrator
    routes/                health · teams · dossier · referees · chat
    schemas/               Pydantic v2 — the contract for the frontend
  scripts/                 One-shot ingest, clustering, RAG builders
  tests/                   pytest, per-module + integration
frontend/
  app/                     /, /dossier/[teamId]
  components/dossier/      One panel per section + ChatWidget + PrintButton
  components/charts/       Recharts wrappers
  components/ui/           shadcn primitives
  lib/                     api.ts, types.ts, utils.ts
```

## Pipeline

`backend/app/llm/orchestrator.py` runs three stages, strictly sequential:

1. **Parallel analysis** — `RunnableParallel` fans out the six stat modules and the media-intel Pinecone lookup. No LLM calls.
2. **Section enrichment** — short prose summaries for form / identity / matchups / players via `asyncio.gather`. If any of these fail the section just gets an empty summary, the dossier still ships.
3. **Gameplan synthesis** — single `GAMEPLAN_PROMPT | llm.with_structured_output(GameplanNarrative)` call, fed all sections as JSON.

The chat widget (`POST /chat`) is grounded in the dossier JSON plus three SQLite tools (`get_team_roster`, `get_recent_matches`, `get_referee_profile`). It's instructed to refuse anything outside that scope.

## API

| Method | Path | |
|---|---|---|
| `GET` | `/health` | liveness |
| `GET` | `/teams` | dropdown source |
| `GET` | `/dossier/{team_id}` | full `DossierResponse` |
| `GET` | `/referees` | distinct ref names |
| `GET` | `/referees/stats?name=` | per-ref stats |
| `POST` | `/chat` | tactical Q&A on the dossier |

## Setup

You'll need Python 3.11+, Node 18+, [`uv`](https://github.com/astral-sh/uv), and keys for API-Football, OpenAI, Pinecone.

`.env` at the repo root:

```env
API_FOOTBALL_KEY=...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o
PINECONE_API_KEY=...
```

### Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

Open http://localhost:3000.

### Data bootstrap (one-time)

```bash
cd backend
uv run python scripts/ingest_season.py
uv run python scripts/ingest_standings_h2h.py
uv run python scripts/ingest_referees.py
uv run python scripts/build_archetypes.py
uv run python scripts/scrape_media.py
uv run python scripts/ingest_pinecone.py
```

## Dev

```bash
cd backend
uv run pytest
uv run ruff check .
uv run mypy .
```

## Conventions

A few non-obvious ones (full list in `.claude/CLAUDE.md`):

- `from __future__ import annotations` at the top of every backend module.
- `pathlib.Path` everywhere, no `os.path`.
- All ingestion caches raw JSON before parsing: `backend/app/ingestion/raw/{source}/{endpoint}/{hash}.json`.
- All LLM calls go through `app/llm/client.py`. All prompts live in `app/llm/prompts.py`. No inline prompt strings, no ad-hoc OpenAI clients.
- All `SelectContent` uses `position="popper" side="bottom" sideOffset={4} avoidCollisions={false}` so the menu doesn't flip upward.
- Dark theme, accent `#00ff88`, `font-mono` for stats. No emojis in code or UI.

### What we don't have

No coordinate or positional data. No heatmaps, no pressing zones, no xG. Everything is aggregated per-match stats from API-Football.

## Branches

No direct pushes to `main`. Feature branches follow `initials/feature-name`. Add Python deps to `backend/pyproject.toml` (uv-managed) — never `pip install` ad-hoc.

---

Hackathon project. Internal use, FC Universitatea Cluj coaching staff.
