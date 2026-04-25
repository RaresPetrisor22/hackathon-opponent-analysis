"""Unit tests for analysis.game_state.compute_game_state.

Run with:
    cd backend
    uv run pytest tests/test_game_state.py -v
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.analysis.game_state import compute_game_state
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


def _goal(api_team_id: int, minute: int, *, own_goal: bool = False) -> dict:
    return {
        "time": {"elapsed": minute, "extra": None},
        "team": {"id": api_team_id, "name": "T"},
        "player": {"id": 1, "name": "P"},
        "type": "Goal",
        "detail": "Own Goal" if own_goal else "Normal Goal",
    }


async def _make_match(
    session,
    *,
    fixture_id: int,
    home_id: int,
    away_id: int,
    events: list[dict],
    home_score: int = 0,
    away_score: int = 0,
    date: datetime | None = None,
) -> Match:
    match = Match(
        id=fixture_id,
        season_id=2024,
        league_id=283,
        home_team_id=home_id,
        away_team_id=away_id,
        home_score=home_score,
        away_score=away_score,
        date=date or datetime(2025, 1, fixture_id, tzinfo=timezone.utc),
        status="FT",
        stats_home={"ball_possession": 50},
        stats_away={"ball_possession": 50},
        events=events,
    )
    session.add(match)
    await session.flush()
    return match


class TestComputeGameState:
    @pytest.mark.asyncio
    async def test_empty_db_returns_zeroed_records(self, session) -> None:
        team = await _make_team(session, 100, "Solo FC")
        result = await compute_game_state(team.id, session)
        assert {r.state for r in result.records} == {"winning", "drawing", "losing"}
        for r in result.records:
            assert r.matches == 0
            assert r.avg_goals_for == 0.0
            assert r.avg_goals_against == 0.0

    @pytest.mark.asyncio
    async def test_first_goal_attributed_to_drawing(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "FCSB")
        # Cluj scores at minute 10 from 0-0 -> goal counts in "drawing"
        await _make_match(
            session, fixture_id=1, home_id=cluj.id, away_id=opp.id,
            events=[_goal(cluj.api_football_id, 10)],
        )
        result = await compute_game_state(cluj.id, session)
        by_state = {r.state: r for r in result.records}
        assert by_state["drawing"].avg_goals_for == 1.0
        assert by_state["drawing"].matches == 1

    @pytest.mark.asyncio
    async def test_second_goal_attributed_to_winning(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "FCSB")
        # Cluj scores twice — second goal occurs while already winning 1-0
        await _make_match(
            session, fixture_id=1, home_id=cluj.id, away_id=opp.id,
            events=[
                _goal(cluj.api_football_id, 10),
                _goal(cluj.api_football_id, 50),
            ],
        )
        result = await compute_game_state(cluj.id, session)
        by_state = {r.state: r for r in result.records}
        assert by_state["drawing"].avg_goals_for == 1.0
        assert by_state["winning"].avg_goals_for == 1.0
        assert by_state["winning"].matches == 1

    @pytest.mark.asyncio
    async def test_goal_against_while_drawing_then_losing(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "FCSB")
        # Opp scores twice; first while 0-0, second while cluj already losing
        await _make_match(
            session, fixture_id=1, home_id=cluj.id, away_id=opp.id,
            events=[
                _goal(opp.api_football_id, 5),
                _goal(opp.api_football_id, 60),
            ],
        )
        result = await compute_game_state(cluj.id, session)
        by_state = {r.state: r for r in result.records}
        assert by_state["drawing"].avg_goals_against == 1.0
        assert by_state["losing"].avg_goals_against == 1.0
        assert by_state["losing"].matches == 1

    @pytest.mark.asyncio
    async def test_own_goal_credited_to_opponent(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "FCSB")
        # Cluj player scores own goal -> counted as goal_against
        await _make_match(
            session, fixture_id=1, home_id=cluj.id, away_id=opp.id,
            events=[_goal(cluj.api_football_id, 30, own_goal=True)],
        )
        result = await compute_game_state(cluj.id, session)
        by_state = {r.state: r for r in result.records}
        assert by_state["drawing"].avg_goals_against == 1.0
        assert by_state["drawing"].avg_goals_for == 0.0

    @pytest.mark.asyncio
    async def test_events_processed_in_minute_order(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "FCSB")
        # Events given out of chronological order
        await _make_match(
            session, fixture_id=1, home_id=cluj.id, away_id=opp.id,
            events=[
                _goal(cluj.api_football_id, 80),  # would be "winning" if processed second
                _goal(cluj.api_football_id, 10),  # actually first chronologically
            ],
        )
        result = await compute_game_state(cluj.id, session)
        by_state = {r.state: r for r in result.records}
        # Correct ordering: first goal at min 10 in drawing, second at min 80 in winning
        assert by_state["drawing"].avg_goals_for == 1.0
        assert by_state["winning"].avg_goals_for == 1.0

    @pytest.mark.asyncio
    async def test_non_goal_events_ignored(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "FCSB")
        await _make_match(
            session, fixture_id=1, home_id=cluj.id, away_id=opp.id,
            events=[
                {"time": {"elapsed": 20}, "team": {"id": cluj.api_football_id},
                 "type": "Card", "detail": "Yellow Card"},
                {"time": {"elapsed": 60}, "team": {"id": cluj.api_football_id},
                 "type": "subst", "detail": "Substitution 1"},
                _goal(cluj.api_football_id, 75),
            ],
        )
        result = await compute_game_state(cluj.id, session)
        by_state = {r.state: r for r in result.records}
        assert by_state["drawing"].avg_goals_for == 1.0

    @pytest.mark.asyncio
    async def test_excludes_matches_without_stats(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "FCSB")
        # Match with stats: cluj scores
        await _make_match(
            session, fixture_id=1, home_id=cluj.id, away_id=opp.id,
            events=[_goal(cluj.api_football_id, 10)],
        )
        # Match without stats: forced SQL NULL
        from sqlalchemy import null, update as sqla_update
        await _make_match(
            session, fixture_id=2, home_id=cluj.id, away_id=opp.id,
            events=[_goal(cluj.api_football_id, 10)],
        )
        await session.execute(
            sqla_update(Match).where(Match.id == 2).values(
                stats_home=null(), stats_away=null()
            )
        )
        await session.flush()
        result = await compute_game_state(cluj.id, session)
        by_state = {r.state: r for r in result.records}
        # Only the with-stats match contributes
        assert by_state["drawing"].matches == 1

    @pytest.mark.asyncio
    async def test_unrelated_matches_ignored(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        a = await _make_team(session, 2, "Team A")
        b = await _make_team(session, 3, "Team B")
        await _make_match(
            session, fixture_id=1, home_id=a.id, away_id=b.id,
            events=[_goal(a.api_football_id, 10)],
        )
        result = await compute_game_state(cluj.id, session)
        for r in result.records:
            assert r.matches == 0

    @pytest.mark.asyncio
    async def test_match_with_no_events_visits_only_drawing(self, session) -> None:
        cluj = await _make_team(session, 1, "U Cluj")
        opp = await _make_team(session, 2, "FCSB")
        await _make_match(
            session, fixture_id=1, home_id=cluj.id, away_id=opp.id,
            events=[],
        )
        result = await compute_game_state(cluj.id, session)
        by_state = {r.state: r for r in result.records}
        assert by_state["drawing"].matches == 1
        assert by_state["winning"].matches == 0
        assert by_state["losing"].matches == 0
