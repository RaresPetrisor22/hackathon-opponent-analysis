from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.dossier import PlayerCardsSection


async def compute_player_cards(
    team_id: int, session: AsyncSession
) -> PlayerCardsSection:
    """Identify key attacking threats and defensive vulnerabilities.

    For threats: rank players by goals + assists over the season, surface top 3.
    For vulnerabilities: identify positions / players with high cards/fouls
    conceded and low duel-success rates (from Wyscout data where available).

    Returns at most 5 threat cards and 3 vulnerability cards.

    Args:
        team_id: Internal DB team ID.
        session: Async SQLAlchemy session.
    """
    # TODO: implement
    raise NotImplementedError
