"""Unit tests for analysis.players.compute_player_cards.

Run with:
    cd backend
    uv run pytest tests/test_players.py -v
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import null, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.analysis.players import compute_player_cards
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
    t = Team(api_football_id=api_id, name=name)
    session.add(t)
    await session.flush()
    return t


def _player_entry(
    *,
    player_id: int,
    name: str,
    minutes: int = 90,
    position: str = "F",
    number: int | None = 9,
    goals: int = 0,
    assists: int = 0,
    shots: int = 0,
    shots_on: int = 0,
    yellows: int = 0,
    reds: int = 0,
    fouls_committed: int = 0,
    duels_won: int = 0,
    duels_total: int = 0,
    photo: str | None = "https://photo.example/p.png",
) -> dict[str, Any]:
    return {
        "player": {"id": player_id, "name": name, "photo": photo},
        "statistics": [
            {
                "games": {"minutes": minutes, "number": number, "position": position},
                "goals": {"total": goals, "assists": assists},
                "shots": {"total": shots, "on": shots_on},
                "cards": {"yellow": yellows, "red": reds},
                "fouls": {"committed": fouls_committed},
                "duels": {"won": duels_won, "total": duels_total},
                "tackles": {"total": 0},
            }
        ],
    }


async def _make_match(
    session,
    *,
    fixture_id: int,
    home_id: int,
    away_id: int,
    players_home: list | None = None,
    players_away: list | None = None,
    has_stats: bool = True,
) -> Match:
    m = Match(
        id=fixture_id,
        season_id=2024,
        league_id=283,
        home_team_id=home_id,
        away_team_id=away_id,
        home_score=0,
        away_score=0,
        date=datetime(2025, 1, fixture_id, tzinfo=timezone.utc),
        status="FT",
        stats_home={"ball_possession": 50} if has_stats else None,
        stats_away={"ball_possession": 50} if has_stats else None,
        players_home=players_home,
        players_away=players_away,
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


class TestComputePlayerCards:
    @pytest.mark.asyncio
    async def test_empty_db_returns_empty_lists(self, session) -> None:
        team = await _make_team(session, 1, "Solo")
        r = await compute_player_cards(team.id, session)
        assert r.key_threats == []
        assert r.defensive_vulnerabilities == []

    @pytest.mark.asyncio
    async def test_threats_ranked_by_goals_plus_assists(self, session) -> None:
        a = await _make_team(session, 1, "A")
        b = await _make_team(session, 2, "B")
        await _make_match(
            session, fixture_id=1, home_id=a.id, away_id=b.id,
            players_home=[
                _player_entry(player_id=10, name="Striker", goals=3, assists=1),
                _player_entry(player_id=11, name="Winger", goals=1, assists=4),
                _player_entry(player_id=12, name="Defender", goals=0, assists=0),
            ],
        )
        r = await compute_player_cards(a.id, session)
        names = [c.name for c in r.key_threats]
        # Striker (4 G+A) and Winger (5 G+A) — winger ranks first
        assert names[0] == "Winger"
        assert names[1] == "Striker"
        assert "Defender" not in names  # 0 contributions excluded

    @pytest.mark.asyncio
    async def test_threat_level_thresholds(self, session) -> None:
        a = await _make_team(session, 1, "A")
        b = await _make_team(session, 2, "B")
        # 3 matches contributing to thresholds
        for i in range(3):
            await _make_match(
                session, fixture_id=i + 1, home_id=a.id, away_id=b.id,
                players_home=[
                    _player_entry(player_id=10, name="Star", goals=3, assists=0),
                    _player_entry(player_id=11, name="Mid", goals=1, assists=1),
                    _player_entry(player_id=12, name="Sub", goals=0, assists=1),
                ],
            )
        r = await compute_player_cards(a.id, session)
        cards = {c.name: c for c in r.key_threats}
        assert cards["Star"].threat_level == "high"     # 9 G+A
        assert cards["Mid"].threat_level == "medium"    # 6 G+A
        assert cards["Sub"].threat_level == "low"       # 3 G+A

    @pytest.mark.asyncio
    async def test_aggregates_across_matches(self, session) -> None:
        a = await _make_team(session, 1, "A")
        b = await _make_team(session, 2, "B")
        # team plays 2 matches: once home, once away
        await _make_match(
            session, fixture_id=1, home_id=a.id, away_id=b.id,
            players_home=[_player_entry(player_id=10, name="Fwd", goals=2, assists=1, minutes=90)],
        )
        await _make_match(
            session, fixture_id=2, home_id=b.id, away_id=a.id,
            players_away=[_player_entry(player_id=10, name="Fwd", goals=1, assists=0, minutes=60)],
        )
        r = await compute_player_cards(a.id, session)
        c = r.key_threats[0]
        assert c.key_stats["goals"] == 3.0
        assert c.key_stats["assists"] == 1.0
        assert c.key_stats["matches"] == 2.0
        assert c.key_stats["minutes"] == 150.0

    @pytest.mark.asyncio
    async def test_skips_zero_minute_appearances(self, session) -> None:
        a = await _make_team(session, 1, "A")
        b = await _make_team(session, 2, "B")
        await _make_match(
            session, fixture_id=1, home_id=a.id, away_id=b.id,
            players_home=[
                _player_entry(player_id=10, name="Bench", minutes=0, goals=99),
            ],
        )
        r = await compute_player_cards(a.id, session)
        assert r.key_threats == []  # never featured -> no stats absorbed

    @pytest.mark.asyncio
    async def test_picks_modal_position_and_number(self, session) -> None:
        a = await _make_team(session, 1, "A")
        b = await _make_team(session, 2, "B")
        await _make_match(
            session, fixture_id=1, home_id=a.id, away_id=b.id,
            players_home=[_player_entry(
                player_id=10, name="Versatile", position="F", number=9,
                goals=1, assists=0,
            )],
        )
        await _make_match(
            session, fixture_id=2, home_id=a.id, away_id=b.id,
            players_home=[_player_entry(
                player_id=10, name="Versatile", position="F", number=9,
                goals=1, assists=0,
            )],
        )
        await _make_match(
            session, fixture_id=3, home_id=a.id, away_id=b.id,
            players_home=[_player_entry(
                player_id=10, name="Versatile", position="M", number=20,
                goals=1, assists=0,
            )],
        )
        r = await compute_player_cards(a.id, session)
        c = r.key_threats[0]
        assert c.position == "F"
        assert c.jersey_number == 9

    @pytest.mark.asyncio
    async def test_vulnerability_requires_min_matches(self, session) -> None:
        a = await _make_team(session, 1, "A")
        b = await _make_team(session, 2, "B")
        # Only 1 appearance — below MIN_MATCHES (3)
        await _make_match(
            session, fixture_id=1, home_id=a.id, away_id=b.id,
            players_home=[_player_entry(
                player_id=10, name="OneOff", yellows=3, reds=1, fouls_committed=8,
            )],
        )
        r = await compute_player_cards(a.id, session)
        assert r.defensive_vulnerabilities == []

    @pytest.mark.asyncio
    async def test_vulnerability_high_when_red_card(self, session) -> None:
        a = await _make_team(session, 1, "A")
        b = await _make_team(session, 2, "B")
        for i in range(3):
            await _make_match(
                session, fixture_id=i + 1, home_id=a.id, away_id=b.id,
                players_home=[_player_entry(
                    player_id=10, name="HotHead",
                    yellows=1 if i < 2 else 0,
                    reds=1 if i == 2 else 0,
                    fouls_committed=4,
                )],
            )
        r = await compute_player_cards(a.id, session)
        c = r.defensive_vulnerabilities[0]
        assert c.name == "HotHead"
        assert c.threat_level == "high"

    @pytest.mark.asyncio
    async def test_vulnerability_ranking_by_score(self, session) -> None:
        a = await _make_team(session, 1, "A")
        b = await _make_team(session, 2, "B")
        # Player 10: 6 yellows over 3 matches; Player 11: 3 yellows
        for i in range(3):
            await _make_match(
                session, fixture_id=i + 1, home_id=a.id, away_id=b.id,
                players_home=[
                    _player_entry(player_id=10, name="Cards", yellows=2, fouls_committed=3),
                    _player_entry(player_id=11, name="Cleaner", yellows=1, fouls_committed=2),
                ],
            )
        r = await compute_player_cards(a.id, session)
        names = [c.name for c in r.defensive_vulnerabilities]
        assert names.index("Cards") < names.index("Cleaner")

    @pytest.mark.asyncio
    async def test_excludes_matches_without_stats(self, session) -> None:
        a = await _make_team(session, 1, "A")
        b = await _make_team(session, 2, "B")
        await _make_match(
            session, fixture_id=1, home_id=a.id, away_id=b.id,
            players_home=[_player_entry(player_id=10, name="X", goals=2, assists=1)],
        )
        # match without stats shouldn't be counted, even if players list is present
        await _make_match(
            session, fixture_id=2, home_id=a.id, away_id=b.id,
            players_home=[_player_entry(player_id=10, name="X", goals=99, assists=99)],
            has_stats=False,
        )
        r = await compute_player_cards(a.id, session)
        c = r.key_threats[0]
        assert c.key_stats["goals"] == 2.0
        assert c.key_stats["matches"] == 1.0

    @pytest.mark.asyncio
    async def test_uses_correct_team_side(self, session) -> None:
        """When team is home, read players_home; when away, read players_away."""
        a = await _make_team(session, 1, "A")
        b = await _make_team(session, 2, "B")
        await _make_match(
            session, fixture_id=1, home_id=a.id, away_id=b.id,
            players_home=[_player_entry(player_id=10, name="A-Star", goals=3)],
            players_away=[_player_entry(player_id=20, name="B-Star", goals=99)],
        )
        await _make_match(
            session, fixture_id=2, home_id=b.id, away_id=a.id,
            players_home=[_player_entry(player_id=20, name="B-Star", goals=99)],
            players_away=[_player_entry(player_id=10, name="A-Star", goals=2)],
        )
        r = await compute_player_cards(a.id, session)
        names = [c.name for c in r.key_threats]
        assert "A-Star" in names
        assert "B-Star" not in names

    @pytest.mark.asyncio
    async def test_handles_missing_player_id(self, session) -> None:
        a = await _make_team(session, 1, "A")
        b = await _make_team(session, 2, "B")
        await _make_match(
            session, fixture_id=1, home_id=a.id, away_id=b.id,
            players_home=[
                {"player": {"id": None}, "statistics": []},
                _player_entry(player_id=10, name="Real", goals=1),
            ],
        )
        r = await compute_player_cards(a.id, session)
        assert len(r.key_threats) == 1
        assert r.key_threats[0].name == "Real"
