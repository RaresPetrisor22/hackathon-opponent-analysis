"""Unit tests for llm.orchestrator.generate_dossier.

Verifies the wiring between Stage 1 (parallel analysis) and Stage 2 (LLM
gameplan synthesis) without making real LLM calls. Stubs the analysis
modules and the gameplan chain.

Run with:
    cd backend
    uv run pytest tests/test_orchestrator.py -v
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base
from app.llm import orchestrator
from app.models.archetype import Archetype  # noqa: F401
from app.models.match import Match  # noqa: F401
from app.models.player import Player  # noqa: F401
from app.models.team import Team
from app.schemas.dossier import (
    FormSection,
    GameStateRecord,
    GameStateSection,
    GameplanNarrative,
    IdentitySection,
    MatchupSection,
    PlayerCardsSection,
    RefereeSection,
    TacticalIdentityStats,
)


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()


def _stub_form() -> FormSection:
    return FormSection(
        last_5=[], last_10=[], wins_last5=0, draws_last5=0, losses_last5=0,
        goals_scored_avg=0.0, goals_conceded_avg=0.0, form_string="",
    )


def _stub_identity() -> IdentitySection:
    return IdentitySection(
        stats=TacticalIdentityStats(
            avg_possession=50, avg_shots=10, avg_shots_on_target=4,
            avg_pass_accuracy=75, avg_fouls=12, avg_yellow_cards=2,
            avg_corners=5, preferred_formation="4-3-3",
        ),
        pressing_intensity="medium", play_style="balanced", notes="",
    )


def _stub_matchups() -> MatchupSection:
    return MatchupSection(
        archetypes=[], fcu_archetype_id=0, fcu_archetype_name="x",
        prediction_summary="", best_archetype_vs_opponent="",
    )


def _stub_game_state() -> GameStateSection:
    return GameStateSection(
        records=[
            GameStateRecord(state="winning", matches=0, avg_goals_for=0.0,
                            avg_goals_against=0.0, defensive_change="",
                            offensive_change=""),
            GameStateRecord(state="drawing", matches=0, avg_goals_for=0.0,
                            avg_goals_against=0.0, defensive_change="",
                            offensive_change=""),
            GameStateRecord(state="losing", matches=0, avg_goals_for=0.0,
                            avg_goals_against=0.0, defensive_change="",
                            offensive_change=""),
        ],
        tendency_when_losing="", tendency_when_winning="",
    )


class _FakeChain:
    """Stand-in for the GAMEPLAN_PROMPT | llm chain."""

    def __init__(self) -> None:
        self.last_inputs: dict[str, Any] | None = None

    async def ainvoke(self, inputs: dict[str, Any]) -> GameplanNarrative:
        self.last_inputs = inputs
        return GameplanNarrative(
            headline="Test headline",
            body="Test body",
            key_actions=["a", "b"],
        )


@pytest.fixture
def patch_pipeline(monkeypatch):
    """Stub all 6 analysis modules + the gameplan chain.

    Returns the fake chain so tests can assert on the inputs it received.
    """
    fake_chain = _FakeChain()

    async def fake_form(team_id, session):
        return _stub_form()

    async def fake_identity(team_id, session):
        return _stub_identity()

    async def fake_matchups(team_id, fcu_id, session):
        return _stub_matchups()

    async def fake_game_state(team_id, session):
        return _stub_game_state()

    async def fake_players(team_id, session):
        return PlayerCardsSection(key_threats=[], defensive_vulnerabilities=[])

    monkeypatch.setattr(orchestrator.form, "compute_form", fake_form)
    monkeypatch.setattr(orchestrator.identity, "compute_identity", fake_identity)
    monkeypatch.setattr(orchestrator.matchups, "predict_matchup", fake_matchups)
    monkeypatch.setattr(orchestrator.game_state, "compute_game_state", fake_game_state)
    monkeypatch.setattr(orchestrator.players, "compute_player_cards", fake_players)
    monkeypatch.setattr(orchestrator, "_build_gameplan_chain", lambda: fake_chain)
    return fake_chain


class TestGenerateDossier:
    @pytest.mark.asyncio
    async def test_unknown_opponent_raises_value_error(
        self, session, patch_pipeline
    ) -> None:
        with pytest.raises(ValueError, match="not found"):
            await orchestrator.generate_dossier(999, session)

    @pytest.mark.asyncio
    async def test_returns_full_dossier_with_opponent_name(
        self, session, patch_pipeline
    ) -> None:
        opp = Team(api_football_id=42, name="Rapid Bucuresti")
        session.add(opp)
        await session.flush()

        result = await orchestrator.generate_dossier(opp.id, session)

        assert result.opponent_id == opp.id
        assert result.opponent_name == "Rapid Bucuresti"
        assert result.gameplan.headline == "Test headline"
        assert result.form is not None
        assert result.identity is not None
        assert result.matchups is not None
        assert result.game_state is not None
        # players + referee both run live. The fake players stub returns
        # an empty section; referee runs the real module which, with no
        # upcoming-fixture lookup yet, returns the unassigned-referee stub.
        assert result.players.key_threats == []
        assert result.referee.referee_name is None
        assert "No referee assigned" in result.referee.notes

    @pytest.mark.asyncio
    async def test_gameplan_chain_receives_opponent_name_and_dossier_json(
        self, session, patch_pipeline
    ) -> None:
        opp = Team(api_football_id=42, name="Sepsi OSK")
        session.add(opp)
        await session.flush()

        await orchestrator.generate_dossier(opp.id, session)

        inputs = patch_pipeline.last_inputs
        assert inputs is not None
        assert inputs["opponent_name"] == "Sepsi OSK"
        # match_date is today's ISO date — just check shape
        assert len(inputs["match_date"]) == 10
        # full_dossier_json must include all six sections as keys
        for key in ("form", "identity", "matchups", "players",
                    "game_state", "referee"):
            assert f'"{key}"' in inputs["full_dossier_json"]


class TestExceptionPropagation:
    """All analysis-module errors must surface so the route returns a real
    500 instead of silently shipping garbage. Every module is implemented
    now — no NotImplementedError swallowing remains."""

    @pytest.mark.asyncio
    async def test_form_runtime_error_propagates(
        self, session, patch_pipeline, monkeypatch
    ) -> None:
        opp = Team(api_football_id=1, name="X")
        session.add(opp)
        await session.flush()

        async def boom(team_id, session):
            raise RuntimeError("form blew up")

        monkeypatch.setattr(orchestrator.form, "compute_form", boom)
        with pytest.raises(RuntimeError, match="form blew up"):
            await orchestrator.generate_dossier(opp.id, session)

    @pytest.mark.asyncio
    async def test_matchups_error_propagates(
        self, session, patch_pipeline, monkeypatch
    ) -> None:
        opp = Team(api_football_id=1, name="X")
        session.add(opp)
        await session.flush()

        async def boom(team_id, fcu_id, session):
            raise RuntimeError("matchups blew up")

        monkeypatch.setattr(orchestrator.matchups, "predict_matchup", boom)
        with pytest.raises(RuntimeError, match="matchups blew up"):
            await orchestrator.generate_dossier(opp.id, session)

    @pytest.mark.asyncio
    async def test_players_error_propagates(
        self, session, patch_pipeline, monkeypatch
    ) -> None:
        opp = Team(api_football_id=1, name="X")
        session.add(opp)
        await session.flush()

        async def boom(team_id, session):
            raise RuntimeError("players truly broken")

        monkeypatch.setattr(orchestrator.players, "compute_player_cards", boom)
        with pytest.raises(RuntimeError, match="players truly broken"):
            await orchestrator.generate_dossier(opp.id, session)

    @pytest.mark.asyncio
    async def test_referee_error_propagates(
        self, session, patch_pipeline, monkeypatch
    ) -> None:
        opp = Team(api_football_id=1, name="X")
        session.add(opp)
        await session.flush()

        async def boom(referee_name, league_id, season, session):
            raise RuntimeError("referee truly broken")

        monkeypatch.setattr(orchestrator.referee, "compute_referee_context", boom)
        with pytest.raises(RuntimeError, match="referee truly broken"):
            await orchestrator.generate_dossier(opp.id, session)


class TestStageOrdering:
    """Stage 2 (LLM) must never start before Stage 1 (analysis) finishes."""

    @pytest.mark.asyncio
    async def test_gameplan_chain_invoked_after_all_sections_ready(
        self, session, monkeypatch
    ) -> None:
        opp = Team(api_football_id=7, name="Farul")
        session.add(opp)
        await session.flush()

        events: list[str] = []

        async def fake_form(team_id, session):
            events.append("form")
            return _stub_form()

        async def fake_identity(team_id, session):
            events.append("identity")
            return _stub_identity()

        async def fake_matchups(team_id, fcu_id, session):
            events.append("matchups")
            return _stub_matchups()

        async def fake_game_state(team_id, session):
            events.append("game_state")
            return _stub_game_state()

        class OrderedFakeChain:
            async def ainvoke(self, inputs):
                events.append("gameplan")
                return GameplanNarrative(headline="h", body="b", key_actions=[])

        monkeypatch.setattr(orchestrator.form, "compute_form", fake_form)
        monkeypatch.setattr(orchestrator.identity, "compute_identity", fake_identity)
        monkeypatch.setattr(orchestrator.matchups, "predict_matchup", fake_matchups)
        monkeypatch.setattr(
            orchestrator.game_state, "compute_game_state", fake_game_state
        )
        monkeypatch.setattr(orchestrator, "_build_gameplan_chain", OrderedFakeChain)

        await orchestrator.generate_dossier(opp.id, session)

        # gameplan must appear last; all four real analysis modules must
        # have run before it (players + referee fall through to empty
        # without being recorded here, which is fine).
        assert events[-1] == "gameplan"
        assert {"form", "identity", "matchups", "game_state"}.issubset(set(events[:-1]))


class TestResponseShape:
    @pytest.mark.asyncio
    async def test_generated_at_is_iso_utc(
        self, session, patch_pipeline
    ) -> None:
        opp = Team(api_football_id=99, name="Petrolul")
        session.add(opp)
        await session.flush()

        result = await orchestrator.generate_dossier(opp.id, session)
        # Must round-trip through datetime.fromisoformat and be tz-aware.
        parsed = datetime.fromisoformat(result.generated_at)
        assert parsed.tzinfo is not None
        # Should be within a tight window of "now" — generously 30s.
        delta = abs((datetime.now(timezone.utc) - parsed).total_seconds())
        assert delta < 30

    @pytest.mark.asyncio
    async def test_dossier_json_is_valid_serialised_payload(
        self, session, patch_pipeline
    ) -> None:
        """The JSON handed to the LLM must be parseable and contain dicts."""
        opp = Team(api_football_id=11, name="UTA Arad")
        session.add(opp)
        await session.flush()

        await orchestrator.generate_dossier(opp.id, session)

        payload = json.loads(patch_pipeline.last_inputs["full_dossier_json"])
        assert set(payload.keys()) == {
            "form", "identity", "matchups", "players", "game_state", "referee"
        }
        for v in payload.values():
            assert isinstance(v, dict)


class TestRouteValueErrorMapping:
    """Route translates ValueError -> 404 instead of 500."""

    @pytest.mark.asyncio
    async def test_route_returns_404_for_unknown_team(
        self, session, patch_pipeline, monkeypatch
    ) -> None:
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from app.db import get_session
        from app.routes.dossier import router

        app = FastAPI()
        app.include_router(router, prefix="/dossier")

        async def override_session():
            yield session

        app.dependency_overrides[get_session] = override_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            r = await c.get("/dossier/9999")
        assert r.status_code == 404
        assert "not found" in r.json()["detail"]
