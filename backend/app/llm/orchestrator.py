from __future__ import annotations

"""Dossier orchestrator.

Flow
----
1. Run all six deterministic analysis modules concurrently via asyncio.gather:
   - form.compute_form
   - identity.compute_identity
   - matchups.predict_matchup
   - players.compute_player_cards
   - game_state.compute_game_state
   - referee.compute_referee_context

2. Feed the structured results into call_llm to generate the GameplanNarrative.
   The LLM receives the full dossier JSON so it can synthesise across sections.

3. Assemble and return the complete DossierResponse.

The LLM is never called before the data modules complete.
"""

import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis import form, game_state, identity, matchups, players, referee
from app.config import settings
from app.llm import client as llm_client
from app.llm.prompts import GAMEPLAN_PROMPT, SYSTEM_SCOUTING_ANALYST
from app.schemas.dossier import DossierResponse, GameplanNarrative


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
    # TODO: fetch opponent team record (name, etc.) from DB

    # Step 1: run all deterministic modules in parallel
    (
        form_section,
        identity_section,
        matchup_section,
        players_section,
        game_state_section,
        referee_section,
    ) = await asyncio.gather(
        form.compute_form(opponent_team_id, session),
        identity.compute_identity(opponent_team_id, session),
        matchups.predict_matchup(opponent_team_id, settings.fcu_team_id, session),
        players.compute_player_cards(opponent_team_id, session),
        game_state.compute_game_state(opponent_team_id, session),
        referee.compute_referee_context(None, settings.superliga_league_id, settings.superliga_season, session),
    )

    # Step 2: LLM narrative synthesis
    # TODO: build full_dossier_json from the six sections
    gameplan = await llm_client.call_llm(
        system=SYSTEM_SCOUTING_ANALYST,
        user=GAMEPLAN_PROMPT.format(
            opponent_name="TBD",
            match_date="TBD",
            full_dossier_json="{}",
        ),
        response_schema=GameplanNarrative,
    )

    # Step 3: assemble response
    return DossierResponse(
        opponent_id=opponent_team_id,
        opponent_name="TBD",
        generated_at=datetime.now(timezone.utc).isoformat(),
        form=form_section,
        identity=identity_section,
        matchups=matchup_section,
        players=players_section,
        game_state=game_state_section,
        referee=referee_section,
        gameplan=gameplan,
    )
