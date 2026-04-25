"""Unit tests for analysis.form.compute_form.

Run with:
    cd backend
    uv run pytest tests/test_form.py -v
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import null, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.analysis.form import compute_form
from app.db import Base
from app.models.archetype import Archetype  # noqa: F401  (register with metadata)
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
    home_score: int | None,
    away_score: int | None,
    date: datetime,
    has_stats: bool = True,
) -> Match:
    match = Match(
        id=fixture_id,
        season_id=2024,
        league_id=283,
        home_team_id=home_id,
        away_team_id=away_id,
        home_score=home_score,
        away_score=away_score,
        date=date,
        status="FT",
        stats_home={"ball_possession": 50} if has_stats else None,
        stats_away={"ball_possession": 50} if has_stats else None,
    )
    session.add(match)
    await session.flush()
    if not has_stats:
        # SQLAlchemy JSON columns default to none_as_null=False, so Python
        # None is stored as JSON null (not SQL NULL). Match.complete() uses
        # `IS NOT NULL` which would match JSON null. Force a real SQL NULL
        # so the filter behaves the way the docstring promises.
        await session.execute(
            update(Match)
            .where(Match.id == fixture_id)
            .values(stats_home=null(), stats_away=null())
        )
        await session.flush()
    return match


class TestComputeForm:
    @pytest.mark.asyncio
    async def test_empty_db_returns_empty_form(self, session) -> None:
        team = await _make_team(session, 100, "Solo FC")
        result = await compute_form(team.id, session)
        assert result.last_5 == []
        assert result.last_10 == []
        assert result.wins_last5 == 0
        assert result.draws_last5 == 0
        assert result.losses_last5 == 0
        assert result.goals_scored_avg == 0.0
        assert result.goals_conceded_avg == 0.0
        assert result.form_string == ""

    @pytest.mark.asyncio
    async def test_home_win_recorded_correctly(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "FCSB")
        await _make_match(
            session,
            fixture_id=1,
            home_id=cluj.id,
            away_id=opp.id,
            home_score=3,
            away_score=1,
            date=datetime(2025, 4, 20, tzinfo=timezone.utc),
        )
        result = await compute_form(cluj.id, session)
        assert len(result.last_5) == 1
        entry = result.last_5[0]
        assert entry.opponent == "FCSB"
        assert entry.home_away == "H"
        assert entry.goals_for == 3
        assert entry.goals_against == 1
        assert entry.result == "W"
        assert result.wins_last5 == 1
        assert result.form_string == "W"

    @pytest.mark.asyncio
    async def test_away_loss_flips_perspective(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "Rapid")
        await _make_match(
            session,
            fixture_id=1,
            home_id=opp.id,
            away_id=cluj.id,
            home_score=2,
            away_score=0,
            date=datetime(2025, 4, 20, tzinfo=timezone.utc),
        )
        result = await compute_form(cluj.id, session)
        entry = result.last_5[0]
        assert entry.opponent == "Rapid"
        assert entry.home_away == "A"
        assert entry.goals_for == 0
        assert entry.goals_against == 2
        assert entry.result == "L"
        assert result.losses_last5 == 1

    @pytest.mark.asyncio
    async def test_draw_classified(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "Hermannstadt")
        await _make_match(
            session,
            fixture_id=1,
            home_id=cluj.id,
            away_id=opp.id,
            home_score=1,
            away_score=1,
            date=datetime(2025, 4, 20, tzinfo=timezone.utc),
        )
        result = await compute_form(cluj.id, session)
        assert result.last_5[0].result == "D"
        assert result.draws_last5 == 1

    @pytest.mark.asyncio
    async def test_orders_descending_by_date(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "Sepsi")
        # Insert out of order
        await _make_match(
            session, fixture_id=1, home_id=cluj.id, away_id=opp.id,
            home_score=1, away_score=0,
            date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        await _make_match(
            session, fixture_id=2, home_id=cluj.id, away_id=opp.id,
            home_score=0, away_score=2,
            date=datetime(2025, 4, 1, tzinfo=timezone.utc),
        )
        await _make_match(
            session, fixture_id=3, home_id=cluj.id, away_id=opp.id,
            home_score=2, away_score=2,
            date=datetime(2025, 2, 15, tzinfo=timezone.utc),
        )
        result = await compute_form(cluj.id, session)
        # Most recent first in last_5
        assert [e.date for e in result.last_5] == [
            "2025-04-01",
            "2025-02-15",
            "2025-01-01",
        ]
        # form_string is reversed -> chronological (oldest -> newest)
        # results in date order: W (Jan), D (Feb), L (Apr)
        assert result.form_string == "WDL"

    @pytest.mark.asyncio
    async def test_last5_and_last10_split(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "Farul")
        for i in range(12):
            await _make_match(
                session,
                fixture_id=100 + i,
                home_id=cluj.id,
                away_id=opp.id,
                home_score=2,
                away_score=1,
                date=datetime(2025, 1, 1 + i, tzinfo=timezone.utc),
            )
        result = await compute_form(cluj.id, session)
        assert len(result.last_5) == 5
        assert len(result.last_10) == 10
        assert result.wins_last5 == 5
        assert result.goals_scored_avg == 2.0
        assert result.goals_conceded_avg == 1.0

    @pytest.mark.asyncio
    async def test_excludes_matches_without_stats(self, session) -> None:
        """Match.complete() filter: matches with stats_home=None are skipped."""
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "Petrolul")
        await _make_match(
            session, fixture_id=1, home_id=cluj.id, away_id=opp.id,
            home_score=3, away_score=0,
            date=datetime(2025, 4, 20, tzinfo=timezone.utc),
            has_stats=True,
        )
        await _make_match(
            session, fixture_id=2, home_id=cluj.id, away_id=opp.id,
            home_score=9, away_score=9,
            date=datetime(2025, 4, 25, tzinfo=timezone.utc),
            has_stats=False,
        )
        result = await compute_form(cluj.id, session)
        assert len(result.last_5) == 1
        assert result.last_5[0].goals_for == 3  # the with-stats match
        assert result.wins_last5 == 1

    @pytest.mark.asyncio
    async def test_unrelated_team_matches_ignored(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        a = await _make_team(session, 2, "Team A")
        b = await _make_team(session, 3, "Team B")
        # match between unrelated teams
        await _make_match(
            session, fixture_id=1, home_id=a.id, away_id=b.id,
            home_score=3, away_score=0,
            date=datetime(2025, 4, 20, tzinfo=timezone.utc),
        )
        result = await compute_form(cluj.id, session)
        assert result.last_5 == []
