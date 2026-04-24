# Project Overview — Opponent Dossier

Pre-match scouting tool for FC Universitatea Cluj. The coaching staff selects the next opponent and the system generates a 7-section report powered by API-Football data and an OpenAI LLM.

---

## Folder-by-folder breakdown

### `backend/app/ingestion/`
Fetches raw data from API-Football and saves it to disk as JSON before anything else touches it.

`api_football.py` — the only data client in the project. Every method (fixtures, teams, player stats, standings, H2H, referee) makes an HTTP request, caches the response in `raw/api_football/{endpoint}/{hash}.json`, and returns the raw dict. The cache is the safety net against the 100 req/day free-tier limit — once a fixture is cached, you never pay for it again.

**Ties to product:** Foundation of everything. None of the 7 dossier sections can exist without this data being ingested first. Currently all methods have `TODO` — nothing is implemented yet.

---

### `backend/app/models/`
Defines the SQLite database tables using SQLAlchemy 2.0.

| Model | What it stores |
|---|---|
| `Team` | Every SuperLiga team with their API-Football ID |
| `Player` | Players linked to teams, populated from fixture player stats |
| `Match` | Every played fixture — scores, formations, raw stats JSON per side |
| `Archetype` | KMeans cluster results — name, centroid, list of match IDs |

**Ties to product:** These are the data structures that all 6 analysis modules read from. The `Match.stats_home` / `Match.stats_away` JSON columns are the raw material for every statistic shown in the dossier.

---

### `backend/scripts/`
Two one-time CLI scripts you run before the app starts serving requests.

- `ingest_season.py` — pulls all SuperLiga 2024-25 fixtures from API-Football, upserts Teams and Matches to DB
- `build_archetypes.py` — reads all Match rows, fits KMeans, writes Archetype rows and assigns each match an archetype ID

Run them in order:
```bash
cd backend
uv run python scripts/ingest_season.py
uv run python scripts/build_archetypes.py
```

**Ties to product:** Must be run before the UI works. Offline setup, not real-time. DB upsert logic is currently `TODO`.

---

### `backend/app/analysis/`
Six pure-data modules, one per dossier section. Each queries the DB and returns a typed Pydantic object. No LLM calls here.

| File | Produces | Status |
|---|---|---|
| `form.py` | `FormSection` — last 5/10 results, goal averages | `NotImplementedError` |
| `identity.py` | `IdentitySection` — possession, press intensity, play style | `NotImplementedError` |
| `matchups.py` | `MatchupSection` — KMeans archetype records + FCU prediction | `NotImplementedError` |
| `players.py` | `PlayerCardsSection` — threat and vulnerability cards | `NotImplementedError` |
| `game_state.py` | `GameStateSection` — behaviour when winning/drawing/losing | `NotImplementedError` |
| `referee.py` | `RefereeSection` — cards, fouls, home-factor for assigned ref | `NotImplementedError` |

**Ties to product:** The statistical heart of the dossier. Six modules run in parallel (Stage 1 of the pipeline), then their outputs feed the LLM.

---

### `backend/app/llm/`
The LangChain layer — the only place where OpenAI is called.

- `client.py` — `invoke_structured(system, user, schema)`: builds a `ChatPromptTemplate`, calls `llm.with_structured_output(schema)`, retries on rate limits, logs every call
- `prompts.py` — five `ChatPromptTemplate` constants (FORM, IDENTITY, MATCHUP, PLAYERS, GAMEPLAN), all with `TODO` content
- `orchestrator.py` — the pipeline: **Stage 1** runs all 6 analysis modules concurrently via `RunnableParallel`, **Stage 2** feeds the results into `GAMEPLAN_PROMPT | llm.with_structured_output(GameplanNarrative)`

**Ties to product:** Section 7 (Gameplan Narrative) is the only LLM output. The other 6 sections are deterministic. The orchestrator wires everything together and is what the `/dossier/{team_id}` route calls.

---

### `backend/app/routes/`
Three FastAPI routers.

- `GET /health` — liveness check
- `GET /teams` — returns all teams in DB (powers the frontend dropdown)
- `GET /dossier/{team_id}` — calls `generate_dossier()`, returns the full `DossierResponse`

**Ties to product:** The two endpoints the frontend actually uses.

---

### `backend/app/schemas/`
Pydantic v2 models that define the exact JSON shape of every API response. `dossier.py` contains all 7 section schemas plus the top-level `DossierResponse`.

**Ties to product:** The contract between backend and frontend. `frontend/lib/types.ts` mirrors these exactly — if you change a schema, update both files.

---

### `frontend/`
Next.js 14 App Router UI with two pages and seven section components.

- `app/page.tsx` — landing page with opponent dropdown + "Generate Dossier" button
- `app/dossier/[teamId]/page.tsx` — the main dossier view, server component, fetches from backend
- `components/dossier/` — one component per section (FormPanel, IdentityCard, MatchupIntelligence, PlayerCards, GameStatePanel, RefereeCard, GameplanNarrative)
- `components/charts/RadarFingerprint.tsx` — Recharts radar chart for tactical fingerprint
- `lib/api.ts` — all backend fetch calls
- `lib/types.ts` — TypeScript interfaces matching backend schemas

**Ties to product:** The coach-facing UI. All components receive typed props and are styled with the dark scouting-tool aesthetic (`#0a0e1a` background, `#00ff88` accent).

---

## Current state: what works vs what doesn't

| Layer | Status |
|---|---|
| Project structure, config, DB models | Done |
| API-Football client (caching, rate-limit retry) | Scaffolded — `TODO` on response parsing |
| DB upsert in ingest script | `TODO` |
| All 6 analysis modules | `NotImplementedError` |
| LangChain pipeline / orchestrator | Wired up — `TODO` prompt content |
| Frontend components | Scaffolded — will render once backend returns real data |

---

## Recommended next steps (in order)

### 1. Implement ingestion + DB upsert
**Files:** `backend/scripts/ingest_season.py`, `backend/app/ingestion/api_football.py`

Parse the fixture statistics response, map API-Football stat labels to the `Match.stats_home/away` dict, upsert Teams and Matches. This unlocks everything else — without data in the DB, nothing runs.

### 2. Implement `form.py` and `identity.py`
**Files:** `backend/app/analysis/form.py`, `backend/app/analysis/identity.py`

Simplest modules — only need `Match` rows with stats. Get these working first to validate the full end-to-end request through the pipeline.

### 3. Implement `matchups.py` + `build_archetypes.py`
**Files:** `backend/app/analysis/matchups.py`, `backend/scripts/build_archetypes.py`

The hero feature. Extract the 6-feature vector from match stats, fit KMeans, assign archetypes. This is the demo centrepiece and what `MatchupIntelligence.tsx` renders.

### 4. Implement remaining analysis modules
**Files:** `backend/app/analysis/players.py`, `backend/app/analysis/game_state.py`, `backend/app/analysis/referee.py`

Fills out the rest of the dossier sections.

### 5. Write prompt content in `prompts.py`
**File:** `backend/app/llm/prompts.py`

The `GAMEPLAN_PROMPT` especially. At this point all 6 sections return real data so you can test the full pipeline and tune the prompts.

### 6. Frontend polish
Components are scaffolded but untested with real data. Verify layouts, loading states, and that the `MatchupIntelligence` hero component looks good for the demo.

---

## Quick-start commands

```bash
# Backend
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev

# One-time data setup (run after keys are in .env)
cd backend
uv run python scripts/ingest_season.py
uv run python scripts/build_archetypes.py
```

API keys go in `.env` at the project root (already gitignored):
```
API_FOOTBALL_KEY=your_key_here
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o
```
