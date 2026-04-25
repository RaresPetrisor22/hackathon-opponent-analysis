"""Unit tests for analysis.identity.compute_identity.

Run with:
    cd backend
    uv run pytest tests/test_identity.py -v
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import null, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.analysis.identity import compute_identity
from app.db import Base
from app.models.archetype import Archetype  # noqa: F401
from app.models.match import Match
from app.models.player import Player  # noqa: F401
from app.models.team import Team


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()


async def _make_team(session, api_id: int, name: str) -> Team:
    team = Team(api_football_id=api_id, name=name)
    session.add(team)
    await session.flush()
    return team


async def _make_match(
    session,
    *,
    fixture_id: int,
    home_id: int,
    away_id: int,
    stats_home: dict[str, Any] | None,
    stats_away: dict[str, Any] | None,
    formation_home: str | None = "4-3-3",
    formation_away: str | None = "4-2-3-1",
    date: datetime | None = None,
) -> Match:
    match = Match(
        id=fixture_id,
        season_id=2024,
        league_id=283,
        home_team_id=home_id,
        away_team_id=away_id,
        home_score=0,
        away_score=0,
        date=date or datetime(2025, 1, fixture_id, tzinfo=timezone.utc),
        status="FT",
        stats_home=stats_home,
        stats_away=stats_away,
        formation_home=formation_home,
        formation_away=formation_away,
    )
    session.add(match)
    await session.flush()
    if stats_home is None and stats_away is None:
        await session.execute(
            update(Match)
            .where(Match.id == fixture_id)
            .values(stats_home=null(), stats_away=null())
        )
        await session.flush()
    return match


def _stats(**overrides: Any) -> dict[str, Any]:
    base = {
        "ball_possession": 50,
        "total_shots": 10,
        "shots_on_goal": 4,
        "passes_pct": 75,
        "fouls": 12,
        "yellow_cards": 2,
        "corner_kicks": 5,
    }
    base.update(overrides)
    return base


class TestComputeIdentity:
    @pytest.mark.asyncio
    async def test_empty_db_returns_zeroed_section(self, session) -> None:
        team = await _make_team(session, 100, "Solo FC")
        result = await compute_identity(team.id, session)
        assert result.stats.avg_possession == 0.0
        assert result.stats.avg_shots == 0.0
        assert result.stats.preferred_formation == "unknown"

    @pytest.mark.asyncio
    async def test_averages_home_and_away_stats(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "FCSB")
        await _make_match(
            session,
            fixture_id=1,
            home_id=cluj.id,
            away_id=opp.id,
            stats_home=_stats(ball_possession=60, total_shots=14),
            stats_away=_stats(ball_possession=40),
        )
        await _make_match(
            session,
            fixture_id=2,
            home_id=opp.id,
            away_id=cluj.id,
            stats_home=_stats(ball_possession=55),
            stats_away=_stats(ball_possession=45, total_shots=8),
        )
        result = await compute_identity(cluj.id, session)
        # cluj: home in match1 (60), away in match2 (45) -> avg 52.5
        assert result.stats.avg_possession == 52.5
        # cluj total_shots: 14 (home) + 8 (away) = 22 / 2 = 11
        assert result.stats.avg_shots == 11.0

    @pytest.mark.asyncio
    async def test_skips_none_stat_values(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "FCSB")
        await _make_match(
            session,
            fixture_id=1,
            home_id=cluj.id,
            away_id=opp.id,
            stats_home=_stats(ball_possession=60),
            stats_away=_stats(),
        )
        await _make_match(
            session,
            fixture_id=2,
            home_id=cluj.id,
            away_id=opp.id,
            stats_home=_stats(ball_possession=None, total_shots=20),
            stats_away=_stats(),
        )
        result = await compute_identity(cluj.id, session)
        # ball_possession had only 1 valid sample (60)
        assert result.stats.avg_possession == 60.0
        # total_shots from 10 + 20 = 30/2 = 15
        assert result.stats.avg_shots == 15.0

    @pytest.mark.asyncio
    async def test_preferred_formation_picks_mode(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "FCSB")
        for i, formation in enumerate(["4-3-3", "4-3-3", "4-2-3-1"], start=1):
            await _make_match(
                session,
                fixture_id=i,
                home_id=cluj.id,
                away_id=opp.id,
                stats_home=_stats(),
                stats_away=_stats(),
                formation_home=formation,
            )
        result = await compute_identity(cluj.id, session)
        assert result.stats.preferred_formation == "4-3-3"

    @pytest.mark.asyncio
    async def test_pressing_intensity_high_when_fouls_high(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "FCSB")
        await _make_match(
            session, fixture_id=1, home_id=cluj.id, away_id=opp.id,
            stats_home=_stats(fouls=18), stats_away=_stats(),
        )
        result = await compute_identity(cluj.id, session)
        assert result.pressing_intensity == "high"

    @pytest.mark.asyncio
    async def test_pressing_intensity_low_when_fouls_low(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "FCSB")
        await _make_match(
            session, fixture_id=1, home_id=cluj.id, away_id=opp.id,
            stats_home=_stats(fouls=8), stats_away=_stats(),
        )
        result = await compute_identity(cluj.id, session)
        assert result.pressing_intensity == "low"

    @pytest.mark.asyncio
    async def test_play_style_possession_label(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "FCSB")
        await _make_match(
            session, fixture_id=1, home_id=cluj.id, away_id=opp.id,
            stats_home=_stats(ball_possession=60, passes_pct=85),
            stats_away=_stats(),
        )
        result = await compute_identity(cluj.id, session)
        assert result.play_style == "possession-based build-up"

    @pytest.mark.asyncio
    async def test_play_style_direct_when_low_possession(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "FCSB")
        await _make_match(
            session, fixture_id=1, home_id=cluj.id, away_id=opp.id,
            stats_home=_stats(ball_possession=40),
            stats_away=_stats(),
        )
        result = await compute_identity(cluj.id, session)
        assert result.play_style == "direct / counter-attacking"

    @pytest.mark.asyncio
    async def test_excludes_matches_without_stats(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "FCSB")
        await _make_match(
            session, fixture_id=1, home_id=cluj.id, away_id=opp.id,
            stats_home=_stats(ball_possession=60),
            stats_away=_stats(),
        )
        await _make_match(
            session, fixture_id=2, home_id=cluj.id, away_id=opp.id,
            stats_home=None, stats_away=None,
        )
        result = await compute_identity(cluj.id, session)
        # Only the with-stats match contributes
        assert result.stats.avg_possession == 60.0

    @pytest.mark.asyncio
    async def test_unrelated_matches_ignored(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        a = await _make_team(session, 2, "Team A")
        b = await _make_team(session, 3, "Team B")
        await _make_match(
            session, fixture_id=1, home_id=a.id, away_id=b.id,
            stats_home=_stats(ball_possession=99), stats_away=_stats(),
        )
        result = await compute_identity(cluj.id, session)
        assert result.stats.avg_possession == 0.0
