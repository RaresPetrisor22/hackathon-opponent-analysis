from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.dossier import FormSection


async def compute_form(team_id: int, session: AsyncSession, n: int = 10) -> FormSection:
    """Compute recent form for a team.

    Queries the last `n` completed fixtures for `team_id`, ordered by date
    descending. Calculates W/D/L counts, goals scored/conceded averages,
    and returns a FormSection with last_5 and last_10 match entries.

    Args:
        team_id: Internal DB team ID.
        session: Async SQLAlchemy session.
        n: How many recent matches to fetch (at least 10 for both windows).

    Query filter: always apply Match.complete() — five fixtures have no stats
    from the API and must be excluded to keep results consistent.
    """
    # TODO: implement — use .where(Match.complete()) in all DB queries
    raise NotImplementedError
