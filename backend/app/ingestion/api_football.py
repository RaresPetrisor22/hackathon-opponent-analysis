from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import httpx

from app.config import settings

CACHE_ROOT = Path(__file__).parent / "raw" / "api_football"


class ApiFootballClient:
    """Async client for the API-Football v3 REST API.

    All responses are cached to disk at CACHE_ROOT/{endpoint}/{params_hash}.json
    before parsing. On subsequent calls the cached file is returned directly,
    avoiding rate-limit consumption.

    The free tier allows 100 requests/day. Use the ingest scripts to bulk-pull
    in a single session; the UI should never call this client directly.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._key = api_key or settings.api_football_key
        self._base = settings.api_football_base_url
        self._headers = {"x-apisports-key": self._key}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cache_path(self, endpoint: str, params: dict[str, Any]) -> Path:
        params_hash = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()
        path = CACHE_ROOT / endpoint.strip("/").replace("/", "_") / f"{params_hash}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    # Pro plan allows 300 requests/minute (5/sec). Stay slightly under that.
    _THROTTLE_SECONDS = 0.25
    _BACKOFF_SECONDS = [2, 5, 10, 30, 60]

    async def _get(
        self,
        endpoint: str,
        params: dict[str, Any],
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Fetch endpoint, returning cached result if available."""
        cache_file = self._cache_path(endpoint, params)
        if cache_file.exists() and not force_refresh:
            return json.loads(cache_file.read_text(encoding="utf-8"))

        async with httpx.AsyncClient(headers=self._headers, timeout=30) as client:
            for attempt, delay in enumerate([0, *self._BACKOFF_SECONDS]):
                if delay:
                    await asyncio.sleep(delay)
                resp = await client.get(f"{self._base}/{endpoint.lstrip('/')}", params=params)
                if resp.status_code == 429:
                    continue
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                cache_file.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                # Proactive throttle to stay within rate limit
                await asyncio.sleep(self._THROTTLE_SECONDS)
                return data
        raise RuntimeError(f"Rate limited after retries: {endpoint}")

    # ------------------------------------------------------------------
    # Public API methods — all return raw API-Football response dicts
    # ------------------------------------------------------------------

    async def get_leagues(self, country: str = "Romania") -> dict[str, Any]:
        """Fetch all leagues for a country."""
        # TODO: implement
        return await self._get("leagues", {"country": country})

    async def get_teams(self, league_id: int, season: int) -> dict[str, Any]:
        """Fetch all teams in a league/season."""
        # TODO: implement
        return await self._get("teams", {"league": league_id, "season": season})

    async def get_fixtures(self, league_id: int, season: int) -> dict[str, Any]:
        """Fetch all fixtures for a league/season."""
        # TODO: implement
        return await self._get("fixtures", {"league": league_id, "season": season})

    async def get_fixture_events(self, fixture_id: int) -> dict[str, Any]:
        """Fetch goal/card/sub events for a single fixture."""
        # TODO: implement
        return await self._get("fixtures/events", {"fixture": fixture_id})

    async def get_fixture_statistics(self, fixture_id: int) -> dict[str, Any]:
        """Fetch aggregated team statistics for a single fixture."""
        return await self._get("fixtures/statistics", {"fixture": fixture_id})

    async def get_fixture_lineups(self, fixture_id: int) -> dict[str, Any]:
        """Fetch starting lineups + formation for a single fixture."""
        return await self._get("fixtures/lineups", {"fixture": fixture_id})

    async def get_fixture_players(self, fixture_id: int) -> dict[str, Any]:
        """Fetch per-player aggregated statistics for a single fixture."""
        # TODO: implement
        return await self._get("fixtures/players", {"fixture": fixture_id})

    async def get_injuries(self, team_id: int, season: int) -> dict[str, Any]:
        """Fetch injury list for a team in a season."""
        # TODO: implement
        return await self._get("injuries", {"team": team_id, "season": season})

    async def get_standings(self, league_id: int, season: int) -> dict[str, Any]:
        """Fetch league standings table."""
        # TODO: implement
        return await self._get("standings", {"league": league_id, "season": season})

    async def get_head_to_head(self, team_a: int, team_b: int) -> dict[str, Any]:
        """Fetch H2H results between two teams."""
        # TODO: implement
        return await self._get("fixtures/headtohead", {"h2h": f"{team_a}-{team_b}"})

    async def get_referee_fixtures(
        self, referee_name: str, league_id: int, season: int
    ) -> dict[str, Any]:
        """Fetch all fixtures officiated by a referee in a season."""
        return await self._get(
            "fixtures",
            {"referee": referee_name, "league": league_id, "season": season},
        )


# ---------------------------------------------------------------------------
# Parsing helpers (pure functions — no I/O, easy to unit-test)
# ---------------------------------------------------------------------------

# Keys API-Football returns but that are unusable for SuperLiga (always None).
# Dropped during normalisation to keep stats dicts clean.
_DROPPED_STAT_KEYS = frozenset({"goals_prevented"})


def normalize_statistics(raw_stats: list[dict[str, Any]]) -> dict[str, float | int | None]:
    """Convert API-Football's list-of-dicts stats into a flat snake_case dict.

    Input  : [{"type": "Ball Possession", "value": "55%"}, ...]
    Output : {"ball_possession": 55.0, ...}

    String percentages are stripped and cast to float. Numeric strings are
    cast to int or float. None / missing values stay as None. Keys in
    _DROPPED_STAT_KEYS are excluded (never populated for SuperLiga).
    """
    out: dict[str, float | int | None] = {}
    for entry in raw_stats:
        raw_type = entry.get("type", "")
        if not raw_type:
            continue
        key = raw_type.strip().lower().replace(" ", "_").replace("%", "pct").replace("__", "_")
        if key in _DROPPED_STAT_KEYS:
            continue
        value = entry.get("value")
        out[key] = _coerce_stat_value(value)
    return out


def _coerce_stat_value(value: Any) -> float | int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        v = value.strip().rstrip("%")
        try:
            if "." in v:
                return float(v)
            return int(v)
        except ValueError:
            try:
                return float(v)
            except ValueError:
                return None
    return None


def extract_formation(lineups_response: list[dict[str, Any]], team_id: int) -> str | None:
    """From /fixtures/lineups response list, find the formation for a team."""
    for entry in lineups_response:
        if entry.get("team", {}).get("id") == team_id:
            return entry.get("formation")
    return None
