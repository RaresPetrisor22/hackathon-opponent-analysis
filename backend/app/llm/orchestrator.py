from __future__ import annotations

"""Dossier orchestrator — two-stage LangChain pipeline.

Stage 1  Parallel Analysis Agents
    Six deterministic analysis modules run concurrently via RunnableParallel.
    Each module queries the DB and returns a typed Pydantic section object.
    No LLM calls happen here.

Stage 2  Gameplan Synthesis Agent
    A single LangChain chain (GAMEPLAN_PROMPT | llm.with_structured_output)
    receives all six section outputs serialised as JSON and produces the
    GameplanNarrative. This is the only LLM call in the pipeline.

The two stages are kept strictly sequential: Stage 2 never starts before
Stage 1 completes.
"""

import json
from datetime import datetime, timezone

from langchain_core.runnables import RunnableLambda, RunnableParallel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis import form, game_state, identity, matchups, media_intel, players, referee
from app.config import settings
from app.llm.client import _get_llm
from app.llm.prompts import GAMEPLAN_PROMPT
from app.models.team import Team
from app.schemas.dossier import (
    DossierResponse,
    FormSection,
    GameStateSection,
    GameplanNarrative,
    IdentitySection,
    MatchupSection,
    MediaIntelligence,
    PlayerCardsSection,
    RefereeSection,
)


# ---------------------------------------------------------------------------
# Stage 1: Parallel Analysis Agents
# Each lambda receives a context dict: {"team_id": int, "session": AsyncSession}
# and returns the typed section object for that analysis domain.
# ---------------------------------------------------------------------------

def _build_parallel_stage(
    team_id: int, api_football_id: int, session: AsyncSession
) -> RunnableParallel:  # type: ignore[type-arg]
    """Wire up the six analysis modules as concurrent runnables.

    Using RunnableLambda so each async function integrates cleanly with
    LangChain's ainvoke, which handles coroutine detection automatically.
    """

    async def run_form(_: dict) -> FormSection:
        return await form.compute_form(team_id, session)

    async def run_identity(_: dict) -> IdentitySection:
        return await identity.compute_identity(team_id, session)

    async def run_matchups(_: dict) -> MatchupSection:
        return await matchups.predict_matchup(team_id, settings.fcu_team_id, session)

    async def run_players(_: dict) -> PlayerCardsSection:
        return await players.compute_player_cards(team_id, session)

    async def run_game_state(_: dict) -> GameStateSection:
        return await game_state.compute_game_state(team_id, session)

    async def run_referee(_: dict) -> RefereeSection:
        # No upcoming-fixture wiring yet — pass None so referee.py returns
        # the unassigned-fixture stub. Replace with actual referee_name once
        # the upcoming-fixture lookup is in place.
        return await referee.compute_referee_context(
            None, settings.superliga_league_id, settings.superliga_season, session
        )

    async def run_media_intel(_: dict) -> MediaIntelligence:
        # Pinecone vectors are keyed on api_football_id, not the internal DB id
        return await media_intel.get_media_intel(api_football_id)

    return RunnableParallel(
        form=RunnableLambda(run_form),
        identity=RunnableLambda(run_identity),
        matchups=RunnableLambda(run_matchups),
        players=RunnableLambda(run_players),
        game_state=RunnableLambda(run_game_state),
        referee=RunnableLambda(run_referee),
        media_intel=RunnableLambda(run_media_intel),
    )


# ---------------------------------------------------------------------------
# Stage 2: Gameplan Synthesis Agent
# ---------------------------------------------------------------------------

def _build_gameplan_chain() -> object:
    """Return the GAMEPLAN_PROMPT | llm.with_structured_output chain."""
    return GAMEPLAN_PROMPT | _get_llm().with_structured_output(GameplanNarrative)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def generate_dossier(
    opponent_team_id: int,
    session: AsyncSession,
) -> DossierResponse:
    """Generate the full pre-match dossier for the given opponent.

    Args:
        opponent_team_id: Internal DB team ID of the next opponent.
        session: Async SQLAlchemy session (injected by FastAPI dependency).

    Returns:
        DossierResponse with all seven sections populated.
    """
    opponent = (
        await session.execute(select(Team).where(Team.id == opponent_team_id))
    ).scalar_one_or_none()
    if opponent is None:
        raise ValueError(f"Opponent team_id={opponent_team_id} not found.")
    opponent_name = opponent.name

    # ---- Stage 1: Parallel Analysis Agents --------------------------------
    parallel = _build_parallel_stage(opponent_team_id, opponent.api_football_id, session)
    sections = await parallel.ainvoke({})

    form_section: FormSection = sections["form"]
    identity_section: IdentitySection = sections["identity"]
    matchup_section: MatchupSection = sections["matchups"]
    players_section: PlayerCardsSection = sections["players"]
    game_state_section: GameStateSection = sections["game_state"]
    referee_section: RefereeSection = sections["referee"]
    media_intel_section: MediaIntelligence = sections["media_intel"]

    # ---- Stage 2: Gameplan Synthesis Agent --------------------------------
    now = datetime.now(timezone.utc)
    full_dossier_json = json.dumps(
        {
            "form": form_section.model_dump(),
            "identity": identity_section.model_dump(),
            "matchups": matchup_section.model_dump(),
            "players": players_section.model_dump(),
            "game_state": game_state_section.model_dump(),
            "referee": referee_section.model_dump(),
            "media_intel": media_intel_section.model_dump(),
        },
        default=str,
    )

    gameplan_chain = _build_gameplan_chain()
    gameplan: GameplanNarrative = await gameplan_chain.ainvoke(  # type: ignore[assignment]
        {
            "opponent_name": opponent_name,
            "match_date": now.date().isoformat(),
            "full_dossier_json": full_dossier_json,
        }
    )

    return DossierResponse(
        opponent_id=opponent_team_id,
        opponent_name=opponent_name,
        generated_at=now.isoformat(),
        form=form_section,
        identity=identity_section,
        matchups=matchup_section,
        players=players_section,
        game_state=game_state_section,
        referee=referee_section,
        media_intel=media_intel_section,
        gameplan=gameplan,
    )
