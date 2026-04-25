"""Unit tests for the ingestion layer.

Covers:
  - pure parsing helpers (normalize_statistics, _coerce_stat_value, extract_formation)
  - fixture-based league-membership filter (count_team_appearances, select_league_teams)
  - DB upsert helpers (upsert_team, upsert_match_skeleton) using an in-memory SQLite DB

Run with:
    cd backend
    uv run pytest tests/test_ingestion.py -v
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base
from app.ingestion.api_football import (
    _coerce_stat_value,
    extract_formation,
    normalize_statistics,
)
from app.ingestion.upserts import (
    count_team_appearances,
    select_league_teams,
    upsert_match_skeleton,
    upsert_team,
)
from app.models.match import Match  # noqa: F401  (register with Base.metadata)
from app.models.archetype import Archetype  # noqa: F401
from app.models.player import Player  # noqa: F401
from app.models.team import Team


# ---------------------------------------------------------------------------
# Pure parsing helpers
# ---------------------------------------------------------------------------

class TestCoerceStatValue:
    def test_none_stays_none(self) -> None:
        assert _coerce_stat_value(None) is None

    def test_empty_string_becomes_none(self) -> None:
        assert _coerce_stat_value("") is None

    def test_integer_passes_through(self) -> None:
        assert _coerce_stat_value(14) == 14

    def test_float_passes_through(self) -> None:
        assert _coerce_stat_value(1.85) == 1.85

    def test_percentage_string_strips_and_casts(self) -> None:
        assert _coerce_stat_value("55%") == 55
        assert _coerce_stat_value("84%") == 84

    def test_decimal_string_becomes_float(self) -> None:
        assert _coerce_stat_value("1.85") == 1.85

    def test_integer_string_becomes_int(self) -> None:
        assert _coerce_stat_value("42") == 42

    def test_unparseable_string_becomes_none(self) -> None:
        assert _coerce_stat_value("not-a-number") is None

    def test_bool_becomes_int(self) -> None:
        assert _coerce_stat_value(True) == 1
        assert _coerce_stat_value(False) == 0


class TestNormalizeStatistics:
    def test_typical_response(self) -> None:
        raw = [
            {"type": "Ball Possession", "value": "55%"},
            {"type": "Total Shots", "value": 12},
            {"type": "Shots on Goal", "value": 5},
            {"type": "Passes %", "value": "84%"},
            {"type": "Fouls", "value": 10},
        ]
        out = normalize_statistics(raw)
        assert out["ball_possession"] == 55
        assert out["total_shots"] == 12
        assert out["shots_on_goal"] == 5
        assert out["passes_pct"] == 84
        assert out["fouls"] == 10

    def test_none_values_preserved_as_none(self) -> None:
        raw = [{"type": "expected_goals", "value": None}]
        out = normalize_statistics(raw)
        assert out["expected_goals"] is None

    def test_dropped_keys_excluded(self) -> None:
        # goals_prevented is in _DROPPED_STAT_KEYS — API-Football always
        # returns it as None for SuperLiga, so it's filtered out entirely.
        raw = [
            {"type": "expected_goals", "value": 1.5},
            {"type": "goals_prevented", "value": None},
        ]
        out = normalize_statistics(raw)
        assert "goals_prevented" not in out
        assert out["expected_goals"] == 1.5

    def test_empty_type_skipped(self) -> None:
        raw = [{"type": "", "value": 5}, {"type": "Fouls", "value": 10}]
        out = normalize_statistics(raw)
        assert "fouls" in out
        assert "" not in out
        assert len(out) == 1

    def test_empty_input_returns_empty_dict(self) -> None:
        assert normalize_statistics([]) == {}


class TestExtractFormation:
    def _make_entry(self, team_id: int, formation: str) -> dict:
        return {"team": {"id": team_id}, "formation": formation}

    def test_returns_home_formation(self) -> None:
        entries = [self._make_entry(100, "4-3-3"), self._make_entry(200, "3-5-2")]
        assert extract_formation(entries, 100) == "4-3-3"

    def test_returns_away_formation(self) -> None:
        entries = [self._make_entry(100, "4-3-3"), self._make_entry(200, "3-5-2")]
        assert extract_formation(entries, 200) == "3-5-2"

    def test_missing_team_returns_none(self) -> None:
        entries = [self._make_entry(100, "4-3-3")]
        assert extract_formation(entries, 999) is None

    def test_empty_response_returns_none(self) -> None:
        assert extract_formation([], 100) is None


# ---------------------------------------------------------------------------
# League-membership filter (lives in scripts/ingest_season.py)
# ---------------------------------------------------------------------------

def _make_fixture(home_id: int, away_id: int) -> dict:
    return {"teams": {"home": {"id": home_id}, "away": {"id": away_id}}}


class TestLeagueTeamFilter:
    def test_count_team_appearances_counts_home_and_away(self) -> None:
        fixtures = [
            _make_fixture(1, 2),
            _make_fixture(2, 3),
            _make_fixture(1, 3),
        ]
        counts = count_team_appearances(fixtures)
        assert counts == {1: 2, 2: 2, 3: 2}

    def test_select_league_teams_drops_low_appearance_teams(self) -> None:
        # Team 99 only plays 1 fixture — should be excluded
        fixtures = [_make_fixture(1, 2) for _ in range(15)]
        fixtures.append(_make_fixture(1, 99))
        result = select_league_teams(fixtures, min_fixtures=10)
        assert 1 in result
        assert 2 in result
        assert 99 not in result

    def test_select_league_teams_realistic_superliga(self) -> None:
        """Simulate the exact Voluntari / Metaloglobus issue."""
        fixtures: list[dict] = []
        # 16 core teams play 39 fixtures each → mutual double round-robin
        for home in range(1, 17):
            for _ in range(39):
                away = (home % 16) + 1
                fixtures.append(_make_fixture(home, away))
        # 2 outsider teams play only 2 fixtures each (playoff)
        fixtures.extend([_make_fixture(17, 1), _make_fixture(1, 17)])
        fixtures.extend([_make_fixture(18, 2), _make_fixture(2, 18)])

        league = select_league_teams(fixtures, min_fixtures=10)
        assert len(league) == 16
        assert 17 not in league
        assert 18 not in league


# ---------------------------------------------------------------------------
# DB upsert helpers — in-memory SQLite
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()


class TestUpsertTeam:
    @pytest.mark.asyncio
    async def test_insert_new_team(self, session) -> None:
        team = await upsert_team(
            session,
            {"id": 2599, "name": "Universitatea Cluj", "code": "UCL", "logo": "x.png"},
        )
        assert team.id is not None
        assert team.api_football_id == 2599
        assert team.name == "Universitatea Cluj"

    @pytest.mark.asyncio
    async def test_update_existing_team(self, session) -> None:
        await upsert_team(session, {"id": 559, "name": "Old Name"})
        await upsert_team(session, {"id": 559, "name": "FCSB", "logo": "new.png"})
        result = await session.execute(select(Team).where(Team.api_football_id == 559))
        team = result.scalar_one()
        assert team.name == "FCSB"
        assert team.logo_url == "new.png"
        # Only one row — update not duplicate insert
        all_rows = (await session.execute(select(Team))).scalars().all()
        assert len(all_rows) == 1


class TestUpsertMatchSkeleton:
    @pytest.mark.asyncio
    async def test_insert_new_match(self, session) -> None:
        home = await upsert_team(session, {"id": 100, "name": "Home FC"})
        away = await upsert_team(session, {"id": 200, "name": "Away FC"})
        team_map = {100: home.id, 200: away.id}

        fixture = {
            "fixture": {
                "id": 999999,
                "date": "2025-05-10T18:00:00+00:00",
                "venue": {"name": "Test Stadium"},
                "referee": "John Ref",
                "status": {"short": "FT"},
            },
            "league": {"id": 283, "season": 2024},
            "teams": {"home": {"id": 100}, "away": {"id": 200}},
            "goals": {"home": 2, "away": 1},
        }
        match = await upsert_match_skeleton(session, fixture, team_map)
        assert match is not None
        assert match.id == 999999
        assert match.home_score == 2
        assert match.away_score == 1
        assert match.status == "FT"
        assert match.referee_name == "John Ref"
        assert match.formation_home is None  # lineups come later

    @pytest.mark.asyncio
    async def test_skip_when_team_not_in_map(self, session) -> None:
        fixture = {
            "fixture": {"id": 1, "date": "2025-01-01T00:00:00+00:00",
                        "venue": {}, "referee": None, "status": {"short": "NS"}},
            "league": {"id": 283, "season": 2024},
            "teams": {"home": {"id": 9999}, "away": {"id": 8888}},
            "goals": {"home": None, "away": None},
        }
        match = await upsert_match_skeleton(session, fixture, team_id_map={})
        assert match is None
