# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Opponent Dossier is a pre-match scouting tool for FC Universitatea Cluj (Romanian SuperLiga). The coaching staff selects the next opponent and the system generates a seven-section report: form, tactical identity, archetype-based matchup intelligence, player cards, game-state patterns, referee context, and an LLM-written gameplan. The archetype-based matchup intelligence is the core feature — prioritise and highlight it accordingly. Data comes exclusively from API-Football v3 (cached to disk). The backend is FastAPI + SQLite (async); the frontend is Next.js 14 (App Router).

## Repository Layout

- `backend/app/` — FastAPI app
  - `routes/` — `health`, `teams`, `dossier`, `referees` (mounted in `main.py`)
  - `schemas/` — Pydantic v2 request/response models (`common.py`, `dossier.py`)
  - `models/` — SQLAlchemy 2.0 ORM (`team`, `match`, `player`, `referee`, `standings`, `archetype`)
  - `ingestion/` — `api_football.py` (fetch + cache), `upserts.py`, `raw/` cache tree
  - `analysis/` — six deterministic modules: `form`, `identity`, `matchups`, `players`, `game_state`, `referee`
  - `llm/` — `client.py` (single LLM gateway), `prompts.py` (all `ChatPromptTemplate`s), `orchestrator.py` (LangChain pipeline)
  - `mock.py` — demo/stub data fallback
- `frontend/` — Next.js 14
  - `app/page.tsx` — home page with opponent selector
  - `app/dossier/` — dossier page route
  - `components/dossier/` — one panel per section (`FormPanel`, `IdentityCard`, `MatchupIntelligence`, `PlayerCards`, `GameStatePanel`, `RefereeCard`, `GameplanNarrative`, `PrintButton`)
  - `components/charts/` — Recharts wrappers (`RadarFingerprint`)
  - `components/ui/` — shadcn primitives currently in use: `badge`, `button`, `select`, `separator`
  - `lib/` — `api.ts`, `types.ts`, `utils.ts`

## Coding Conventions

### Python (backend)

- Put `from __future__ import annotations` at the top of every backend module — this is the project default, not conditional.
- Use `pathlib.Path` everywhere — never `os.path`.
- Type-hint every function signature, including return types.
- All API input/output uses Pydantic v2 models defined in `backend/app/schemas/`.
- SQLAlchemy models use the 2.0 `Mapped[]` / `mapped_column()` style — no legacy `Column()`. The base class is `app.db.Base`.
- All ingestion methods must cache the raw JSON response to disk before parsing. Cache path: `backend/app/ingestion/raw/{source}/{endpoint}/{params_hash}.json` (e.g. `raw/api_football/fixtures_statistics/...`).
- All LLM calls go through `backend/app/llm/client.py` (`invoke_structured`) — never instantiate `ChatOpenAI` or call the OpenAI SDK directly from analysis modules or routes.
- All prompt templates live in `backend/app/llm/prompts.py` as `ChatPromptTemplate` constants — never inline prompt strings elsewhere.
- Use `async`/`await` throughout (httpx, SQLAlchemy async session via `get_session`, FastAPI async routes).
- Respect the existing LLM retry policy in `client.py` (rate-limit retries at 2s / 8s / 30s). Do not add ad-hoc retry loops elsewhere.

### TypeScript (frontend)

- Use shadcn/ui for primitives that already exist in `components/ui/` (`Button`, `Select`, `Badge`, `Separator`). For primitives not yet generated (e.g. Card, Skeleton, Tabs), add them via the shadcn CLI before use rather than hand-rolling — do not build custom button/input/select components from scratch.
- All types mirror the backend Pydantic schemas and live in `frontend/lib/types.ts`.
- All backend fetch calls go through `frontend/lib/api.ts`.
- Recharts for all data visualisations.
- Icons via `lucide-react`. Class merging via `clsx` + `tailwind-merge` (helpers in `lib/utils.ts`).

