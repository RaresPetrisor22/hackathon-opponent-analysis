"""Unit tests for analysis.referee.compute_referee_context.

Run with:
    cd backend
    uv run pytest tests/test_referee.py -v
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import null, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.analysis.referee import compute_referee_context
from app.db import Base
from app.models.archetype import Archetype  # noqa: F401
from app.models.match import Match
from app.models.player import Player  # noqa: F401
from app.models.team import Team


LEAGUE = 283
SEASON = 2024


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
    t = Team(api_football_id=api_id, name=name)
    session.add(t)
    await session.flush()
    return t


def _stats(yellows: float | None = 2, reds: float | None = 0, fouls: float | None = 12) -> dict[str, Any]:
    return {"yellow_cards": yellows, "red_cards": reds, "fouls": fouls}


async def _make_match(
    session,
    *,
    fixture_id: int,
    home_id: int,
    away_id: int,
    referee: str | None,
    home_score: int = 1,
    away_score: int = 1,
    stats_home: dict | None = None,
    stats_away: dict | None = None,
    league_id: int = LEAGUE,
    season_id: int = SEASON,
    has_stats: bool = True,
) -> Match:
    m = Match(
        id=fixture_id,
        season_id=season_id,
        league_id=league_id,
        home_team_id=home_id,
        away_team_id=away_id,
        home_score=home_score,
        away_score=away_score,
        date=datetime(2025, 1, fixture_id, tzinfo=timezone.utc),
        status="FT",
        referee_name=referee,
        stats_home=stats_home if has_stats else None,
        stats_away=stats_away if has_stats else None,
    )
    session.add(m)
    await session.flush()
    if not has_stats:
        await session.execute(
            update(Match).where(Match.id == fixture_id).values(
                stats_home=null(), stats_away=null()
            )
        )
        await session.flush()
    return m


class TestComputeRefereeContext:
    @pytest.mark.asyncio
    async def test_none_referee_returns_unassigned_stub(self, session) -> None:
        r = await compute_referee_context(None, LEAGUE, SEASON, session)
        assert r.referee_name is None
        assert r.total_matches == 0
        assert r.home_advantage_factor is None
        assert "No referee assigned" in r.notes

    @pytest.mark.asyncio
    async def test_unknown_referee_returns_no_history_stub(self, session) -> None:
        r = await compute_referee_context("Nobody", LEAGUE, SEASON, session)
        assert r.referee_name == "Nobody"
        assert r.total_matches == 0
        assert "No prior matches" in r.notes

    @pytest.mark.asyncio
    async def test_aggregates_cards_and_fouls_across_both_teams(self, session) -> None:
        a = await _make_team(session, 1, "A")
        b = await _make_team(session, 2, "B")
        await _make_match(
            session, fixture_id=1, home_id=a.id, away_id=b.id, referee="Ref X",
            stats_home=_stats(yellows=3, reds=1, fouls=14),
            stats_away=_stats(yellows=2, reds=0, fouls=10),
        )
        r = await compute_referee_context("Ref X", LEAGUE, SEASON, session)
        assert r.total_matches == 1
        # both teams summed: 3+2=5 yellows, 1+0=1 red, 14+10=24 fouls
        assert r.avg_yellow_cards == 5.0
        assert r.avg_red_cards == 1.0
        assert r.avg_fouls_called == 24.0

    @pytest.mark.asyncio
    async def test_averages_over_multiple_matches(self, session) -> None:
        a = await _make_team(session, 1, "A")
        b = await _make_team(session, 2, "B")
        await _make_match(
            session, fixture_id=1, home_id=a.id, away_id=b.id, referee="Ref X",
            stats_home=_stats(yellows=4), stats_away=_stats(yellows=2),
        )
        await _make_match(
            session, fixture_id=2, home_id=a.id, away_id=b.id, referee="Ref X",
            stats_home=_stats(yellows=2), stats_away=_stats(yellows=0),
        )
        r = await compute_referee_context("Ref X", LEAGUE, SEASON, session)
        # match1 total=6, match2 total=2; avg = (6+2)/2 = 4
        assert r.total_matches == 2
        assert r.avg_yellow_cards == 4.0

    @pytest.mark.asyncio
    async def test_handles_none_stat_values(self, session) -> None:
        a = await _make_team(session, 1, "A")
        b = await _make_team(session, 2, "B")
        await _make_match(
            session, fixture_id=1, home_id=a.id, away_id=b.id, referee="Ref X",
            stats_home={"yellow_cards": None, "red_cards": None, "fouls": 10},
            stats_away=_stats(yellows=3, reds=0, fouls=8),
        )
        r = await compute_referee_context("Ref X", LEAGUE, SEASON, session)
        # Nones treated as 0; only the away yellow counts -> 3.0
        assert r.avg_yellow_cards == 3.0
        assert r.avg_red_cards == 0.0
        assert r.avg_fouls_called == 18.0

    @pytest.mark.asyncio
    async def test_home_advantage_factor(self, session) -> None:
        a = await _make_team(session, 1, "A")
        b = await _make_team(session, 2, "B")
        # 3 home wins, 1 away win, 1 draw
        for fid, hs, as_ in [(1, 2, 0), (2, 3, 1), (3, 1, 0), (4, 0, 2), (5, 1, 1)]:
            await _make_match(
                session, fixture_id=fid, home_id=a.id, away_id=b.id,
                referee="Ref X", home_score=hs, away_score=as_,
                stats_home=_stats(), stats_away=_stats(),
            )
        r = await compute_referee_context("Ref X", LEAGUE, SEASON, session)
        assert r.total_matches == 5
        assert r.home_advantage_factor == 0.6

    @pytest.mark.asyncio
    async def test_other_referees_ignored(self, session) -> None:
        a = await _make_team(session, 1, "A")
        b = await _make_team(session, 2, "B")
        await _make_match(
            session, fixture_id=1, home_id=a.id, away_id=b.id, referee="Ref X",
            stats_home=_stats(), stats_away=_stats(),
        )
        await _make_match(
            session, fixture_id=2, home_id=a.id, away_id=b.id, referee="Ref Y",
            stats_home=_stats(yellows=10), stats_away=_stats(yellows=10),
        )
        r = await compute_referee_context("Ref X", LEAGUE, SEASON, session)
        assert r.total_matches == 1

    @pytest.mark.asyncio
    async def test_other_seasons_ignored(self, session) -> None:
        a = await _make_team(session, 1, "A")
        b = await _make_team(session, 2, "B")
        await _make_match(
            session, fixture_id=1, home_id=a.id, away_id=b.id, referee="Ref X",
            stats_home=_stats(), stats_away=_stats(),
        )
        await _make_match(
            session, fixture_id=2, home_id=a.id, away_id=b.id, referee="Ref X",
            season_id=2023, stats_home=_stats(), stats_away=_stats(),
        )
        r = await compute_referee_context("Ref X", LEAGUE, SEASON, session)
        assert r.total_matches == 1

    @pytest.mark.asyncio
    async def test_other_leagues_ignored(self, session) -> None:
        a = await _make_team(session, 1, "A")
        b = await _make_team(session, 2, "B")
        await _make_match(
            session, fixture_id=1, home_id=a.id, away_id=b.id, referee="Ref X",
            stats_home=_stats(), stats_away=_stats(),
        )
        await _make_match(
            session, fixture_id=2, home_id=a.id, away_id=b.id, referee="Ref X",
            league_id=999, stats_home=_stats(), stats_away=_stats(),
        )
        r = await compute_referee_context("Ref X", LEAGUE, SEASON, session)
        assert r.total_matches == 1

    @pytest.mark.asyncio
    async def test_excludes_matches_without_stats(self, session) -> None:
        a = await _make_team(session, 1, "A")
        b = await _make_team(session, 2, "B")
        await _make_match(
            session, fixture_id=1, home_id=a.id, away_id=b.id, referee="Ref X",
            stats_home=_stats(yellows=3), stats_away=_stats(yellows=1),
        )
        await _make_match(
            session, fixture_id=2, home_id=a.id, away_id=b.id, referee="Ref X",
            has_stats=False,
        )
        r = await compute_referee_context("Ref X", LEAGUE, SEASON, session)
        # Only the with-stats match contributes
        assert r.total_matches == 1
        assert r.avg_yellow_cards == 4.0

    @pytest.mark.asyncio
    async def test_notes_include_card_label(self, session) -> None:
        a = await _make_team(session, 1, "A")
        b = await _make_team(session, 2, "B")
        await _make_match(
            session, fixture_id=1, home_id=a.id, away_id=b.id, referee="Strict",
            stats_home=_stats(yellows=4), stats_away=_stats(yellows=4),
        )
        r = await compute_referee_context("Strict", LEAGUE, SEASON, session)
        assert "card-heavy" in r.notes

        await _make_match(
            session, fixture_id=2, home_id=a.id, away_id=b.id, referee="Lenient",
            stats_home=_stats(yellows=1), stats_away=_stats(yellows=1),
        )
        r2 = await compute_referee_context("Lenient", LEAGUE, SEASON, session)
        assert "lenient" in r2.notes
