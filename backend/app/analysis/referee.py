from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.dossier import RefereeSection


async def compute_referee_context(
    referee_name: str | None,
    league_id: int,
    season: int,
    session: AsyncSession,
) -> RefereeSection:
    """Compute statistical profile for the assigned referee.

    Queries all fixtures in the season officiated by the named referee.
    Aggregates avg yellow cards, red cards, fouls called per match.
    Computes a rough home-advantage factor (home win % in their fixtures vs
    league average). Returns RefereeSection; if referee_name is None, returns
    a section with null/zero values and a note.

    Args:
        referee_name: Full name as returned by API-Football (may be None if unassigned).
        league_id: API-Football league ID.
        season: Season year.
        session: Async SQLAlchemy session.
    """
    # TODO: implement
    raise NotImplementedError