## What We Do NOT Have

No coordinate data. No heatmaps. No pressing zones. Everything is aggregated per-match stats. Do not suggest or scaffold any spatial / positional feature.

## Architecture Decisions

- The dossier orchestrator (`backend/app/llm/orchestrator.py`) is a two-stage LangChain pipeline:
  - **Stage 1 — parallel analysis**: `RunnableParallel` of `RunnableLambda`s wrapping the six analysis modules (`form`, `identity`, `matchups`, `players`, `game_state`, `referee`). Pure DB reads, no LLM calls.
  - **Stage 2 — gameplan synthesis**: a single chain `GAMEPLAN_PROMPT | llm.with_structured_output(GameplanNarrative)` consumes all six section outputs serialised as JSON. This is the only LLM call in the pipeline.
  - Stage 2 never starts before Stage 1 completes. New analysis modules go into Stage 1's `RunnableParallel`; new LLM features either reuse the gameplan chain or use `client.invoke_structured` with a schema.
- Archetype-based matchup intelligence is the core feature. `models/archetype.py` is a first-class entity; `analysis/matchups.py` predicts the matchup against `settings.fcu_team_id`. The four archetype labels are: "Dominant Possession Elite", "Defensive / Low Output", "Long-Range Specialists", and "Counter-Attacking Pressing Side".
- Romanian SuperLiga league ID for API-Football: **283**, season **2024** (see `app/config.py` — `superliga_league_id`, `superliga_season`). FCU team ID: **2599** (`fcu_team_id`). Confirm at runtime if upstream data changes.
- Default LLM: `gpt-4o` (`settings.openai_model`), temperature 0.3. Override via env, not in code.
- SQLite is intentional — no Docker, no Postgres. `database_url` defaults to `sqlite+aiosqlite:///./data/app.db`. `init_db()` runs `create_all` plus idempotent `ALTER TABLE` shims for late-added match columns.
- `mock.py` provides stub/demo data — keep it in sync when ingestion shapes change.
- `uv` manages Python deps. Always edit `backend/pyproject.toml`; never `pip install` ad-hoc.

## Testing

- Tests live in `backend/tests/`. Tooling: `pytest` + `pytest-asyncio` (dev deps in `pyproject.toml`).
- Lint/type-check via `ruff` and `mypy` (strict). Line length 100, target `py311`.

## Design Rules

- Dark theme: background `#0a0e1a`, accent `#00ff88`.
- No emoji anywhere in the UI or in code comments.
- Stats use `font-mono`; narrative text uses Inter.
- No "AI-powered" badges, no chat bubbles, no SaaS-style marketing copy in the UI.

## Referee Endpoints

Two dedicated endpoints live in `backend/app/routes/referees.py` (mounted at `/referees`):
- `GET /referees` — returns a sorted list of distinct referee names from completed SuperLiga 2024 matches.
- `GET /referees/stats?name=...` — returns a full `RefereeSection` for the named referee, reusing `analysis/referee.py`.

`RefereeCard` is a `"use client"` component with a live dropdown; selecting a referee fetches their stats and swaps the stat boxes. The assigned referee (from the dossier) is highlighted with an "assigned" badge.

## Select Dropdown Behaviour

All `SelectContent` instances must use `position="popper" side="bottom" sideOffset={4} avoidCollisions={false}` to prevent Radix UI from flipping the menu upward on smaller screens.

## PDF Export

`window.print()` is used for PDF export. Print styles live in `app/globals.css`. Outer layout grids use Tailwind's `print:grid-cols-1` variant to collapse to single-column — do **not** use `.grid { display: block }` as it breaks inner stat grids. All elements carry `* { print-color-adjust: exact }` to preserve dark backgrounds and accent colours.

## When in Doubt

Refer to the top-level `README.md` for architecture and the seven dossier section names/shapes, and to `backend/app/schemas/dossier.py` for the canonical section contracts.
