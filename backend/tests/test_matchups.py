"""Unit tests for analysis.matchups: classify_match + build_feature_matrix.

Run with:
    cd backend
    uv run pytest tests/test_matchups.py -v
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.analysis.matchups import (
    FEATURE_COLS,
    build_feature_matrix,
    classify_match,
)
from app.db import Base
from app.models.archetype import Archetype  # noqa: F401  (register with metadata)
from app.models.match import Match
from app.models.player import Player  # noqa: F401
from app.models.team import Team


# ---------------------------------------------------------------------------
# classify_match — pure function, no DB
# ---------------------------------------------------------------------------

class TestClassifyMatch:
    def test_returns_all_feature_cols(self) -> None:
        out = classify_match({}, {})
        assert set(out.keys()) == set(FEATURE_COLS)

    def test_all_zero_when_no_data(self) -> None:
        out = classify_match({}, {})
        assert out["possession_pct"] == 0.0
        assert out["pass_accuracy"] == 0.0
        assert out["pressing_proxy"] == 0.0
        assert out["directness"] == 0.0
        # shots_ratio defaults to 0.5 (neutral) when both sides have 0 shots
        assert out["shots_ratio"] == 0.5

    def test_basic_extraction(self) -> None:
        team = {
            "ball_possession": 60,
            "total_shots": 12,
            "passes_pct": 85,
            "fouls": 8,
            "total_passes": 480,
        }
        opp = {"total_shots": 8}
        out = classify_match(team, opp)
        assert out["possession_pct"] == 60.0
        assert out["pass_accuracy"] == 85.0
        assert out["pressing_proxy"] == 8.0
        assert out["shots_ratio"] == pytest.approx(12 / 20)
        assert out["directness"] == pytest.approx(12 / 480)

    def test_none_values_treated_as_zero(self) -> None:
        team = {"ball_possession": None, "total_shots": 5, "passes_pct": None,
                "fouls": None, "total_passes": 0}
        opp = {"total_shots": None}
        out = classify_match(team, opp)
        assert out["possession_pct"] == 0.0
        assert out["pass_accuracy"] == 0.0
        assert out["pressing_proxy"] == 0.0
        # zero passes -> directness fall back to 0.0 (avoid div-by-zero)
        assert out["directness"] == 0.0
        # team_shots=5, opp_shots=0 -> all shots from team
        assert out["shots_ratio"] == 1.0


# ---------------------------------------------------------------------------
# build_feature_matrix — DB-backed
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


async def _team(session, api_id: int, name: str) -> Team:
    t = Team(api_football_id=api_id, name=name)
    session.add(t)
    await session.flush()
    return t


async def _match(
    session, *, fixture_id, home_id, away_id, home_score, away_score, date,
    home_stats=None, away_stats=None,
):
    m = Match(
        id=fixture_id,
        season_id=2024,
        league_id=283,
        home_team_id=home_id,
        away_team_id=away_id,
        home_score=home_score,
        away_score=away_score,
        date=date,
        status="FT",
        stats_home=home_stats or {"ball_possession": 50, "total_shots": 10,
                                  "total_passes": 400, "passes_pct": 80, "fouls": 10},
        stats_away=away_stats or {"ball_possession": 50, "total_shots": 10,
                                  "total_passes": 400, "passes_pct": 80, "fouls": 10},
    )
    session.add(m)
    await session.flush()
    return m


class TestBuildFeatureMatrix:
    @pytest.mark.asyncio
    async def test_empty_db(self, session) -> None:
        df = await build_feature_matrix(session)
        assert df.empty
        assert list(df.columns) == ["match_id", "team_id", "season", *FEATURE_COLS]

    @pytest.mark.asyncio
    async def test_one_match_yields_two_rows(self, session) -> None:
        a = await _team(session, 1, "A")
        b = await _team(session, 2, "B")
        await _match(
            session, fixture_id=1, home_id=a.id, away_id=b.id,
            home_score=2, away_score=1,
            date=datetime(2025, 1, 10, tzinfo=timezone.utc),
        )
        df = await build_feature_matrix(session)
        assert len(df) == 2
        assert set(df["team_id"]) == {a.id, b.id}
        assert (df["match_id"] == 1).all()
        assert (df["season"] == 2024).all()

    @pytest.mark.asyncio
    async def test_excludes_matches_without_stats(self, session) -> None:
        """Match.complete() filter: stats_home IS NOT NULL."""
        from sqlalchemy import null, update
        a = await _team(session, 1, "A")
        b = await _team(session, 2, "B")
        await _match(
            session, fixture_id=1, home_id=a.id, away_id=b.id,
            home_score=1, away_score=0,
            date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        await _match(
            session, fixture_id=2, home_id=a.id, away_id=b.id,
            home_score=2, away_score=2,
            date=datetime(2025, 1, 8, tzinfo=timezone.utc),
        )
        # Force fixture 2 to have SQL NULL stats (JSON columns store None as
        # JSON null by default; we need real SQL NULL for complete() to filter).
        await session.execute(
            update(Match).where(Match.id == 2)
            .values(stats_home=null(), stats_away=null())
        )
        await session.flush()
        df = await build_feature_matrix(session)
        assert set(df["match_id"]) == {1}
