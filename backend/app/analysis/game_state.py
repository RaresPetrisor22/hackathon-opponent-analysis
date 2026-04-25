from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.dossier import GameStateSection


async def compute_game_state(team_id: int, session: AsyncSession) -> GameStateSection:
    """Analyse how the team behaves in different game states.

    Uses fixture event data (goals/cards) to reconstruct match timelines and
    determine whether the team was winning, drawing, or losing at each scoring
    event. Aggregates avg goals-for/against and derives qualitative labels for
    tendencies (e.g. "defends deep when winning", "increases directness when
    losing").

    Note: no coordinate data — behavioural inferences are stat-based only.

    Args:
        team_id: Internal DB team ID.
        session: Async SQLAlchemy session.

    Query filter: always apply Match.complete() — five fixtures have no stats
    from the API and must be excluded to keep results consistent.
    """
    # TODO: implement — use .where(Match.complete()) in all DB queries
    raise NotImplementedError
