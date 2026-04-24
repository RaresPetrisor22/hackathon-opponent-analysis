# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Opponent Dossier is a pre-match scouting tool for FC Universitatea Cluj (Romanian SuperLiga). The coaching staff selects the next opponent and the system generates a seven-section report covering form, tactical identity, archetype-based matchup intelligence, player cards, game-state patterns, referee context, and an LLM-written gameplan. Data comes from API-Football v3 (cached to disk) and Wyscout JSON exports. The backend is FastAPI + SQLite; the frontend is Next.js 14.

## Coding Conventions

### Python (backend)
- Use `pathlib.Path` everywhere — never `os.path`.
- Type-hint every function signature, including return types. Use `from __future__ import annotations` at the top of files where needed.
- All API input/output uses Pydantic v2 models defined in `backend/app/schemas/`.
- SQLAlchemy models use the 2.0 `Mapped[]` / `mapped_column()` style — no legacy `Column()`.
- All ingestion methods must cache the raw JSON response to disk before parsing. Cache path: `backend/app/ingestion/raw/{source}/{endpoint}/{params_hash}.json`.
- All LLM calls go through `backend/app/llm/client.py` — never call the OpenAI/Anthropic SDK directly from analysis modules or routes.
- All prompt strings live in `backend/app/llm/prompts.py` as module-level string constants — never inline prompt strings elsewhere.
- Use `async`/`await` throughout the backend (httpx, SQLAlchemy async session, FastAPI async routes).

### TypeScript (frontend)
- Use shadcn/ui for every primitive: Button, Card, Select, Badge, Skeleton, etc. Do not build custom button/input/card components.
- All types mirror the backend Pydantic schemas and live in `frontend/lib/types.ts`.
- All backend fetch calls go through `frontend/lib/api.ts`.
- Recharts for all data visualisations.

## What We Do NOT Have

No coordinate data. No heatmaps. No pressing zones. Everything is aggregated per-match stats. Do not suggest or scaffold any spatial / positional feature.

## Architecture Decisions

- The dossier orchestrator (`backend/app/llm/orchestrator.py`) runs all deterministic analysis modules first (in parallel), then passes structured results to the LLM for narrative synthesis. Never run LLM calls before the data modules complete.
- Romanian SuperLiga league ID for API-Football: **283** (2024-25 season). Confirm at runtime and store in config if it changes.
- SQLite is intentional — no Docker, no Postgres, runs offline at the venue.
- `uv` manages Python deps. Always edit `backend/pyproject.toml`; never `pip install` ad-hoc.

## Design Rules

- Dark theme: background `#0a0e1a`, accent `#00ff88`.
- No emoji anywhere in the UI or in code comments.
- Stats use `font-mono`; narrative text uses Inter.
- No "AI-powered" badges, no chat bubbles, no SaaS-style marketing copy in the UI.

## When in Doubt

Refer to the top-level README.md for architecture and the seven dossier section names/shapes.
